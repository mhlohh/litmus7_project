"""
Example demonstrating how the BusinessInsightAgent, registered as an ADK LLM model
('business-insight-model'), can be integrated inside google-adk Agent pipelines, 
including single Agent execution (e.g. root_agent) and multi-agent coordination
via ParallelAgent.
"""

import asyncio
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ADK_Integration")

# Import the agent module to trigger the LLMRegistry registration of 'business-insight-model'
try:
    import agent  # This registers BusinessInsightLlm to LLMRegistry
    from google.adk.agents import Agent, ParallelAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types
except ImportError as e:
    logger.error(
        f"Failed to import google-adk dependencies. Ensure you are running in "
        f"the project virtual environment. Error: {e}"
    )
    raise

# Define sample reviews to analyze
SAMPLE_REVIEWS_CHUNK_1 = [
    "The camera takes incredible photos at night, highly recommend!",
    "The customer service was slow, took 4 days to resolve my refund request.",
    "I wish it had support for wireless charging."
]

SAMPLE_REVIEWS_CHUNK_2 = [
    "Battery life is stellar, easily lasts 2 full days.",
    "The fingerprint sensor is flaky and fails to recognize my finger frequently.",
    "It gets uncomfortably hot when playing high-end games."
]


async def run_single_agent_demo() -> None:
    """
    Demonstrates using the 'business-insight-model' inside a single root agent.
    """
    logger.info("--- Starting Single ADK Agent Demo ---")

    # 1. Instantiate the ADK Agent with our registered local model
    root_agent = Agent(
        model="business-insight-model",
        name="root_business_analyst",
        description="An agent that extracts structured insights from customer reviews.",
        instruction="Analyze the reviews and return clean JSON."
    )

    # 2. Instantiate the InMemoryRunner
    runner = InMemoryRunner(agent=root_agent)
    
    # 3. Create a session for running the task
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="user_1"
    )

    # 4. Formulate the reviews input prompt
    prompt_text = "\n".join(SAMPLE_REVIEWS_CHUNK_1)
    logger.info("Sending review text to the ADK Agent...")

    # 5. Run the agent and gather the output event streams
    response_text = ""
    async for event in runner.run_async(
        user_id="user_1",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt_text)]
        )
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

    # 6. Parse and print the final JSON response
    try:
        parsed_result = json.loads(response_text)
        print("\n[ADK Root Agent Output]:")
        print(json.dumps(parsed_result, indent=4))
    except json.JSONDecodeError:
        print("\n[ADK Root Agent Output (Raw)]:")
        print(response_text)
    
    logger.info("--- Finished Single ADK Agent Demo ---\n")


async def run_parallel_agents_demo() -> None:
    """
    Demonstrates executing two sub-agents in parallel using ParallelAgent,
    both powered by 'business-insight-model'.
    """
    logger.info("--- Starting ParallelAgent Demo ---")

    # 1. Define sub-agents, each dedicated to analyzing different datasets
    analyst_a = Agent(
        model="business-insight-model",
        name="analyst_a",
        description="Analyst A responsible for reviewing chunk 1."
    )

    analyst_b = Agent(
        model="business-insight-model",
        name="analyst_b",
        description="Analyst B responsible for reviewing chunk 2."
    )

    # 2. Create the ParallelAgent orchestrator container
    parallel_orchestrator = ParallelAgent(
        name="parallel_orchestrator",
        description="Runs multiple sub-analysts concurrently.",
        sub_agents=[analyst_a, analyst_b]
    )

    # 3. Execute with the runner
    runner = InMemoryRunner(agent=parallel_orchestrator)
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="user_1"
    )

    # Prepare user query targeting the sub-agents
    query = (
        f"Analyst A: Please analyze these reviews:\n"
        f"{chr(10).join(SAMPLE_REVIEWS_CHUNK_1)}\n\n"
        f"Analyst B: Please analyze these reviews:\n"
        f"{chr(10).join(SAMPLE_REVIEWS_CHUNK_2)}"
    )

    logger.info("Executing sub-agents in parallel...")
    
    # 4. Run the parallel workspace
    async for event in runner.run_async(
        user_id="user_1",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=query)]
        )
    ):
        # Log events from sub-agents as they complete
        if event.author:
            logger.info(f"Received update from '{event.author}'")

    logger.info("--- Finished ParallelAgent Demo ---\n")


async def main() -> None:
    """
    Sequentially runs the single agent and parallel agents demos.
    """
    await run_single_agent_demo()
    await run_parallel_agents_demo()


if __name__ == "__main__":
    asyncio.run(main())
