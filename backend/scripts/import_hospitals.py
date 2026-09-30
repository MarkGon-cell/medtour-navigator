import os
import re
import pandas as pd
from sqlalchemy import create_engine

from app.database.database import DATABASE_URL


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

CSV_PATH = os.path.join(PROJECT_ROOT, "hospital_directory.csv")


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def clean_text(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value or value.lower() in {"nan", "none", "null", "0", "0.0",}:
        return None

    return value


def clean_int(value):
    if pd.isna(value):
        return None

    try:
        value = str(value).strip()

        if not value or value.lower() in {
            "nan",
            "none",
            "null",
            "0",
            "0.0",
        }:
            return None

        # Remove commas and other common formatting characters
        value = value.replace(",", "")

        number = float(value)

        if number <= 0:
            return None

        # Sanity check for hospital directory data.
        # A single hospital having more than 10,000 beds
        # is treated as invalid directory data.
        if number > 10000:
            return None

        return int(number)

    except (ValueError, TypeError):
        return None


def parse_coordinates(value):
    """
    Convert Location_Coordinates into latitude/longitude.
    Expected formats include:
    '19.358466,72.788650'
    """

    if pd.isna(value):
        return None, None

    value = str(value).strip()

    numbers = re.findall(r"-?\d+(?:\.\d+)?", value)

    if len(numbers) < 2:
        return None, None

    try:
        latitude = float(numbers[0])
        longitude = float(numbers[1])

        # Valid approximate bounds for India
        if not (6 <= latitude <= 38):
            return None, None

        if not (68 <= longitude <= 98):
            return None, None

        return latitude, longitude

    except ValueError:
        return None, None


# ---------------------------------------------------------
# Load CSV
# ---------------------------------------------------------

print(f"Loading CSV: {CSV_PATH}")

df = pd.read_csv(CSV_PATH)

print(f"Original records: {len(df)}")


# ---------------------------------------------------------
# Parse coordinates
# ---------------------------------------------------------

coordinates = df["Location_Coordinates"].apply(parse_coordinates)

df["latitude"] = coordinates.apply(lambda x: x[0])
df["longitude"] = coordinates.apply(lambda x: x[1])


# Remove hospitals without valid coordinates
df = df.dropna(subset=["latitude", "longitude"]).copy()

print(f"Records with valid coordinates: {len(df)}")


# ---------------------------------------------------------
# Clean important fields
# ---------------------------------------------------------

df["Hospital_Name"] = df["Hospital_Name"].apply(clean_text)
df["State"] = df["State"].apply(clean_text)
df["District"] = df["District"].apply(clean_text)

df["Town"] = df["Town"].apply(clean_text)
df["Subtown"] = df["Subtown"].apply(clean_text)
df["Village"] = df["Village"].apply(clean_text)

df["Address_Original_First_Line"] = (
    df["Address_Original_First_Line"].apply(clean_text)
)

df["Pincode"] = df["Pincode"].apply(clean_text)

# Remove records without basic identity
df = df.dropna(subset=["Hospital_Name", "State"]).copy()

print(f"Records after basic validation: {len(df)}")


# ---------------------------------------------------------
# Determine city
# ---------------------------------------------------------

def get_city(row):
    for field in ["Town", "Subtown", "Village", "District"]:
        value = clean_text(row.get(field))

        if value:
            return value

    return None


df["city"] = df.apply(get_city, axis=1)


# ---------------------------------------------------------
# Emergency information
# ---------------------------------------------------------

def is_emergency_available(value):
    if pd.isna(value):
        return False

    value = str(value).strip().lower()

    if not value:
        return False

    return (
        "24 hours" in value
        or "emergency service" in value
        or value in {"yes", "available", "true", "1"}
    )


df["emergency_available"] = (
    df["Emergency_Services"]
    .apply(is_emergency_available)
)


# ---------------------------------------------------------
# Convert hospital data to database format
# ---------------------------------------------------------

hospital_df = pd.DataFrame({
    "name": df["Hospital_Name"].apply(clean_text),

    "category": df["Hospital_Category"].apply(clean_text),
    "care_type": df["Hospital_Care_Type"].apply(clean_text),
    "discipline": df["Discipline_Systems_of_Medicine"].apply(clean_text),

    "city": df["city"].apply(clean_text),
    "state": df["State"].apply(clean_text),
    "district": df["District"].apply(clean_text),

    "subdistrict": df["Subdistrict"].apply(clean_text),

    "address": df["Address_Original_First_Line"].apply(clean_text),
    "pincode": df["Pincode"].apply(clean_text),

    "latitude": df["latitude"],
    "longitude": df["longitude"],

    "specialties": df["Specialties"].apply(clean_text),
    "facilities": df["Facilities"].apply(clean_text),
    "miscellaneous_facilities": (
        df["Miscellaneous_Facilities"].apply(clean_text)
    ),

    "emergency_available": df["emergency_available"],

    "emergency_services": (
        df["Emergency_Services"].apply(clean_text)
    ),

    "emergency_phone": (
        df["Emergency_Num"].apply(clean_text)
    ),

    "ambulance_phone": (
        df["Ambulance_Phone_No"].apply(clean_text)
    ),

    "bloodbank_phone": (
        df["Bloodbank_Phone_No"].apply(clean_text)
    ),

    "phone": (
        df["Telephone"].apply(clean_text)
    ),

    "mobile": (
        df["Mobile_Number"].apply(clean_text)
    ),

    "tollfree": (
        df["Tollfree"].apply(clean_text)
    ),

    "helpline": (
        df["Helpline"].apply(clean_text)
    ),

    "website": (
        df["Website"].apply(clean_text)
    ),

    "email": (
        df["Hospital_Primary_Email_Id"].apply(clean_text)
    ),

    "total_beds": (
        df["Total_Num_Beds"].apply(clean_int)
    ),

    "private_wards": (
        df["Number_Private_Wards"].apply(clean_int)
    ),

    "economically_weaker_beds": (
        df["Num_Bed_for_Eco_Weaker_Sec"].apply(clean_int)
    ),

    "doctors": (
        df["Number_Doctor"].apply(clean_int)
    ),

    "medical_consultants": (
        df["Num_Mediconsultant_or_Expert"].apply(clean_int)
    ),

    "established_year": (
        df["Establised_Year"].apply(clean_int)
    ),

    "accreditation": (
        df["Accreditation"].apply(clean_text)
    ),

    "registration_number": (
        df["Hospital_Regis_Number"].apply(clean_text)
    ),

    "empanelment": (
        df["Empanelment_or_Collaboration_with"].apply(clean_text)
    ),

    "tariff_range": (
        df["Tariff_Range"].apply(clean_text)
    ),
})


# ---------------------------------------------------------
# Remove exact duplicates
# ---------------------------------------------------------

before_duplicates = len(hospital_df)

hospital_df = hospital_df.drop_duplicates(
    subset=["name", "latitude", "longitude"]
).reset_index(drop=True)

duplicates_removed = before_duplicates - len(hospital_df)

print(f"Removed {duplicates_removed} duplicate records.")
print(f"Final records to import: {len(hospital_df)}")


# ---------------------------------------------------------
# PostgreSQL connection
# ---------------------------------------------------------

engine = create_engine(DATABASE_URL)


# ---------------------------------------------------------
# Replace hospitals table
# ---------------------------------------------------------

print("Replacing hospitals table...")

hospital_df.to_sql(
    "hospitals",
    engine,
    if_exists="replace",
    index=True,
    index_label="id",
)


print(
    f"Successfully imported {len(hospital_df)} hospital records."
)

print("Hospital import completed successfully.")