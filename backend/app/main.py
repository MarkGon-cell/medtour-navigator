from fastapi import FastAPI
from app.auth.dependencies import get_current_user
from fastapi import Depends
from app.database.database import Base, engine
from app.models.user import User
from app.auth.auth import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MedTour Navigator API"
)

app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "MedTour Navigator API Running"
    }

@app.get("/profile")
def profile(current_user: str = Depends(get_current_user)):
    return {
        "message": "Welcome!",
        "user": current_user
    }