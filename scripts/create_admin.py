from sqlmodel import Session, select
from app.db import engine
from app.models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def create_admin():
    with Session(engine) as session:
        statement = select(User).where(User.email == "admin@example.com")
        user = session.exec(statement).first()
        
        if not user:
            print("Creating default admin user...")
            hashed_password = pwd_context.hash("admin")
            user = User(email="admin@example.com", hashed_password=hashed_password, is_active=True, is_superuser=True)
            session.add(user)
            session.commit()
            print("Admin user created: admin@example.com / admin")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    create_admin()

