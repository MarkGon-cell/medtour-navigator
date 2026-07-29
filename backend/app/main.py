from fastapi import FastAPI

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