import uuid
from datetime import datetime
from app.database import SessionLocal, engine, Base
from app import models
from app.security import hash_password

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

def seed_admin():
    db = SessionLocal()
    
    # Check if admin already exists
    admin = db.query(models.User).filter(models.User.email == "admin@example.com").first()
    if admin:
        print("✅ Admin already exists")
        return
    
    # Create admin user
    admin = models.User(
        id=str(uuid.uuid4()),
        name="Admin",
        email="admin@example.com",
        password_hash=hash_password("admin123"),
        role=models.RoleEnum.admin,
        auth_provider="local",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(admin)
    db.commit()
    db.close()
    print("✅ Admin user created: admin@example.com / admin123")

if __name__ == "__main__":
    seed_admin()