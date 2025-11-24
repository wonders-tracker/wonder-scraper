"""
Create admin user with secure password from environment variable.
Usage: ADMIN_PASSWORD=your-secure-password python scripts/create_admin.py
"""
import os
import secrets
from sqlmodel import Session, select
from app.db import engine
from app.models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def create_admin():
    # Require password from environment variable
    admin_email = os.getenv("ADMIN_EMAIL", "admin@wonderstrader.com")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        # Generate secure random password if not provided
        admin_password = secrets.token_urlsafe(32)
        print(f"No ADMIN_PASSWORD env var set. Generated secure password:")
        print(f"  {admin_password}")
        print(f"\nSave this password securely - it will not be shown again!")
        print(f"Or set ADMIN_PASSWORD environment variable before running.\n")

    with Session(engine) as session:
        statement = select(User).where(User.email == admin_email)
        user = session.exec(statement).first()

        if not user:
            print(f"Creating admin user: {admin_email}")
            hashed_password = pwd_context.hash(admin_password)
            user = User(
                email=admin_email,
                hashed_password=hashed_password,
                is_active=True,
                is_superuser=True
            )
            session.add(user)
            session.commit()
            print(f"Admin user created successfully.")
        else:
            print(f"Admin user {admin_email} already exists.")

if __name__ == "__main__":
    create_admin()

