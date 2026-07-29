from sqlalchemy.orm import Session

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