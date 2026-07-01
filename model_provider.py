import os
import asyncio
from dotenv import load_dotenv
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

load_dotenv()
from aggregator import score_to_status, STATUS_NEEDS_ATTENTION

# Configuration parameters for LM Studio / LiteLLM local models
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "openai/qwen2.5-coder-7b-instruct-mlx")
LOCAL_PARALLEL_MODEL_NAME = os.getenv("LOCAL_PARALLEL_MODEL_NAME", LOCAL_MODEL_NAME)
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:1234/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "lm-studio")

# LiteLLM/LM Studio configuration
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Concurrency limit for local model provider to prevent LM Studio compute/OOM errors under concurrent load
CONCURRENCY_LIMIT = int(os.getenv("LOCAL_CONCURRENCY_LIMIT", "1"))
concurrency_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

# Monkeypatch LiteLlm.generate_content_async to enforce the concurrency limit
_original_generate_content_async = LiteLlm.generate_content_async

async def _semaphore_generate_content_async(self, *args, **kwargs):
    async with concurrency_semaphore:
        try:
            async for response in _original_generate_content_async(self, *args, **kwargs):
                yield response
        except Exception as e:
            is_parallel_model = (getattr(self, 'model', None) == LOCAL_PARALLEL_MODEL_NAME)
            if is_parallel_model and LOCAL_PARALLEL_MODEL_NAME != LOCAL_MODEL_NAME:
                print(f"⚠️ Warning: Model '{self.model}' failed with error: {e}")
                print(f"👉 Falling back to aggregator model '{LOCAL_MODEL_NAME}' to process this step...")
                old_model = self.model
                self.model = LOCAL_MODEL_NAME
                try:
                    async for response in _original_generate_content_async(self, *args, **kwargs):
                        yield response
                finally:
                    self.model = old_model
            else:
                raise e

LiteLlm.generate_content_async = _semaphore_generate_content_async

# Instantiate model objects
model_obj = LiteLlm(model=LOCAL_MODEL_NAME)
parallel_model_obj = LiteLlm(model=LOCAL_PARALLEL_MODEL_NAME)

print(f"✅ Aggregator Model: {LOCAL_MODEL_NAME}")
print(f"✅ Parallel Sub-agents Model: {LOCAL_PARALLEL_MODEL_NAME}")

async def setup():
    """
    Setup function mapping to main.py lifespan contract.
    No global runner is built here as the pipeline is dynamically constructed 
    per request based on the size of the reviews list.
    """
    pass

def chunk_reviews(prompt: str) -> list[list[str]]:
    """
    Helper to chunk a large block of reviews (each review on a separate line)
    into smaller sub-lists of reviews.
    """
    lines = [line.strip() for line in prompt.split('\n') if line.strip()]
    if not lines:
        return [["No reviews provided."]]
    
    # Cap total reviews to analyze for performance and context limits of local models
    max_reviews = int(os.getenv("MAX_REVIEWS_TO_ANALYZE", "100"))
    lines = lines[:max_reviews]
    
    # Dynamically select a chunk size based on input size
    if len(lines) < 10:
        chunk_size = 3
    elif len(lines) < 100:
        chunk_size = 10
    else:
        chunk_size = 20  # 5 chunks of 20 reviews for max 100
        
    chunks = []
    for i in range(0, len(lines), chunk_size):
        chunks.append(lines[i:i + chunk_size])
    return chunks

