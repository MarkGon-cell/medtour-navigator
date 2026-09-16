import os
import re

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL not found in backend/.env"
    )

CSV_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "hospital_directory.csv",
)

CSV_PATH = os.path.abspath(CSV_PATH)


# ---------------------------------------------------------
# Load CSV
# ---------------------------------------------------------

print("Loading hospital dataset...")

df = pd.read_csv(
    CSV_PATH,
    low_memory=False,
)

print(
    f"Original records: {len(df)}"
)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def clean_text(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    if value.lower() in {
        "0",
        "0.0",
        "0.00",
        "nan",
        "none",
        "null",
    }:
        return None

    return value


def parse_coordinates(value):
    """
    Convert:

        19.0760, 72.8777

    into:

        (19.0760, 72.8777)

    Invalid values return None.
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    match = re.match(
        r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$",
        value,
    )

    if not match:
        return None

    latitude = float(match.group(1))
    longitude = float(match.group(2))

    # India geographic sanity check.
    #
    # These bounds are deliberately broad.
    if not (
        6 <= latitude <= 38
        and 68 <= longitude <= 98
    ):
        return None

    return latitude, longitude


def parse_integer(value):
    if pd.isna(value):
        return None

    try:
        number = float(str(value).strip())

        if number < 0:
            return None

        return int(number)

    except (ValueError, TypeError):
        return None


def parse_emergency(value):
    if pd.isna(value):
        return False

    value = str(value).strip().lower()

    return value in {
        "yes",
        "y",
        "true",
        "1",
        "available",
        "24x7",
        "24/7",
        "24 hours",
        "emergency services 24 hours",
    }


# ---------------------------------------------------------
# Parse coordinates
# ---------------------------------------------------------

print("Cleaning coordinates...")

coordinates = df[
    "Location_Coordinates"
].apply(parse_coordinates)

df["latitude"] = coordinates.apply(
    lambda x: x[0] if x else None
)

df["longitude"] = coordinates.apply(
    lambda x: x[1] if x else None
)


# ---------------------------------------------------------
# Remove records without valid coordinates
# ---------------------------------------------------------

before = len(df)

df = df.dropna(
    subset=[
        "latitude",
        "longitude",
    ]
).copy()

print(
    f"Removed {before - len(df)} records without valid coordinates."
)

print(
    f"Records with valid coordinates: {len(df)}"
)


# ---------------------------------------------------------
# Clean important columns
# ---------------------------------------------------------

df["Hospital_Name"] = df[
    "Hospital_Name"
].apply(clean_text)

df["State"] = df[
    "State"
].apply(clean_text)

df["District"] = df[
    "District"
].apply(clean_text)

df["Address_Original_First_Line"] = df[
    "Address_Original_First_Line"
].apply(clean_text)

df["Pincode"] = df[
    "Pincode"
].apply(clean_text)

df["Specialties"] = df[
    "Specialties"
].apply(clean_text)

df["Facilities"] = df[
    "Facilities"
].apply(clean_text)

df["Emergency_Services"] = df[
    "Emergency_Services"
].apply(clean_text)

df["Ambulance_Phone_No"] = df[
    "Ambulance_Phone_No"
].apply(clean_text)

df["Telephone"] = df[
    "Telephone"
].apply(clean_text)

df["Website"] = df[
    "Website"
].apply(clean_text)

df["Tariff_Range"] = df[
    "Tariff_Range"
].apply(clean_text)


# ---------------------------------------------------------
# City
# ---------------------------------------------------------

def choose_city(row):
    for column in [
        "Town",
        "Subtown",
        "Village",
        "District",
    ]:
        value = clean_text(
            row.get(column)
        )

        if value:
            return value

    return None


df["city"] = df.apply(
    choose_city,
    axis=1,
)


# ---------------------------------------------------------
# Emergency
# ---------------------------------------------------------

df["emergency_available"] = df[
    "Emergency_Services"
].apply(parse_emergency)


# ---------------------------------------------------------
# Beds
# ---------------------------------------------------------

df["total_beds"] = df[
    "Total_Num_Beds"
].apply(parse_integer)


# ---------------------------------------------------------
# Remove records without hospital names/states
# ---------------------------------------------------------

before = len(df)

df = df.dropna(
    subset=[
        "Hospital_Name",
        "State",
    ]
).copy()

print(
    f"Removed {before - len(df)} records without name/state."
)


# ---------------------------------------------------------
# Remove exact duplicate hospital records
# ---------------------------------------------------------

before = len(df)

df = df.drop_duplicates(
    subset=[
        "Hospital_Name",
        "latitude",
        "longitude",
    ]
).copy()

print(
    f"Removed {before - len(df)} duplicate records."
)

print(
    f"Final records to import: {len(df)}"
)


# ---------------------------------------------------------
# Prepare PostgreSQL dataframe
# ---------------------------------------------------------

hospital_df = pd.DataFrame({
    "name": df["Hospital_Name"],
    "city": df["city"],
    "state": df["State"],
    "district": df["District"],
    "address": df[
        "Address_Original_First_Line"
    ],
    "pincode": df["Pincode"],

    "latitude": df["latitude"],
    "longitude": df["longitude"],

    "specialties": df["Specialties"],
    "facilities": df["Facilities"],

    "emergency_available":
        df["emergency_available"],

    "emergency_services":
        df["Emergency_Services"],

    "ambulance_phone":
        df["Ambulance_Phone_No"],

    "phone": df["Telephone"],
    "website": df["Website"],

    "total_beds":
        df["total_beds"],

    "tariff_range":
        df["Tariff_Range"],
})


# ---------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------

print("Connecting to PostgreSQL...")

engine = create_engine(
    DATABASE_URL
)


# ---------------------------------------------------------
# Replace existing hospitals table
# ---------------------------------------------------------

print(
    "Replacing existing hospital table..."
)

with engine.begin() as connection:

    connection.execute(
        text(
            "DROP TABLE IF EXISTS hospitals CASCADE"
        )
    )


# ---------------------------------------------------------
# Import
# ---------------------------------------------------------

print(
    "Importing hospitals into PostgreSQL..."
)

hospital_df.to_sql(
    "hospitals",
    engine,
    if_exists="replace",
    index=True,
    index_label="id",
    chunksize=1000,
)

print(
    "Hospital import completed successfully."
)

print(
    f"Imported {len(hospital_df)} hospital records."
)