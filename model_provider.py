import os
import asyncio
from dotenv import load_dotenv
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

load_dotenv()

# Configuration parameters for LM Studio / LiteLLM local models
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "openai/qwen2.5-coder-7b-instruct-mlx")
LOCAL_PARALLEL_MODEL_NAME = os.getenv("LOCAL_PARALLEL_MODEL_NAME", LOCAL_MODEL_NAME)
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:1234/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "lm-studio")

# LiteLLM/LM Studio configuration
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

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
    
    # Dynamically select a chunk size based on input size
    if len(lines) < 10:
        chunk_size = 3
    elif len(lines) < 100:
        chunk_size = 10
    else:
        chunk_size = 100
        
    chunks = []
    for i in range(0, len(lines), chunk_size):
        chunks.append(lines[i:i + chunk_size])
    return chunks

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
4. **Quality Filter**: Remove any insights with low confidence, low frequency, or trivial/irrelevant content.
5. **Format**: Output the final ranked list of insights as a valid JSON array of objects conforming to this schema:
[
  {{
    "insight": "Description of the insight",
    "score": 4.5,
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
                return json.loads(json_str)
            except Exception:
                pass
                
        return response_text
        
    except Exception as e:
        print(f"❌ Error communicating with local model provider: {e}")
        print(f"👉 Please ensure that your local LM Studio server is running and listening on {OPENAI_API_BASE}")
        raise e
