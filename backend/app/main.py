from fastapi import FastAPI
from app.auth.dependencies import get_current_user
from fastapi import Depends
from app.database.database import Base, engine
from app.models.user import User
from app.auth.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from app.models.hospital import Hospital
from app.api.hospitals import router as hospital_router
from app.database.database import get_db
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MedTour Navigator API"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(hospital_router)

@app.get("/")
def root():
    return {
        "message": "MedTour Navigator API Running"
    }

@app.get("/profile")
def profile(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == current_user
    ).first()

    if not user:
        return {
            "message": "User not found"
        }

    return {
        "message": "Welcome!",
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
    }