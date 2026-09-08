import uuid
from datetime import datetime
from app.database import SessionLocal, engine, Base
from app import models

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

def seed_products():
    db = SessionLocal()
    
    products = [
        {
            "name": "iPhone 15 Pro",
            "description": "Latest Apple smartphone with A17 Pro chip",
            "price": 999.99,
            "stock": 50,
            "images": "",
            "category": "electronics",
            "popularity": 150
        },
        {
            "name": "Samsung Galaxy S24",
            "description": "Premium Android smartphone with AI features",
            "price": 899.99,
            "stock": 40,
            "images": "",
            "category": "electronics",
            "popularity": 140
        },
        {
            "name": "MacBook Air M3",
            "description": "Ultra-thin laptop with M3 chip",
            "price": 1099.99,
            "stock": 30,
            "images": "",
            "category": "electronics",
            "popularity": 120
        },
        {
            "name": "Sony WH-1000XM5",
            "description": "Industry-leading noise cancelling headphones",
            "price": 349.99,
            "stock": 60,
            "images": "",
            "category": "electronics",
            "popularity": 130
        },
        {
            "name": "Nike Air Max 270",
            "description": "Comfortable running shoes with air cushioning",
            "price": 129.99,
            "stock": 80,
            "images": "",
            "category": "fitness",
            "popularity": 110
        },
        {
            "name": "Adidas Ultraboost",
            "description": "Premium running shoes with boost technology",
            "price": 179.99,
            "stock": 70,
            "images": "",
            "category": "fitness",
            "popularity": 100
        },
        {
            "name": "Levi's Denim Jacket",
            "description": "Classic denim jacket for all seasons",
            "price": 89.99,
            "stock": 100,
            "images": "",
            "category": "fashion",
            "popularity": 90
        },
        {
            "name": "Ray-Ban Aviator Sunglasses",
            "description": "Iconic aviator sunglasses with UV protection",
            "price": 154.99,
            "stock": 45,
            "images": "",
            "category": "fashion",
            "popularity": 95
        },
        {
            "name": "Amazon Echo Dot (5th Gen)",
            "description": "Smart speaker with Alexa voice assistant",
            "price": 49.99,
            "stock": 200,
            "images": "",
            "category": "home",
            "popularity": 85
        },
        {
            "name": "Instant Pot Duo 7-in-1",
            "description": "Electric pressure cooker, slow cooker, and more",
            "price": 89.99,
            "stock": 55,
            "images": "",
            "category": "home",
            "popularity": 88
        },
        {
            "name": "Kindle Paperwhite",
            "description": "Waterproof e-reader with 300 ppi display",
            "price": 149.99,
            "stock": 75,
            "images": "",
            "category": "electronics",
            "popularity": 92
        },
        {
            "name": "Stanley Quencher Tumbler",
            "description": "40 oz insulated tumbler with handle and straw",
            "price": 45.00,
            "stock": 150,
            "images": "",
            "category": "home",
            "popularity": 120
        },
        {
            "name": "Dyson V15 Detect Vacuum",
            "description": "Powerful cordless vacuum with laser dust detection",
            "price": 749.99,
            "stock": 25,
            "images": "",
            "category": "home",
            "popularity": 115
        },
        {
            "name": "LG C3 OLED TV (65-inch)",
            "description": "4K OLED smart TV with perfect blacks",
            "price": 1599.99,
            "stock": 15,
            "images": "",
            "category": "electronics",
            "popularity": 135
        },
        {
            "name": "Yeti Rambler 30 oz Tumbler",
            "description": "Stainless steel tumbler with MagSlider lid",
            "price": 35.00,
            "stock": 120,
            "images": "",
            "category": "home",
            "popularity": 78
        },
        {
            "name": "Logitech MX Master 3S Mouse",
            "description": "Advanced wireless mouse for productivity",
            "price": 99.99,
            "stock": 65,
            "images": "",
            "category": "electronics",
            "popularity": 105
        },
        {
            "name": "Apple Watch Series 9",
            "description": "Smartwatch with health monitoring features",
            "price": 399.99,
            "stock": 35,
            "images": "",
            "category": "electronics",
            "popularity": 125
        },
        {
            "name": "Patagonia Better Sweater Fleece",
            "description": "Warm and sustainable fleece jacket",
            "price": 139.00,
            "stock": 40,
            "images": "",
            "category": "fashion",
            "popularity": 82
        },
        {
            "name": "Hydro Flask 32 oz Wide Mouth",
            "description": "Insulated water bottle with flex cap",
            "price": 44.95,
            "stock": 90,
            "images": "",
            "category": "fitness",
            "popularity": 95
        },
        {
            "name": "Bose SoundLink Flex Speaker",
            "description": "Portable Bluetooth speaker with deep bass",
            "price": 149.00,
            "stock": 50,
            "images": "",
            "category": "electronics",
            "popularity": 88
        }
    ]
    
    added_count = 0
    skipped_count = 0
    
    for p in products:
        # Check if product already exists (by name)
        existing = db.query(models.Product).filter(models.Product.name == p["name"]).first()
        if not existing:
            product = models.Product(
                id=str(uuid.uuid4()),
                name=p["name"],
                description=p["description"],
                price=p["price"],
                stock=p["stock"],
                images=p["images"],
                category=p["category"],
                popularity=p["popularity"],
                created_at=datetime.utcnow()
            )
            db.add(product)
            added_count += 1
            print(f"✅ Added: {p['name']}")
        else:
            skipped_count += 1
            print(f"⏭️  Skipped (already exists): {p['name']}")
    
    db.commit()
    db.close()
    print(f"\n📊 Summary: {added_count} products added, {skipped_count} skipped")

if __name__ == "__main__":
    seed_products()