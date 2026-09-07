from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401
from app import ws_manager
from app.routers import (
    auth, products, cart, checkout, orders, returns,
    admin_returns, reviews, admin_reviews, webhooks, notifications, ws
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart E-Commerce Platform - FastAPI Backend",
    description="Complete e-commerce platform with reviews & ratings system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def capture_event_loop():
    import asyncio
    ws_manager.main_loop = asyncio.get_event_loop()


# Include all routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(checkout.router)
app.include_router(orders.router)
app.include_router(returns.router)
app.include_router(reviews.router)           # NEW
app.include_router(admin_reviews.router)     # NEW
app.include_router(admin_returns.router)
app.include_router(webhooks.router)
app.include_router(notifications.router)
app.include_router(ws.router)


@app.get("/")
def root():
    return {
        "status": "ok", 
        "service": "fastapi_backend", 
        "docs": "/docs",
        "version": "1.0.0",
        "reviews_enabled": True
    }