import asyncio
import re
import os
from typing import List, Dict, Any
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from lm_studio_llm import LMStudioLlm

# Initialize our custom LM Studio LLM
lm_studio_model = LMStudioLlm(model=os.getenv("LM_STUDIO_MODEL_NAME", "Qwen2.5-Coder-7B-Instruct-GGUF"))

# Define specialized instructions for each sub-agent
SENTIMENT_INSTRUCTIONS = (
    "You are a Sentiment Analyst. Analyze the sentiment of the user query.\n"
    "Identify if the sentiment is Positive, Negative, or Neutral, and specify any emotion.\n"
    "Keep your analysis concise. At the end of your response, write exactly:\n"
    "Confidence: <float_value_between_0_and_1>"
)

INTENT_INSTRUCTIONS = (
    "You are an Intent Analyst. Identify the user's primary intent from the query\n"
    "(e.g., cancel subscription, pause service, ask product details, report issue).\n"
    "Keep your analysis concise. At the end of your response, write exactly:\n"
    "Confidence: <float_value_between_0_and_1>"
)

METADATA_INSTRUCTIONS = (
    "You are a Metadata Auditor. Categorize the query type (e.g. system_status, user_action) "
    "and check if there are system flags or entities.\n"
    "Keep your analysis concise. At the end of your response, write exactly:\n"
    "Confidence: <float_value_between_0_and_1>"
)

# Instantiate the agents
sentiment_agent = Agent(
    model=lm_studio_model,
    name="sentiment_analyst",
    description="Analyzes the sentiment of a query.",
    instruction=SENTIMENT_INSTRUCTIONS
)

intent_agent = Agent(
    model=lm_studio_model,
    name="intent_analyst",
    description="Identifies user intent.",
    instruction=INTENT_INSTRUCTIONS
)

metadata_agent = Agent(
    model=lm_studio_model,
    name="metadata_auditor",
    description="Audits query metadata.",
    instruction=METADATA_INSTRUCTIONS
)

async def execute_sub_agent(agent: Agent, category: str, query: str) -> Dict[str, Any]:
    """
    Executes a single ADK Agent using InMemoryRunner, parses the response,
    and returns its category, raw output, and parsed/calculated confidence weight.
    """
    runner = InMemoryRunner(agent=agent)
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="user",
    )
    
    raw_text = ""
    try:
        async for event in runner.run_async(
            user_id="user",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=query)]
            )
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            raw_text += part.text
    except Exception as e:
        raw_text = f"[ERROR] Agent execution failed: {str(e)}"
    
    # Parse the confidence weight from the output (e.g., "Confidence: 0.95")
    weight = 0.80  # Default confidence weight
    match = re.search(r"Confidence:\s*([0-9.]+)", raw_text, re.IGNORECASE)
    if match:
        try:
            parsed_weight = float(match.group(1))
            if 0.0 <= parsed_weight <= 1.0:
                weight = parsed_weight
        except ValueError:
            pass

    return {
        "category": category,
        "raw_text": raw_text,
        "weight": weight
    }

async def run_parallel_research(query: str) -> List[Dict[str, Any]]:
    """
    Spawns concurrent sub-agents to analyze the single query.
    """
    tasks = [
        execute_sub_agent(sentiment_agent, "sentiment", query),
        execute_sub_agent(intent_agent, "user_intent", query),
        execute_sub_agent(metadata_agent, "system_status", query)
    ]
    return await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Test block
    async def test_main():
        test_query = "The service is down! I want to pause my subscription right now."
        print(f"Running parallel research for query: '{test_query}'\n")
        results = await run_parallel_research(test_query)
        for res in results:
            print(f"--- Category: {res['category']} (Weight: {res['weight']}) ---")
            print(res["raw_text"])
            print()
            
    asyncio.run(test_main())
