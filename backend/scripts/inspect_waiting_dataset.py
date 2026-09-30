import pandas as pd
from pathlib import Path

DATASET_PATH = (
    Path(__file__).resolve().parent.parent
    / "datasets"
    / "waiting_time"
    / "ed2022-stata.dta"
)

print("Dataset path:")
print(DATASET_PATH)

if not DATASET_PATH.exists():
    print("\nERROR: Dataset file was not found.")
    print("Check the filename inside:")
    print(DATASET_PATH.parent)
    raise SystemExit(1)

df = pd.read_stata(
    DATASET_PATH,
    convert_categoricals=False
)

print("\n==============================")
print("DATASET INFORMATION")
print("==============================")

print("Rows:", len(df))
print("Columns:", len(df.columns))

print("\nColumns:")
for column in df.columns:
    print(column)

print("\n==============================")
print("WAIT TIME INFORMATION")
print("==============================")

if "WAITTIME" in df.columns:
    print(df["WAITTIME"].describe())
    print("\nMissing WAITTIME:")
    print(df["WAITTIME"].isna().sum())
else:
    print("WAITTIME column was not found.")

print("\n==============================")
print("FIRST 5 RECORDS")
print("==============================")

print(df.head())