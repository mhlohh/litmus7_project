from fastapi import FastAPI
from models import Product
from contextlib import asynccontextmanager
from gemini_model import setup, ask
from parallel_researcher import run_parallel_research
from aggregator_engine import ThinkingAggregatorAgent
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup() 
    yield


app = FastAPI(lifespan=lifespan)


products = [
    Product(id=1, name="phone", description="budget phone", price=99.0, quantity=10),
    Product(id=2, name="Laptop", description="Asus Rog", price=2999.0, quantity=50),
    Product(id=3, name="Pen", description="Parker Pen", price=9.0, quantity=40),
    Product(id=4, name="Table", description="Round Bottom Table", price=99.0, quantity=20),
    Product(id=5, name="Television", description="4k 60 hz TV", price=499.0, quantity=30),
]


@app.get("/ask")
async def ask_ai(prompt: str):
    response = await ask(prompt)
    return {"response": response}


@app.get("/aggregate")
async def aggregate_query(query: str):
    raw_findings = await run_parallel_research(query)
    aggregator = ThinkingAggregatorAgent(raw_findings)
    report_str = await aggregator.process()
    try:
        return json.loads(report_str)
    except Exception:
        return {"error": "Failed to parse report", "raw": report_str}


@app.get("/products")
def get_all_products():
    return products


@app.get("/product/{id}")
def get_product_by_id(id: int):
    for product in products:
        if product.id == id:
            return product
    return "This product does not exist"


@app.post("/product", status_code=201)
def add_product(product: Product):
    products.append(product)
    return {"message": "Product added successfully", "product": product}


@app.put("/product/{id}")
def update_product(id: int, product: Product):
    for index, existing_product in enumerate(products):
        if existing_product.id == id:
            products[index] = product
            return {"message": "Product updated successfully", "product": product}
    return {"message": "id not found!"}


@app.delete("/product/{id}")
def delete_product(id: int):
    for product in products:
        if product.id == id:
            products.remove(product)
            return {"message": f"id: {id} product removed"}
    return {"message": "Product not found!"}


if __name__ == "__main__":
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description="Run the Sequential-over-Parallel ADK Aggregator pipeline.")
    parser.add_argument("--query", type=str, required=True, help="The query to analyze.")
    args = parser.parse_args()
    
    async def run_pipeline():
        print(f"Starting pipeline for query: '{args.query}'\n")
        print("1. Running parallel research sub-agents...")
        raw_findings = await run_parallel_research(args.query)
        for rf in raw_findings:
            print(f"   [{rf['category']}] weight={rf['weight']}: {rf['raw_text'].strip()}")
            
        print("\n2. Running Thinking Aggregator Judge...")
        aggregator = ThinkingAggregatorAgent(raw_findings)
        report_json = await aggregator.process()
        print("\n--- Final Report ---")
        print(report_json)
        
    asyncio.run(run_pipeline())