def parse_fallback_insights(text: str) -> list[dict]:
    import re
    insights = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    for line in lines:
        if line.lower().startswith(("here is", "sure", "ok", "based on", "the analysis", "overall", "i analyzed")):
            continue
            
        cleaned = re.sub(r'^[\d\-\*\.\)\s\•]+', '', line).strip()
        if not cleaned or len(cleaned) < 15:
            continue
            
        score_match = re.search(r'(?:score|rating)[\s:]*([\d\.]+)', cleaned, re.IGNORECASE)
        score = 5.0
        if score_match:
            try:
                score = float(score_match.group(1))
            except ValueError:
                pass
                
        category_match = re.search(r'category[\s:]*([a-zA-Z]+)', cleaned, re.IGNORECASE)
        category = "Other"
        if category_match:
            category = category_match.group(1)
            
        status = score_to_status(score)
        
        cleaned_insight = re.sub(r'[\(\[\{][^\)\]\}]*(?:score|rating|category)[^\)\]\}]*[\)\]\}]', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned_insight = re.sub(r'\s+', ' ', cleaned_insight).strip()
        cleaned_insight = cleaned_insight.rstrip(",;:- ")
        
        if cleaned_insight:
            insights.append({
                "insight": cleaned_insight,
                "score": score,
                "status": status,
                "frequency": 1,
                "example_quote": "Extracted from text report.",
                "category": category.lower()
            })
            
    if not insights and text.strip():
        insights.append({
            "insight": text.strip()[:250] + "..." if len(text.strip()) > 250 else text.strip(),
            "score": 5.0,
            "status": "Worth watching",
            "frequency": 1,
            "example_quote": "Refer to raw output for details.",
            "category": "other"
        })
        
    return insights

async def ask(prompt: str) -> str:
    """
    Core function called by FastAPI `/ask` endpoint.
    Dynamically constructs a parallel review processing pipeline, runs it,
    and returns the aggregated result.
    """
    chunks = chunk_reviews(prompt)
    sub_agents = []
    
    # 1. Create Parallel Sub-agents for each chunk using the parallel model object
    for i, chunk in enumerate(chunks):
        chunk_text = "\n".join(chunk)
        sub_agent = Agent(
            name=f"ReviewResearcher_{i}",
            model=parallel_model_obj,
            instruction=f"""Analyze the following product reviews, extract key business-relevant insights, issues, or features, and output a list of distinct insights.
For each insight, include:
- The insight description
- A representative quote
- A confidence level (between 0.0 and 1.0)
- The category of the insight (e.g., quality, support, price, usability, etc.)

Reviews:
{chunk_text}""",
            output_key=f"insights_{i}"
        )
        sub_agents.append(sub_agent)
        
    parallel_reviews_team = ParallelAgent(
        name="ParallelReviewsTeam",
        sub_agents=sub_agents
    )
    
    # 2. Formulate Aggregator Prompt using the output keys from sub-agents
    input_vars = ""
    for i in range(len(chunks)):
        input_vars += f"\n**Chunk {i} Insights:**\n{{insights_{i}}}\n"
        
    aggregator_instruction = f"""Combine and aggregate all the extracted insights from the parallel review analysis chunks below:

{input_vars}

You must execute a 5-stage flow to synthesize the findings:
1. **Collect**: Gather all raw insights from all chunks.
2. **Deduplicate**: Merge highly similar or duplicate insights. If two insights are nearly identical, group them, increment the frequency count, and choose the most representative quote as the example quote.
3. **Score/Rank**: Calculate a score for each unique insight using the formula:
   score = frequency * confidence * category_weight
   Use the following category weights:
   - quality: 1.5
   - support: 1.2
   - price: 1.0
   - usability: 1.3
   - other: 1.0
   (Assume confidence is the average confidence of the merged insights, and frequency is the number of times it was mentioned or merged.)
4. **Quality Filter**: Keep all valid product feedback, positive reviews, issues, and features. Do not filter out insights unless they are completely blank, unrelated to the product, or gibberish.
5. **Format**: Output the final ranked list of insights as a valid JSON array of objects conforming to this schema:
[
  {{
    "insight": "Description of the insight",
    "score": 4.5,
    "status": "Working well",
    "frequency": 3,
    "example_quote": "Representative customer quote",
    "category": "quality"
  }}
]

Important: Your response must be ONLY a valid JSON array and nothing else. No markdown wrappers like ```json or trailing text.
"""

    aggregator_agent = Agent(
        name="AggregatorAgent",
        model=model_obj,
        instruction=aggregator_instruction,
        output_key="executive_summary"
    )
    
    # 3. Create the root Sequential Agent and InMemoryRunner
    root_agent = SequentialAgent(
        name="ReviewsAnalysisSystem",
        sub_agents=[parallel_reviews_team, aggregator_agent]
    )
    
    runner = InMemoryRunner(agent=root_agent)
    
    try:
        session = await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id="user",
        )
        
        response_text = ""
        async for event in runner.run_async(
            user_id="user",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="Run the product review aggregation pipeline.")]
            )
        ):
            # Print execution logs for parallel agents, aggregator, and root agent
            node_path = event.node_info.path if event.node_info else "unknown"
            author = event.author or "System"
            
            # Print intermediate agent trace if not partial/stream chunks
            if not event.partial:
                print(f"🔄 [Agent Event] Author: {author} | Node Path: {node_path}")
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            snippet = part.text.strip().replace('\n', ' ')
                            if len(snippet) > 100:
                                snippet = snippet[:100] + "..."
                            print(f"   ├─ Output Text: {snippet}")
                if event.output is not None:
                    print(f"   ├─ Output Data: {event.output}")

            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text
                            
        # Post-process response to extract only the JSON array if available
        import json
        cleaned_text = response_text.strip()
        if "```json" in cleaned_text:
            cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()
            
        start_idx = cleaned_text.find('[')
        end_idx = cleaned_text.rfind(']')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = cleaned_text[start_idx:end_idx + 1]
            try:
                # Validate and return parsed JSON list directly
                data = json.loads(json_str)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "score" in item:
                            try:
                                item["status"] = score_to_status(float(item["score"]))
                            except (ValueError, TypeError):
                                item["status"] = STATUS_NEEDS_ATTENTION
                    return data
            except Exception:
                pass
                
        # Fallback parsing for raw text explanation
        print("⚠️ [Parser Warning] Model returned raw text instead of a JSON array. Applying fallback text parser.")
        return parse_fallback_insights(response_text)
        
    except Exception as e:
        print(f"❌ Error communicating with local model provider: {e}")
        print(f"👉 Please ensure that your local LM Studio server is running and listening on {OPENAI_API_BASE}")
        raise e
