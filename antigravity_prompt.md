# Antigravity Prompt — litmus7 Project Handoff

> Paste everything below as a single prompt into Google Antigravity (Editor view or Manager view, project pointed at the litmus7 repo folder).

---

## PROMPT START

You are working inside the **litmus7** project — a product review intelligence platform that uses a divide-and-conquer pipeline to extract business insights from large volumes of customer reviews. I'm the team lead/architect; I own architecture, system design, and PR reviews across a 6-member team. Read all the context below before touching any code.

### Project Goal

Instead of prompting an LLM with an entire list of reviews at once, litmus7 chunks reviews (e.g. 1000 reviews → chunks of 100), runs each chunk through a parallel sub-agent to extract business-relevant insights, then runs an aggregator agent that synthesizes, deduplicates, scores, and filters those insights into a final structured response served via a FastAPI `/ask` endpoint.

Pipeline diagram (textual): ingestion/chunking → Parallel Model (N sub-agents, one per chunk) → Aggregator Agent (runs after the parallel step to synthesize) → filter/format → FastAPI response.

### Team Structure (for context — do not need to act on this directly)

- **Data Layer** (Members 1 & 2) — own `review_pipeline.py`: `chunk_reviews()` → `process_chunks_parallel()`, contract `list[list[str]]`.
- **AI Core** (Members 3 & 5) — own `aggregator.py` and `gemini_model.py` (the files this task focuses on).
- **Backend & Delivery** (Members 4 & 6) — own `main.py` and `test_main.py`, the FastAPI layer.

### Current Tech Stack

FastAPI, Google ADK (`Agent`, `ParallelAgent`, `SequentialAgent`, `InMemoryRunner`, `google_search` tool), Pydantic, asyncio, python-dotenv. **Gemini API is being replaced by a local LLM served through LM Studio, accessed via LiteLLM, while keeping the Google ADK orchestration layer unchanged.**

### Key Architectural Decision (the actual task)

We are migrating the AI Core layer from Google's Gemini API to a **local LLM run in LM Studio**, integrated through **LiteLLM** (`google.adk.models.lite_llm.LiteLlm`), without changing the ADK orchestration primitives (`Agent`, `ParallelAgent`, `SequentialAgent`, `InMemoryRunner`). Only the `model=` argument passed into each `Agent` changes.

What changes vs. what stays the same:

| Aspect | Before (Gemini API) | After (LM Studio / LiteLLM) |
|---|---|---|
| Model object | `Gemini(model='gemini-2.5-flash-lite', retry_options=retry_config)` | `LiteLlm(model='openai/<lmstudio-model-name>')` |
| Env vars | `GOOGLE_API_KEY` | `OPENAI_API_BASE`, `OPENAI_API_KEY` (point at local LM Studio server, e.g. `http://localhost:1234/v1`) |
| `retry_options` | Required (Gemini-specific) | Not supported on `LiteLlm` — drop it or wrap `ask()` in custom retry logic |
| `google_search` tool | Works natively (Gemini grounding) | **Not supported** through LiteLLM — remove it, or supply a custom search tool function |
| Rate limits | 429 RESOURCE_EXHAUSTED on free tier | None — bounded by local hardware throughput instead |
| Orchestration (`ParallelAgent`/`SequentialAgent`/`InMemoryRunner`) | unchanged | unchanged |

Setup pattern to follow:

```python
# pip install litellm
import os
from google.adk.models.lite_llm import LiteLlm

os.environ["OPENAI_API_BASE"] = "http://localhost:1234/v1"  # LM Studio local server
os.environ["OPENAI_API_KEY"] = "lm-studio"                  # any non-empty string works

local_model = LiteLlm(model="openai/<lmstudio-model-name>")  # use the exact name shown in LM Studio
```

One `LiteLlm` instance can be shared across every `Agent` in the pipeline (sub-agents + aggregator) unless we need different local models per role.

### Existing Code (current state, Gemini-based — this is what needs to be migrated)

**`main.py`** (FastAPI entrypoint, owned by Backend & Delivery):
```python
from fastapi import FastAPI
from models import Product
from contextlib import asynccontextmanager
from gemini_model import setup, ask

@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/ask")
async def ask_ai(prompt: str):
    response = await ask(prompt)
    return {"response": response}
# ... CRUD endpoints for /products omitted for brevity, unrelated to the model layer
```

**`gemini_model.py`** (AI Core, owned by Members 3 & 5 — this is the primary file to migrate):
```python
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search
from google.genai import types

retry_config = types.HttpRetryOptions(
    attempts=3, exp_base=2, initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

root_agent = Agent(
    model='gemini-2.5-flash-lite',
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
    tools=[google_search]
)

runner = None
session_id = None

async def setup():
    global runner, session_id
    runner = InMemoryRunner(agent=root_agent)
    session = await runner.session_service.create_session(
        app_name=runner.app_name, user_id="user",
    )
    session_id = session.id

async def ask(prompt: str) -> str:
    response_text = ""
    async for event in runner.run_async(
        user_id="user", session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
    return response_text
```

**Reference pattern for the parallel research pipeline** (this is the shape the real litmus7 sub-agent/aggregator pipeline should follow, adapted from a working ADK demo — currently Gemini-based, needs the same LiteLLM migration):

