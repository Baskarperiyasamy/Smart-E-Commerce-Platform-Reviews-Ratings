from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional

from app.database import get_db
from app.dependencies import get_current_user
from app import models, schemas

router = APIRouter(tags=["Recommendations"])


# ---------------------------------------------------------------------
# Helper: Get products with rating aggregation
# ---------------------------------------------------------------------
def _get_products_with_ratings(db: Session, product_ids: List[str] = None):
    """Get products with their average rating and review count."""
    query = (
        db.query(
            models.Product,
            func.avg(models.Review.rating).label("avg_rating"),
            func.count(models.Review.id).label("review_count")
        )
        .outerjoin(models.Review, models.Review.product_id == models.Product.id)
        .filter(models.Review.status == models.ReviewStatusEnum.approved)
        .group_by(models.Product.id)
    )
    
    if product_ids:
        query = query.filter(models.Product.id.in_(product_ids))
    
    return query.all()


def _to_product_recommendation(product, avg_rating, review_count):
    """Convert product + rating data to recommendation schema."""
    return schemas.ProductRecommendation(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock,
        images=product.images,
        category=product.category,
        popularity=product.popularity,
        average_rating=round(float(avg_rating or 0), 2),
        review_count=int(review_count or 0),
    )


def _get_product_similarity_score(product_a: models.Product, product_b: models.Product) -> float:
    """Calculate similarity score between two products."""
    score = 0.0
    
    # Same category: +0.4
    if product_a.category == product_b.category:
        score += 0.4
    
    # Similar price range (within 20%): +0.3
    if product_a.price > 0 and product_b.price > 0:
        price_diff = abs(product_a.price - product_b.price) / max(product_a.price, product_b.price)
        if price_diff <= 0.2:
            score += 0.3
    
    # Similar popularity (within 2x): +0.3
    if product_a.popularity > 0 and product_b.popularity > 0:
        pop_ratio = min(product_a.popularity, product_b.popularity) / max(product_a.popularity, product_b.popularity)
        if pop_ratio >= 0.5:
            score += 0.3
    
    return round(score, 2)


