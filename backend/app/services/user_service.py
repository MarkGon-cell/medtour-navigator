from sqlalchemy.orm import Session
from app.auth.security import verify_password
from app.models.user import User
from app.auth.security import hash_password

def create_user(db: Session, full_name: str, email: str, password: str):

    hashed = hash_password(password)

    user = User(
        full_name=full_name,
        email=email,
        password=hashed
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    if not verify_password(password, user.password):
        return None

    return user