```python
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search

tech_researcher = Agent(
    name="TechResearcher",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""Research the latest AI/ML trends. Include 3 key developments,
the main companies involved, and the potential impact. Keep the report very concise (100 words).""",
    tools=[google_search],
    output_key="tech_research",
)

health_researcher = Agent(
    name="HealthResearcher",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""Research recent medical breakthroughs. Include 3 significant advances,
their practical applications, and estimated timelines. Keep the report concise (100 words).""",
    tools=[google_search],
    output_key="health_research",
)

finance_researcher = Agent(
    name="FinanceResearcher",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""Research current fintech trends. Include 3 key trends,
their market implications, and the future outlook. Keep the report concise (100 words).""",
    tools=[google_search],
    output_key="finance_research",
)

aggregator_agent = Agent(
    name="AggregatorAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""Combine these three research findings into a single executive summary:

    **Technology Trends:**
    {tech_research}

    **Health Breakthroughs:**
    {health_research}

    **Finance Innovations:**
    {finance_research}

    Your summary should highlight common themes, surprising connections, and the most important
    key takeaways from all three reports. The final summary should be around 200 words.""",
    output_key="executive_summary",
)

parallel_research_team = ParallelAgent(
    name="ParallelResearchTeam",
    sub_agents=[tech_researcher, health_researcher, finance_researcher],
)

root_agent = SequentialAgent(
    name="ResearchSystem",
    sub_agents=[parallel_research_team, aggregator_agent],
)

runner = InMemoryRunner(agent=root_agent)
response = await runner.run_debug(
    "Run the daily executive briefing on Tech, Health, and Finance"
)
```

In litmus7's real use case, swap "tech/health/finance researchers" conceptually for **N review-chunk sub-agents** (one per chunk of ~100 reviews), and the `aggregator_agent` becomes our 5-stage flow: **collect → deduplicate → score/rank → quality filter → format**, with scoring formula `score = frequency × confidence × category_weight`, and two dedup strategies available (keyword matching vs. LLM re-rank via the model itself). Final output schema per insight: `insight`, `score`, `frequency`, `example_quote`, `category` — this is what the `/ask` FastAPI endpoint serves.

**`models.py`**:
```python
from pydantic import BaseModel

class Product(BaseModel):
    id: int
    name: str
    description: str
    price: float
    quantity: int
```

**`setup.txt`** (environment setup, currently Gemini-oriented, needs an LM Studio note added):
```
1. python -m venv .venv
2. source .venv/bin/Activate
3. pip install fastapi uvicorn
4. pip install dotenv
5. pip install google-adk
6. uvicorn main:app --reload
```

### Known Issues / Constraints to Respect

- Gemini free-tier rate limits (429 `RESOURCE_EXHAUSTED`) were the original trigger for this migration — confirmed in local testing with `gemini-2.0-flash-lite` via a notebook (`Agentic-AI-ADK.ipynb`). This constraint disappears with the local LLM, but local hardware throughput becomes the new bottleneck — especially for the **Parallel Model** stage, where N sub-agents hit the same local LM Studio server concurrently and may queue rather than truly run in parallel.
- `google_search` only works with native Gemini grounding; it will **not** function through LiteLLM/OpenAI-compatible endpoints. For litmus7's actual workload (extracting insights from review text supplied directly in the prompt), no live web search is needed — dropping it has no functional impact.
- Not every local model supports reliable tool/function calling — pick a tool-calling-capable model in LM Studio if any tool use is required (e.g. Qwen2.5-Instruct, Llama-3.1-Instruct family).
- `litellm` must be installed as a separate pip package (`pip install litellm`) — it is not bundled with `google-adk`.
- Ollama remains a documented fallback (`ollama/<model_name>`, no extra env config needed) if LM Studio isn't available on a given machine.

### Task

1. Migrate `gemini_model.py` to use `LiteLlm` pointed at the local LM Studio server instead of the Gemini API, following the setup pattern and table above. Preserve the existing `setup()` / `ask()` function signatures exactly, since `main.py` imports them directly (`from gemini_model import setup, ask`) — do not break that contract.
2. Remove `retry_options` and `tools=[google_search]` from the agent definition (or replace `google_search` with a no-op/custom tool only if explicitly needed later).
3. Add a config flag (e.g. `MODEL_PROVIDER=local|gemini` via `.env`) so the team can switch backends without code changes — propose this as `model_provider.py` (rename from `gemini_model.py`) but confirm naming with me before renaming the shared file, since it's a multi-owner file.
4. Apply the same `LiteLlm` swap to the parallel sub-agent / aggregator pattern shown above, adapted for litmus7's actual chunk-processing pipeline (not the tech/health/finance demo — that's reference only).
5. Update `setup.txt` to add `pip install litellm` and a note about starting the local LM Studio server before running `uvicorn main:app --reload`.
6. Do not touch `main.py`'s product CRUD endpoints, `models.py`, or anything in Data Layer's `review_pipeline.py` scope — out of scope for this task.
7. After migrating, run the app locally (`uvicorn main:app --reload`) and verify `/ask` still returns a response end-to-end through the local model, reporting back any LM Studio connection issues.

Ask me before renaming any multi-owner file (`gemini_model.py`, `aggregator.py`) or changing any of the interface contracts listed above (`chunk_reviews()` → `process_chunks_parallel()` shape, the aggregator output JSON schema).

## PROMPT END
