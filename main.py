from fastapi import FastAPI, Depends
from models import Product
from  database import session, engine
import database_models
from sqlalchemy.orm import Session

app = FastAPI()

database_models.Base.metadata.create_all(bind = engine)


#get http request used for respond based on get("/") / is the request api
@app.get("/")
def greet():
    return "Welcom to Telusko Trac"

#Product List 
products = [
    Product(id = 1,name = "phone",description="budget phone",price = 99.0,quantity= 10),
    Product(id = 2,name = "Laptop",description="Asus Rog",price = 2999,quantity= 50),
    Product(id = 3,name = "Pen",description="Parker Pen",price = 9.0,quantity= 40),
    Product(id = 4,name = "Table",description="Round Bottom Table",price = 99.0,quantity= 20),
    Product(id = 5,name = "Television",description="4k 60 hz TV",price = 499.0,quantity= 30)
]

def get_db():
    db = session()
    try:
        yield db
    finally:
        db.close()

#check weather data inside the database if not exist put products in database

"""The models data type is not compatible with database which we need to 
        convert products class of models to products in database model
        So we db.add(database_models.Products()) The prodcut is from database
        model which is compatible with database . We convert the products from model
        to the Product class in data_base model which take key value pair 
        using **product.model_dump() and use as arguments in the database and mappes to 
        corresponding columns"""
        
def init_db():
    #Intialize the database
    db = session()
    count = db.query(database_models.Product).count()
    if count == 0:
        for product in products:
            db.add(database_models.Product(**product.model_dump()))
        db.commit()
    
init_db()

#get http request used for respond based on get("/") /products return all the products in list
@app.get("/products")
def get_all_products(db: Session = Depends(get_db)):
    db_products = db.query(database_models.Product).all()
    return db_products

@app.get("/product/{id}")
def get_product_by_id(id:int,db: Session = Depends(get_db)):
   db_product = db.query(database_models.Product).filter(database_models.Product.id == id).first()
   if db_product:
       return db_product
   return "This product does not exist"

@app.post("/product") #Post will try to add product in the list
def add_product(product:Product,db: Session= Depends(get_db)):
     #Append product to last of the product list
     db.add(database_models.Product(**product.model_dump()))
     db.commit()

@app.put("/product/{id}") #put request HTTP will update the existing product in list 
def update_product(id:int,product:Product):
    for i in range(len(products)):
        if products[i].id == id: #Check weather the id exist in the product list for updation
            products[i] = product
            return "Product Added Succecfully!"
    return"id not found!"

@app.delete("/product/{id}")
def delete_product(id:int):
    for product in products:
        if product.id == id:
            products.remove(product)
            return f"id: {id} product removed"
    return "Product not found!"          
            

