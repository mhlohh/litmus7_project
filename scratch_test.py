import asyncio
import json
from model_provider import ask
import database

async def main():
    print("Fetching reviews from database...")
    reviews = database.get_reviews(1)
    
    # We will test with a small chunk to quickly test the parallel agent
    test_reviews = reviews[:10]
    prompt = "\n".join(test_reviews)
    
    print(f"Sending {len(test_reviews)} reviews to the parallel ADK pipeline...\n")
    
    try:
        results = await ask(prompt)
        print("\n\n=== FINAL AGGREGATED JSON OUTPUT ===")
        print(json.dumps(results, indent=2))
        print("======================================\n")
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        print("Please ensure LM Studio is running on localhost:1234 and models are loaded.")

if __name__ == "__main__":
    asyncio.run(main())
