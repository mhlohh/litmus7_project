from fastapi import FastAPI
from models import Product

app = FastAPI()

products = [
    Product(id=1, name="phone", description="budget phone", price=99.0, quantity=10),
    Product(id=2, name="Laptop", description="Asus Rog", price=2999.0, quantity=50),
    Product(id=3, name="Pen", description="Parker Pen", price=9.0, quantity=40),
    Product(id=4, name="Table", description="Round Bottom Table", price=99.0, quantity=20),
    Product(id=5, name="Television", description="4k 60 hz TV", price=499.0, quantity=30),
]


@app.get("/")
def greet():
    return "Welcome to Telusko Trac"


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

