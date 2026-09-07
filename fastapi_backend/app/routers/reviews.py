from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app import models, schemas

router = APIRouter(tags=["Reviews"])


@router.post("/reviews", response_model=schemas.ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Submit a review for a product (only from delivered orders)."""
    # Check product exists
    product = db.query(models.Product).filter(models.Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check user has delivered/returned order with this product
    has_eligible_order = (
        db.query(models.OrderItem)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.OrderItem.product_id == payload.product_id,
            models.Order.user_id == current_user.id,
            models.Order.order_status.in_([
                models.OrderStatusEnum.delivered,
                models.OrderStatusEnum.returned,
            ]),
        )
        .first()
    )
    if not has_eligible_order:
        raise HTTPException(
            status_code=400,
            detail="You can only review products from delivered orders",
        )

    # Check one review per user per product
    existing = (
        db.query(models.Review)
        .filter(
            models.Review.user_id == current_user.id,
            models.Review.product_id == payload.product_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You've already reviewed this product",
        )

    # Create review - AUTO APPROVED (no admin needed)
    review = models.Review(
        user_id=current_user.id,
        product_id=payload.product_id,
        rating=payload.rating,
        comment=payload.comment,
        status=models.ReviewStatusEnum.approved,  # AUTO APPROVED!
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return schemas.ReviewOut(
        id=review.id,
        user_id=review.user_id,
        user_name=current_user.name,
        product_id=review.product_id,
        rating=review.rating,
        comment=review.comment,
        status=review.status,
        created_at=review.created_at,
    )


@router.get("/products/{product_id}/reviews", response_model=schemas.ProductReviewsOut)
def get_product_reviews(product_id: str, db: Session = Depends(get_db)):
    """Get all approved reviews for a product with rating aggregation."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get ALL approved reviews (they're all auto-approved)
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