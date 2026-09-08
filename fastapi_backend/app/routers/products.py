from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func

from app.database import get_db
from app.dependencies import require_roles
from app import models, schemas

router = APIRouter(prefix="/products", tags=["Products"])

SORTABLE_FIELDS = {
    "price": models.Product.price,
    "popularity": models.Product.popularity,
    "name": models.Product.name,
}


def _apply_filters(query, category, min_price, max_price, in_stock, sort_by, order):
    if category:
        query = query.filter(models.Product.category == category)
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)
    if in_stock:
        query = query.filter(models.Product.stock > 0)

    if sort_by and sort_by in SORTABLE_FIELDS:
        column = SORTABLE_FIELDS[sort_by]
        query = query.order_by(desc(column) if order == "desc" else asc(column))

    return query


# ============================================================
# IMPORTANT: This route MUST be defined BEFORE /{product_id}
# ============================================================
@router.get(
    "/trending",
    response_model=list[schemas.ProductRecommendation],
    summary="Get trending products",
    description="Get trending products based on popularity, sales, and ratings.",
)
def get_trending_products(
    limit: int = Query(10, ge=1, le=50, description="Number of trending products to return"),
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
        .order_by(
            desc(models.Product.popularity),
            desc("total_sold"),
            desc("avg_rating")
        )
        .limit(limit)
        .all()
    )
    
    result = []
    for product, total_sold, avg_rating, review_count in trending:
        rec = schemas.ProductRecommendation(
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
            total_sold=int(total_sold or 0),
        )
        result.append(rec)
    
    return result


# ============================================================
# This route MUST also be defined BEFORE /{product_id}
# ============================================================
@router.get(
    "/{product_id}/reviews",
    response_model=schemas.ProductReviewsOut,
    summary="Get product reviews",
    description="Get approved reviews for a product with rating aggregation.",
)
def get_product_reviews(product_id: str, db: Session = Depends(get_db)):
    """Get approved reviews for a product with rating aggregation."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    approved = (
        db.query(models.Review)
        .filter(
            models.Review.product_id == product_id,
            models.Review.status == models.ReviewStatusEnum.approved,
        )
        .order_by(models.Review.created_at.desc())
        .all()
    )

    total_reviews = len(approved)
    average_rating = round(sum(r.rating for r in approved) / total_reviews, 2) if total_reviews else 0.0
    top_reviews = sorted(approved, key=lambda r: (r.rating, r.created_at), reverse=True)[:3]

    return schemas.ProductReviewsOut(
        product_id=product_id,
        average_rating=average_rating,
        total_reviews=total_reviews,
        top_reviews=[
            schemas.ReviewOut(
                id=r.id,
                user_id=r.user_id,
                user_name=r.user.name,
                product_id=r.product_id,
                rating=r.rating,
                comment=r.comment,
                status=r.status,
                created_at=r.created_at,
            )
            for r in top_reviews
        ],
        reviews=[
            schemas.ReviewOut(
                id=r.id,
                user_id=r.user_id,
                user_name=r.user.name,
                product_id=r.product_id,
                rating=r.rating,
                comment=r.comment,
                status=r.status,
                created_at=r.created_at,
            )
            for r in approved
        ],
    )


# ============================================================
# This route MUST also be defined BEFORE /{product_id}
# ============================================================
@router.get(
    "/{product_id}/similar",
    response_model=list[schemas.ProductRecommendation],
    summary="Get similar products",
    description="Find products similar to a given product based on category, price, and popularity.",
)
def get_similar_products(
    product_id: str,
    limit: int = Query(6, ge=1, le=20, description="Number of similar products to return"),
    db: Session = Depends(get_db),
):
    """Get products similar to the given product."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    other_products = (
        db.query(models.Product)
        .filter(models.Product.id != product_id)
        .all()
    )
    
    scored_products = []
    for other in other_products:
        score = 0.0
        # Same category: +0.4
        if product.category == other.category:
            score += 0.4
        # Similar price range (within 20%): +0.3
        if product.price > 0 and other.price > 0:
            price_diff = abs(product.price - other.price) / max(product.price, other.price)
            if price_diff <= 0.2:
                score += 0.3
        # Similar popularity (within 2x): +0.3
        if product.popularity > 0 and other.popularity > 0:
            pop_ratio = min(product.popularity, other.popularity) / max(product.popularity, other.popularity)
            if pop_ratio >= 0.5:
                score += 0.3
        
        if score > 0:
            scored_products.append((other, score))
    
    scored_products.sort(key=lambda x: x[1], reverse=True)
    
    top_ids = [p.id for p, _ in scored_products[:limit]]
    rating_data = {}
    if top_ids:
        rated_products = (
            db.query(
                models.Product,
                func.avg(models.Review.rating).label("avg_rating"),
                func.count(models.Review.id).label("review_count")
            )
            .outerjoin(models.Review, models.Review.product_id == models.Product.id)
            .filter(
                models.Review.status == models.ReviewStatusEnum.approved,
                models.Product.id.in_(top_ids),
            )
            .group_by(models.Product.id)
            .all()
        )
        rating_data = {p.id: (avg_rating, review_count) for p, avg_rating, review_count in rated_products}
    
    similar = []
    for other, score in scored_products[:limit]:
        avg_rating, review_count = rating_data.get(other.id, (0, 0))
        rec = schemas.ProductRecommendation(
            id=other.id,
            name=other.name,
            description=other.description,
            price=other.price,
            stock=other.stock,
            images=other.images,
            category=other.category,
            popularity=other.popularity,
            average_rating=round(float(avg_rating or 0), 2),
            review_count=int(review_count or 0),
            similarity_score=round(score, 2),
        )
        similar.append(rec)
    
    return similar


# ============================================================
# Standard CRUD routes (MUST be after /trending and /{id}/similar)
# ============================================================

@router.get("/", response_model=list[schemas.ProductOut])
def list_products(
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "asc",
    db: Session = Depends(get_db),
):
    query = _apply_filters(db.query(models.Product), category, min_price, max_price, in_stock, sort_by, order)
    return query.all()


@router.get("/category/{category}", response_model=list[schemas.ProductOut])
def list_products_by_category(
    category: str,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "asc",
    db: Session = Depends(get_db),
):
    query = _apply_filters(db.query(models.Product), category, min_price, max_price, in_stock, sort_by, order)
    return query.all()


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("admin")),
):
    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: str,
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("admin")),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in payload.model_dump().items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("admin")),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()
    return None