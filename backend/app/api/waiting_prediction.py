from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ml.waiting_time_predictor import predict_waiting_time


router = APIRouter(
    prefix="/waiting-time",
    tags=["Waiting Time Prediction"],
)


class WaitingTimeRequest(BaseModel):
    vmonth: int
    vdayr: int
    arrtime: int
    age: int
    immedr: int
    painscale: int
    lov: int
    admithos: int
    board: int


@router.post("/predict")
def predict_waiting(request: WaitingTimeRequest):

    features = [
        request.vmonth,
        request.vdayr,
        request.arrtime,
        request.age,
        request.immedr,
        request.painscale,
        request.lov,
        request.admithos,
        request.board,
    ]

    result = predict_waiting_time(features)

    if not result["prediction_available"]:
        raise HTTPException(
            status_code=503,
            detail=result["message"],
        )

    return result