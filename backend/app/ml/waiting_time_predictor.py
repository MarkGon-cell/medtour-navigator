import pandas as pd

from app.ml.waiting_time_model import load_model


FEATURES = [
    "VMONTH",
    "VDAYR",
    "ARRTIME",
    "AGE",
    "IMMEDR",
    "PAINSCALE",
    "LOV",
    "ADMITHOS",
    "BOARD",
]


def predict_waiting_time(features):
    model = load_model()

    if model is None:
        return {
            "prediction_available": False,
            "message": "Waiting-time prediction model is not trained yet.",
        }

    try:
        input_data = pd.DataFrame(
            [features],
            columns=FEATURES,
        )

        prediction = model.predict(input_data)[0]

        predicted_minutes = max(
            0,
            round(float(prediction))
        )

        return {
            "prediction_available": True,
            "predicted_waiting_minutes": predicted_minutes,
            "model_version": "random-forest-nhamcs-2022-v1",
        }

    except Exception as e:
        return {
            "prediction_available": False,
            "message": "Unable to generate waiting-time prediction.",
            "error": str(e),
        }