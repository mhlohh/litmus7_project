import os
import ssl
import urllib.request
import pandas as pd
import sqlite3
import json

# Disable SSL verification for urllib requests (needed on macOS in some environments)
ssl._create_default_https_context = ssl._create_unverified_context

# Database Connection Settings
DB_FILE = "data/litmus7.db"

# Pre-defined Products
DEFAULT_PRODUCTS = [
    {"id": 1, "asin": "B00F2SKPIM", "name": "Samsung Galaxy S10", "description": "Flagship Samsung smartphone with Dynamic AMOLED screen.", "price": 899.0, "quantity": 15},
    {"id": 2, "asin": "B00836Y6B2", "name": "iPhone XR", "description": "Liquid Retina display, Face ID, and advanced camera system.", "price": 749.0, "quantity": 25},
    {"id": 3, "asin": "B07FZH9BGV", "name": "OnePlus 7 Pro", "description": "Fluid AMOLED display with 90Hz refresh rate and triple camera.", "price": 669.0, "quantity": 20}
]

def get_connection():
    """Returns a new SQLite3 connection with row factory configured to Row."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """
    Creates SQLite3 tables and populates them with initial products and Amazon reviews.
    Augments the dataset to 1000+ reviews per product to simulate scale.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Create Schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            asin TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            price REAL,
            quantity INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_cache (
            product_id INTEGER PRIMARY KEY,
            analysis TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.commit()
    
    # Check if database is already populated
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] > 0:
        print("💾 Database already populated in SQLite. Skipping initialization.")
        conn.close()
        return
        
    print("🚀 Initializing database with products and reviews...")
    
    # Populate Default Products
    for p in DEFAULT_PRODUCTS:
        cursor.execute(
            "INSERT INTO products (id, asin, name, description, price, quantity) VALUES (?, ?, ?, ?, ?, ?)",
            (p["id"], p["asin"], p["name"], p["description"], p["price"], p["quantity"])
        )
    conn.commit()

    local_cache_dir = "data"
    local_cache_file = os.path.join(local_cache_dir, "reviews_dataset.csv")
    dataset_url = "https://raw.githubusercontent.com/vamshikallem/Text-Analytics-on-Amazon-Cell-Reviews-and-Ratings/master/20191226-reviews.csv"
    
    df = None
    
    # Check if we have a local cache file
    if os.path.exists(local_cache_file):
        print(f"📖 Loading Amazon reviews dataset from local cache: {local_cache_file}...")
        try:
            df = pd.read_csv(local_cache_file)
            print(f"✅ Loaded dataset locally containing {len(df)} rows.")
        except Exception as e:
            print(f"⚠️ Error reading local cache: {e}. Will attempt download.")
            
    if df is None:
        print(f"📥 Downloading Amazon reviews dataset from {dataset_url}...")
        try:
            df = pd.read_csv(dataset_url)
            print(f"✅ Loaded dataset containing {len(df)} rows.")
            
            # Save to local cache
            os.makedirs(local_cache_dir, exist_ok=True)
            df.to_csv(local_cache_file, index=False)
            print(f"💾 Saved dataset to local cache file: {local_cache_file}")
        except Exception as e:
            print(f"❌ Error downloading dataset: {e}")
            
    # Populate products and reviews
    try:
        if df is None:
            raise ValueError("No dataset loaded.")
            
        for product in DEFAULT_PRODUCTS:
            product_id = product["id"]
            asin = product["asin"]
            
            # Filter reviews for this product's ASIN
            prod_reviews = df[df["asin"] == asin]["body"].dropna().tolist()
            print(f"🔍 Found {len(prod_reviews)} real reviews for {product['name']} (ASIN: {asin})")
            
            # Ensure we have 1000+ reviews by duplicating/augmenting
            target_count = 1005
            while len(prod_reviews) < target_count:
                shortage = target_count - len(prod_reviews)
                prod_reviews.extend(prod_reviews[:shortage])
                
            prod_reviews = prod_reviews[:target_count]
            print(f"📈 Scaled {product['name']} reviews count to {len(prod_reviews)}")
            
            # Save reviews
            cursor.executemany(
                "INSERT INTO reviews (product_id, body) VALUES (?, ?)",
                [(product_id, body) for body in prod_reviews]
            )
            print(f"💾 Saved {len(prod_reviews)} reviews for '{product['name']}' to database.")
            
        conn.commit()
        print("🎉 Database Initialization Completed Successfully!")
    except Exception as e:
        print(f"❌ Error populating dataset: {e}")
        # Fallback to local stub reviews if error occurs
        print("👉 Populating database with stub local reviews...")
        for product in DEFAULT_PRODUCTS:
            product_id = product["id"]
            stub_reviews = [
                f"Amazing {product['name']}! Best purchase I've made all year.",
                f"The {product['name']} has some issues with battery life but performs well.",
                f"Terrible quality, screen broke instantly.",
                f"Great value for money, highly recommend the {product['name']}."
            ] * 260
            stub_reviews = stub_reviews[:1005]
            
            cursor.executemany(
                "INSERT INTO reviews (product_id, body) VALUES (?, ?)",
                [(product_id, body) for body in stub_reviews]
            )
            print(f"💾 Saved {len(stub_reviews)} stub reviews for '{product['name']}' to database.")
        conn.commit()
    finally:
        conn.close()

# Run initialization upon import
initialize_database()

# Database helper functions

def get_products() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, asin, name, description, price, quantity FROM products")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_product(product_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, asin, name, description, price, quantity FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_reviews(product_id: int) -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT body FROM reviews WHERE product_id = ?", (product_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r["body"] for r in rows]

def add_review(product_id: int, review_text: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reviews (product_id, body) VALUES (?, ?)", (product_id, review_text))
    conn.commit()
    conn.close()
    # Invalidate the cache since database has a new review
    clear_cache(product_id)

def get_cached_analysis(product_id: int) -> list[dict] | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT analysis FROM analysis_cache WHERE product_id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["analysis"])
        except Exception:
            return None
    return None

def cache_analysis(product_id: int, analysis: list[dict]):
    conn = get_connection()
    cursor = conn.cursor()
    analysis_str = json.dumps(analysis)
    cursor.execute(
        "INSERT OR REPLACE INTO analysis_cache (product_id, analysis) VALUES (?, ?)",
        (product_id, analysis_str)
    )
    conn.commit()
    conn.close()

def clear_cache(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM analysis_cache WHERE product_id = ?", (product_id,))
    conn.commit()
    conn.close()
