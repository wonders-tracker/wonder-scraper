"""
Reset admin password to a known value
"""
from sqlmodel import Session, select
from app.db import engine
from app.models.user import User
from app.core import security

def reset_admin_password():
    """Reset admin@example.com password to 'admin123'"""
    with Session(engine) as session:
        # Find admin user
        admin = session.exec(select(User).where(User.email == "admin@example.com")).first()

        if not admin:
            print("❌ Admin user not found")
            return

        # Reset password
        new_password = "admin123"
        admin.hashed_password = security.get_password_hash(new_password)
        session.add(admin)
        session.commit()

        print(f"✅ Password reset for {admin.email}")
        print(f"   Email: admin@example.com")
        print(f"   Password: {new_password}")

if __name__ == "__main__":
    reset_admin_password()
