from fastapi import FastAPI

from app.database.database import Base, engine
from app.models.user import User

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MedTour Navigator")

@app.get("/")
def root():
    return {"message": "Backend Connected Successfully"}