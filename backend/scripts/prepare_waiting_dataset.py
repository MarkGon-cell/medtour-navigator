import pandas as pd
from pathlib import Path


DATASET_PATH = (
    Path(__file__).resolve().parent.parent
    / "datasets"
    / "waiting_time"
    / "ed2022-stata.dta"
)

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "datasets"
    / "waiting_time"
    / "waiting_training_data.csv"
)


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
    "WAITTIME",
]


print("Loading dataset...")

df = pd.read_stata(
    DATASET_PATH,
    convert_categoricals=False
)

print(f"Original rows: {len(df)}")


# --------------------------------------------------
# Select required columns
# --------------------------------------------------

missing_columns = [
    column for column in FEATURES
    if column not in df.columns
]

if missing_columns:
    print("\nMissing columns:")
    for column in missing_columns:
        print(column)

    raise SystemExit(1)


df = df[FEATURES].copy()


# --------------------------------------------------
# Convert numeric columns
# --------------------------------------------------

for column in FEATURES:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    )


# --------------------------------------------------
# Remove NHAMCS special/missing values
# --------------------------------------------------

# NHAMCS uses negative values such as -9,
# -8 and -7 for special/missing responses.
#
# These should not be interpreted as real values
# by the machine-learning models.

for column in FEATURES:
    if column != "WAITTIME":
        df[column] = df[column].where(
            df[column] >= 0
        )

df["WAITTIME"] = df["WAITTIME"].where(
    df["WAITTIME"] >= 0
)


# --------------------------------------------------
# Remove impossible / missing target values
# --------------------------------------------------

df = df.dropna(
    subset=["WAITTIME"]
)


# --------------------------------------------------
# Convert ARRIVAL TIME
# --------------------------------------------------

# ARRtime is stored as HHMM.
# Example:
# 0604 -> 6:04 AM
# 1419 -> 2:19 PM

def convert_arrival_time(value):
    if pd.isna(value):
        return None

    value = int(value)

    if value < 0:
        return None

    hours = value // 100
    minutes = value % 100

    if hours > 23 or minutes > 59:
        return None

    return hours * 60 + minutes


df["ARRTIME"] = df["ARRTIME"].apply(
    convert_arrival_time
)


# --------------------------------------------------
# Remove rows with missing predictor values
# --------------------------------------------------

df = df.dropna()


# --------------------------------------------------
# Save cleaned dataset
# --------------------------------------------------

df.to_csv(
    OUTPUT_PATH,
    index=False
)


print("\n==============================")
print("CLEANING COMPLETE")
print("==============================")

print("Final rows:", len(df))
print("Features:", list(df.columns))

print("\nWAITTIME statistics:")
print(df["WAITTIME"].describe())

print("\nSaved to:")
print(OUTPUT_PATH)