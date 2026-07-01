from fastapi import FastAPI, HTTPException, Body
from contextlib import asynccontextmanager
from model_provider import setup, ask
import database
import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize AI Core
    await setup() 
    yield

app = FastAPI(lifespan=lifespan)


# NEW database-connected review endpoints
@app.get("/db/products")
def get_database_products():
    """Returns the list of products preloaded with Amazon reviews."""
    return database.get_products()

@app.get("/db/product/{id}")
def get_database_product_by_id(id: int):
    """Returns a specific product from the reviews database."""
    prod = database.get_product(id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found in reviews database")
    return prod

@app.get("/reviews/{product_id}")
def get_product_reviews(product_id: int):
    """Returns reviews for a product in the database."""
    reviews = database.get_reviews(product_id)
    return {"product_id": product_id, "reviews_count": len(reviews), "reviews": reviews}

@app.post("/reviews/{product_id}", status_code=201)
def add_product_review(product_id: int, review: str = Body(..., embed=True)):
    """Submits a new review for a product and invalidates the cached analysis."""
    prod = database.get_product(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found in reviews database")
    database.add_review(product_id, review)
    return {"message": "Review added successfully", "reviews_count": len(database.get_reviews(product_id))}

@app.get("/analyze/{product_id}")
async def analyze_product_reviews(product_id: int):
    """Analyzes a product's reviews using the parallel ADK pipeline (supports caching)."""
    prod = database.get_product(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found in reviews database")
        
    reviews = database.get_reviews(product_id)
    if not reviews:
        return {"product_id": product_id, "cached": False, "analysis": [], "message": "No reviews found for this product"}
        
    # Check Cache
    cached_analysis = database.get_cached_analysis(product_id)
    if cached_analysis is not None:
        print(f"⚡ Cache Hit for Product {product_id}!")
        return {
            "product_id": product_id,
            "product_name": prod["name"],
            "cached": True,
            "reviews_analyzed": len(reviews),
            "analysis": cached_analysis
        }
        
    print(f"🤖 Cache Miss for Product {product_id}! Running parallel analysis pipeline...")
    # Join reviews into a single text prompt
    reviews_prompt = "\n".join([f"- {r}" for r in reviews])
    
    start_time = time.time()
    analysis_result = await ask(reviews_prompt)
    elapsed_time = time.time() - start_time
    
    # Store in cache
    database.cache_analysis(product_id, analysis_result)
    
    return {
        "product_id": product_id,
        "product_name": prod["name"],
        "cached": False,
        "execution_time_seconds": round(elapsed_time, 2),
        "reviews_analyzed": len(reviews),
        "analysis": analysis_result
    }

@app.delete("/analyze/{product_id}/cache")
def clear_product_analysis_cache(product_id: int):
    """Clears the cached review analysis for a product."""
    prod = database.get_product(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found in reviews database")
    database.clear_cache(product_id)
    return {"message": f"Cache cleared successfully for product {product_id}"}
