"""
Main application script to test the Business Insight Agent.
Reads sample customer reviews from a file, passes them to the agent,
and prints the structured business insights JSON.
"""

import os
import json
import logging
from typing import List
from agent import BusinessInsightAgent

# Configure logging to display information clearly during execution
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def load_reviews(file_path: str) -> List[str]:
    """
    Reads customer reviews from a text file.
    Each non-empty line in the file is treated as a single customer review.

    Args:
        file_path (str): The path to the text file containing reviews.

    Returns:
        List[str]: A list of customer review strings.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Review file not found at: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        # Extract reviews, stripping leading/trailing whitespace and ignoring blank lines
        reviews = [line.strip() for line in f if line.strip()]
    
    return reviews

def main() -> None:
    """
    Main function to execute the business insight extraction process.
    """
    # Define paths relative to this script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    reviews_path = os.path.join(script_dir, "sample_reviews.txt")

    try:
        # 1. Read reviews from sample_reviews.txt
        logger.info(f"Reading reviews from: {reviews_path}")
        reviews = load_reviews(reviews_path)
        
        if not reviews:
            logger.warning("No reviews found in sample_reviews.txt.")
            return

        logger.info(f"Loaded {len(reviews)} reviews successfully.")

        # 2. Instantiate the BusinessInsightAgent
        # Uses default base_url="http://127.0.0.1:1234/v1" and api_key="lm-studio"
        agent = BusinessInsightAgent()

        # 3. Analyze reviews using the agent
        logger.info("Invoking BusinessInsightAgent.analyze_reviews() ...")
        result = agent.analyze_reviews(reviews)

        # 4. Pretty print the JSON results
        print("\n================== ANALYSIS RESULTS ==================")
        if isinstance(result, dict):
            # If the result is a dictionary (successfully parsed JSON), pretty print it
            print(json.dumps(result, indent=4))
        else:
            # If JSON parsing failed, print the raw string content returned by the agent
            logger.warning("Agent was unable to parse response as JSON. Printing raw output.")
            print(result)
        print("======================================================\n")

    except FileNotFoundError as e:
        logger.error(e)
    except Exception as e:
        logger.error(f"Application error: {e}")

if __name__ == "__main__":
    main()