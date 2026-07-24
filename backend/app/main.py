from fastapi import FastAPI

app = FastAPI(
    title="MedTour Navigator API",
    version="1.0.0"
)

@app.get("/")
def root():
    return {"message": "MedTour Navigator API is running!"}