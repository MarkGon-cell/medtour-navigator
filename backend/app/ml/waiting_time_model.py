from pathlib import Path
import joblib


MODEL_PATH = Path(__file__).resolve().parent / "waiting_time_model.pkl"


def save_model(model):
    joblib.dump(model, MODEL_PATH)


def load_model():
    if not MODEL_PATH.exists():
        return None

    return joblib.load(MODEL_PATH)