# ---------------------------------------------------------------------
# API 1: GET /recommendations/{user_id} - Personalized Recommendations
# ---------------------------------------------------------------------
@router.get(
    "/recommendations/{user_id}",
    response_model=schemas.RecommendationResponse,
    summary="Get personalized recommendations for a user",
    description="""
    Get personalized recommendations based on:
    - User browsing history (cart items)
    - Past purchases (order items)
    - Product similarity
    - Most viewed items (popularity)
    - Top-rated products
    """,
)
def get_recommendations(
    user_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Get personalized recommendations for a user.
    
    This is a PUBLIC endpoint - no auth required.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. Get user's browsing history (cart items)
    cart_products = (
        db.query(models.Product)
        .join(models.Cart, models.Cart.product_id == models.Product.id)
        .filter(models.Cart.user_id == user_id)
        .all()
    )
    
    # 2. Get user's past purchases (order items)
    order_products = (
        db.query(models.Product)
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(models.Order.user_id == user_id)
        .all()
    )
    
    # 3. Get all interacted product IDs
    interacted_ids = set(p.id for p in cart_products) | set(p.id for p in order_products)
    
    # 4. Get user's preferred categories
    preferred_categories = set()
    for product in cart_products + order_products:
        if product.category:
            preferred_categories.add(product.category)
    
    # 5. Get ALL other products (exclude interacted)
    all_products_query = db.query(models.Product)
    if interacted_ids:
        all_products_query = all_products_query.filter(~models.Product.id.in_(interacted_ids))
    all_products = all_products_query.all()
    
    # 6. Score each product based on user preferences
    scored_products = []
    for product in all_products:
        score = 0.0
        
        # Category match: +2.0
        if product.category in preferred_categories:
            score += 2.0
        
        # Popularity: + popularity/100
        score += product.popularity / 100.0
        
        # Similar price to cart items: +0.5
        for cart_product in cart_products:
            if cart_product.price > 0 and product.price > 0:
                price_diff = abs(cart_product.price - product.price) / max(cart_product.price, product.price)
                if price_diff <= 0.2:
                    score += 0.5
                    break
        
        # Similar price to order items: +0.5
        for order_product in order_products:
            if order_product.price > 0 and product.price > 0:
                price_diff = abs(order_product.price - product.price) / max(order_product.price, product.price)
                if price_diff <= 0.2:
                    score += 0.5
                    break
        
        scored_products.append((product, score))
    
    # 7. Sort by score (highest first)
    scored_products.sort(key=lambda x: x[1], reverse=True)
    
    # 8. Take top N
    top_products = scored_products[:limit]
    
    # 9. Get ratings for top products
    top_ids = [p.id for p, _ in top_products]
    rating_data = {}
    if top_ids:
        rated_products = _get_products_with_ratings(db, top_ids)
        rating_data = {p.id: (avg_rating, review_count) for p, avg_rating, review_count in rated_products}
    
    # 10. Build recommendations
    recommendations = []
    for product, score in top_products:
        avg_rating, review_count = rating_data.get(product.id, (0, 0))
        rec = _to_product_recommendation(product, avg_rating, review_count)
        rec.similarity_score = round(score, 2)
        recommendations.append(rec)
    
    # 11. Fallback: If no recommendations, return trending products
    if not recommendations:
        trending_products = (
            db.query(models.Product)
            .order_by(desc(models.Product.popularity))
            .limit(limit)
            .all()
        )
        for product in trending_products:
            recommendations.append(_to_product_recommendation(product, 0, 0))
    
    # 12. Because You Bought (from past purchases)
    because_you_bought = []
    if order_products:
        order_ids = [p.id for p in order_products[:5]]
        rating_data = {}
        if order_ids:
            rated_products = _get_products_with_ratings(db, order_ids)
            rating_data = {p.id: (avg_rating, review_count) for p, avg_rating, review_count in rated_products}
        
        for product in order_products[:5]:
            avg_rating, review_count = rating_data.get(product.id, (0, 0))
            because_you_bought.append(_to_product_recommendation(product, avg_rating, review_count))
    
    return schemas.RecommendationResponse(
        user_id=user_id,
        recommendations=recommendations,
        because_you_bought=because_you_bought,
        total_recommendations=len(recommendations),
    )


# ---------------------------------------------------------------------
# API 2: GET /products/{id}/similar - Similar Products
# ---------------------------------------------------------------------
@router.get(
    "/products/{product_id}/similar",
    response_model=List[schemas.ProductRecommendation],
    summary="Get similar products",
    description="Find products similar to a given product based on category, price, and popularity.",
)
def get_similar_products(
    product_id: str,
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Get products similar to the given product."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get all other products
    other_products = (
        db.query(models.Product)
        .filter(models.Product.id != product_id)
        .all()
    )
    
    # Calculate similarity scores
    scored_products = []
    for other in other_products:
        score = _get_product_similarity_score(product, other)
        if score > 0:
            scored_products.append((other, score))
    
    # Sort by score (highest first)
    scored_products.sort(key=lambda x: x[1], reverse=True)
    
    # Get ratings for top similar products
    top_ids = [p.id for p, _ in scored_products[:limit]]
    rating_data = {}
    if top_ids:
        rated_products = _get_products_with_ratings(db, top_ids)
        rating_data = {p.id: (avg_rating, review_count) for p, avg_rating, review_count in rated_products}
    
    # Build response
    similar = []
    for other, score in scored_products[:limit]:
        avg_rating, review_count = rating_data.get(other.id, (0, 0))
        rec = _to_product_recommendation(other, avg_rating, review_count)
        rec.similarity_score = score
        similar.append(rec)
    
    return similar


# ---------------------------------------------------------------------
# API 3: GET /products/trending - Trending Products
# ---------------------------------------------------------------------
@router.get(
    "/products/trending",
    response_model=List[schemas.ProductRecommendation],
    summary="Get trending products",
    description="Get trending products based on popularity, sales, and ratings.",
)
def get_trending_products(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get trending products based on popularity and sales."""
    trending = (
        db.query(
            models.Product,
            func.coalesce(func.sum(models.OrderItem.quantity), 0).label("total_sold"),
            func.avg(models.Review.rating).label("avg_rating"),
            func.count(models.Review.id).label("review_count")
        )
        .outerjoin(models.OrderItem, models.OrderItem.product_id == models.Product.id)
        .outerjoin(models.Order, models.Order.id == models.OrderItem.order_id)
        .outerjoin(models.Review, models.Review.product_id == models.Product.id)
        .filter(
            (models.Order.payment_status == models.PaymentStatusEnum.paid) | 
            (models.Order.id.is_(None)) |
            (models.Review.status == models.ReviewStatusEnum.approved) |
            (models.Review.id.is_(None))
        )
        .group_by(models.Product.id)
        .order_by(desc(models.Product.popularity))
        .limit(limit)
        .all()
    )
    
    result = []
    for product, total_sold, avg_rating, review_count in trending:
        rec = _to_product_recommendation(product, avg_rating, review_count)
        rec.total_sold = int(total_sold or 0)
        result.append(rec)
    
    return result


# ---------------------------------------------------------------------
# API: GET /recommendations/me - Current User Recommendations (PUBLIC - NO AUTH)
# ---------------------------------------------------------------------
@router.get(
    "/recommendations/me",
    response_model=schemas.RecommendationResponse,
    summary="Get recommendations for current user",
    description="Get personalized recommendations. Works for all users (no auth required).",
)
def get_my_recommendations(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get recommendations - works for ALL users (no auth required)."""
    # Get trending products (highest popularity)
    trending_products = (
        db.query(models.Product)
        .order_by(desc(models.Product.popularity))
        .limit(limit)
        .all()
    )
    
    # Get ratings for trending products
    top_ids = [p.id for p in trending_products]
    rating_data = {}
    if top_ids:
        rated_products = _get_products_with_ratings(db, top_ids)
        rating_data = {p.id: (avg_rating, review_count) for p, avg_rating, review_count in rated_products}
    
    recommendations = []
    for product in trending_products:
        avg_rating, review_count = rating_data.get(product.id, (0, 0))
        rec = _to_product_recommendation(product, avg_rating, review_count)
        recommendations.append(rec)
    
    return schemas.RecommendationResponse(
        user_id="public",
        recommendations=recommendations,
        because_you_bought=[],
        total_recommendations=len(recommendations),
    )