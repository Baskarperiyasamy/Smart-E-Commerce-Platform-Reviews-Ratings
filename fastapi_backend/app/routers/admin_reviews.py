from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app import models, schemas
from app.notification_service import create_notification

router = APIRouter(prefix="/admin/reviews", tags=["Admin Reviews"])


@router.get("/", response_model=list[schemas.AdminReviewOut])
def list_reviews(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("admin", "staff")),
):
    """List all reviews for moderation."""
    reviews = (
        db.query(models.Review)
        .join(models.Product, models.Product.id == models.Review.product_id)
        .join(models.User, models.User.id == models.Review.user_id)
        .order_by(models.Review.created_at.desc())
        .all()
    )

    return [
        schemas.AdminReviewOut(
            id=r.id,
            user_id=r.user_id,
            user_name=r.user.name,
            product_id=r.product_id,
            product_name=r.product.name,
            rating=r.rating,
            comment=r.comment,
            status=r.status,
            created_at=r.created_at,
        )
        for r in reviews
    ]


@router.post("/{review_id}/approve", response_model=schemas.AdminReviewOut)
def approve_review(
    review_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("admin", "staff")),
):
    """Approve a review."""
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.status == models.ReviewStatusEnum.approved:
        raise HTTPException(status_code=400, detail="Review is already approved")

    review.status = models.ReviewStatusEnum.approved
    db.commit()
    db.refresh(review)

    create_notification(
        db,
        review.user,
        models.NotificationTypeEnum.review_approved,
        f"Your review for '{review.product.name}' has been approved.",
    )

    return schemas.AdminReviewOut(
        id=review.id,
        user_id=review.user_id,
        user_name=review.user.name,
        product_id=review.product_id,
        product_name=review.product.name,
        rating=review.rating,
        comment=review.comment,
        status=review.status,
        created_at=review.created_at,
    )


@router.post("/{review_id}/reject", response_model=schemas.AdminReviewOut)
def reject_review(
    review_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("admin", "staff")),
):
    """Reject a review."""
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.status == models.ReviewStatusEnum.rejected:
        raise HTTPException(status_code=400, detail="Review is already rejected")

    review.status = models.ReviewStatusEnum.rejected
    db.commit()
    db.refresh(review)

    create_notification(
        db,
        review.user,
        models.NotificationTypeEnum.review_rejected,
        f"Your review for '{review.product.name}' was not approved.",
    )

    return schemas.AdminReviewOut(
        id=review.id,
        user_id=review.user_id,
        user_name=review.user.name,
        product_id=review.product_id,
        product_name=review.product.name,
        rating=review.rating,
        comment=review.comment,
        status=review.status,
        created_at=review.created_at,
    )