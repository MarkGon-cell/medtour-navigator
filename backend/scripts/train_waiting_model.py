import pandas as pd
import joblib

from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import GradientBoostingRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

import numpy as np


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "waiting_time"
    / "waiting_training_data.csv"
)

MODEL_DIR = BASE_DIR / "app" / "ml"

MODEL_PATH = MODEL_DIR / "waiting_time_model.pkl"


# --------------------------------------------------
# Load dataset
# --------------------------------------------------

print("Loading training dataset...")

df = pd.read_csv(DATASET_PATH)

print("Rows:", len(df))
print("Columns:", len(df.columns))


# --------------------------------------------------
# Features and target
# --------------------------------------------------

TARGET = "WAITTIME"

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


X = df[FEATURES]
y = df[TARGET]


# --------------------------------------------------
# Feature types
# --------------------------------------------------

categorical_features = [
    "VMONTH",
    "VDAYR",
    "IMMEDR",
    "PAINSCALE",
    "LOV",
    "ADMITHOS",
    "BOARD",
]

numeric_features = [
    "ARRTIME",
    "AGE",
]


# --------------------------------------------------
# Preprocessing
# --------------------------------------------------

preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="most_frequent"
                        ),
                    ),
                    (
                        "onehot",
                        OneHotEncoder(
                            handle_unknown="ignore"
                        ),
                    ),
                ]
            ),
            categorical_features,
        ),
        (
            "numeric",
            Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median"
                        ),
                    ),
                ]
            ),
            numeric_features,
        ),
    ]
)


# --------------------------------------------------
# Train/test split
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
)


print("\nTraining records:", len(X_train))
print("Testing records:", len(X_test))


# --------------------------------------------------
# Models
# --------------------------------------------------

models = {
    "Linear Regression": LinearRegression(),

    "Random Forest": RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    ),

    "Gradient Boosting": GradientBoostingRegressor(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=3,
        random_state=42,
    ),
}


# --------------------------------------------------
# Train and evaluate
# --------------------------------------------------

results = []

trained_pipelines = {}


for name, model in models.items():

    print("\n==============================")
    print(name)
    print("==============================")

    pipeline = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "model",
                model,
            ),
        ]
    )

    pipeline.fit(
        X_train,
        y_train,
    )

    predictions = pipeline.predict(
        X_test
    )

    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            predictions,
        )
    )

    r2 = r2_score(
        y_test,
        predictions,
    )

    print(
        f"MAE:  {mae:.2f} minutes"
    )

    print(
        f"RMSE: {rmse:.2f} minutes"
    )

    print(
        f"R²:   {r2:.4f}"
    )

    results.append(
        {
            "Model": name,
            "MAE": mae,
            "RMSE": rmse,
            "R2": r2,
        }
    )

    trained_pipelines[name] = pipeline


# --------------------------------------------------
# Display results
# --------------------------------------------------

results_df = pd.DataFrame(results)

print("\n\n==============================")
print("MODEL COMPARISON")
print("==============================")

print(
    results_df.to_string(
        index=False
    )
)


# --------------------------------------------------
# Select model based on lowest MAE
# --------------------------------------------------

best_model_name = results_df.loc[
    results_df["MAE"].idxmin(),
    "Model",
]

best_pipeline = trained_pipelines[
    best_model_name
]


print("\n==============================")
print("SELECTED MODEL")
print("==============================")

print(best_model_name)


# --------------------------------------------------
# Save model
# --------------------------------------------------

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

joblib.dump(
    best_pipeline,
    MODEL_PATH,
)


print("\nModel saved to:")

print(MODEL_PATH)