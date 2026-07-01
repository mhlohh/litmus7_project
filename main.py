from fastapi import FastAPI, HTTPException, Body
from models import Product
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

# Original products memory list (untouched)
products = [
    Product(id=1, name="phone", description="budget phone", price=99.0, quantity=10),
    Product(id=2, name="Laptop", description="Asus Rog", price=2999.0, quantity=50),
    Product(id=3, name="Pen", description="Parker Pen", price=9.0, quantity=40),
    Product(id=4, name="Table", description="Round Bottom Table", price=99.0, quantity=20),
    Product(id=5, name="Television", description="4k 60 hz TV", price=499.0, quantity=30),
]

# Original endpoints (untouched)
@app.get("/ask")
async def ask_ai(prompt: str):
    response = await ask(prompt)
    return {"response": response}

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
