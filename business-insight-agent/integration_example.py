"""
Integration example demonstrating how an external orchestrator or aggregator
can run multiple instances of BusinessInsightAgent in parallel.
Uses ThreadPoolExecutor to analyze 5 different review chunks concurrently.
"""

import json
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from agent import BusinessInsightAgent

# Configure logging to clearly show execution thread names and concurrent timeline
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s"
)
logger = logging.getLogger(__name__)

# 5 Mock chunks of reviews representing parallel inputs from an orchestrator/aggregator
REVIEW_CHUNKS = {
    1: [
        "The battery life is stellar, easily lasts 2 days.",
        "Screen brightness is low under direct sunlight.",
        "Charging cable is too short."
    ],
    2: [
        "Excellent build quality, feels very premium in hand.",
        "The software has a few lag issues when multitasking.",
        "I love the minimalist design."
    ],
    3: [
        "Camera takes amazing night photos.",
        "The speaker is quiet and sounds muddy.",
        "Please add support for wireless charging in the next version."
    ],
    4: [
        "Customer service was incredibly helpful when replacing my unit.",
        "The fingerprint scanner fails half the time.",
        "Face unlock works flawlessly."
    ],
    5: [
        "Price is very affordable for these specs.",
        "The back cover gets scratched very easily.",
        "Shipping took longer than promised."
    ]
}

def analyze_chunk(agent: BusinessInsightAgent, chunk_id: int, reviews: List[str]) -> Dict[str, Any]:
    """
    Worker function to call the agent for a specific chunk.
    This runs inside its own worker thread.
    """
    logger.info(f"Starting concurrent analysis for Chunk {chunk_id} ({len(reviews)} reviews)...")
    result = agent.analyze_reviews(reviews, chunk_id=chunk_id)
    return result

def main() -> None:
    # 1. Instantiate a single, shared BusinessInsightAgent
    # Since the BusinessInsightAgent is thread-safe and stateless per request,
    # a single instance can be invoked concurrently across multiple threads.
    agent = BusinessInsightAgent()

    logger.info("Spawning parallel analysis tasks using ThreadPoolExecutor...")

    results = []
    # 2. Run analysis concurrently with 5 worker threads
    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="AggregatorWorker") as executor:
        # Submit tasks to the executor
        future_to_chunk = {
            executor.submit(analyze_chunk, agent, chunk_id, reviews): chunk_id
            for chunk_id, reviews in REVIEW_CHUNKS.items()
        }

        # Gather results as they complete
        for future in as_completed(future_to_chunk):
            chunk_id = future_to_chunk[future]
            try:
                data = future.result()
                results.append(data)
                logger.info(f"Chunk {chunk_id} processing completed successfully.")
            except Exception as e:
                logger.error(f"Chunk {chunk_id} generated an exception: {e}")

    # 3. Print the aggregated outcomes sorted by chunk_id
    print("\n================== CONCURRENT AGGREGATION RESULTS ==================")
    for res in sorted(results, key=lambda x: x.get("chunk_id", 0)):
        chunk_id = res.get("chunk_id")
        print(f"\n--- Chunk ID: {chunk_id} ---")
        if "error" in res:
            print(f"Status: FAILED")
            print(f"Error details: {res['error']}")
        else:
            analysis = res.get("analysis", {})
            print(f"Overall Sentiment: {analysis.get('overall_sentiment')}")
            print(f"Summary: {analysis.get('summary')}")
            print(f"Strengths: {analysis.get('strengths')}")
            print(f"Weaknesses: {analysis.get('weaknesses')}")
            print(f"Requests: {analysis.get('customer_requests')}")
            print(f"Opportunities: {analysis.get('opportunities')}")
            print(f"Risks: {analysis.get('business_risks')}")
    print("\n====================================================================\n")

if __name__ == "__main__":
    main()
