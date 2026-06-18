"""
Ingest Synthea CSV outputs into the ed_twin Postgres database.

Reads 8 CSV files from data/raw/csv/, applies column-name normalization
to match the schema (Synthea uses UPPERCASE, schema uses snake_case),
and bulk-loads each into the corresponding table.

Order matters: parents before children (FK constraints).
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "ed_twin")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD")

if not PG_PASSWORD:
    sys.exit("ERROR: PG_PASSWORD not set. Check .env file.")

# URL-encode the password in case of special characters
from urllib.parse import quote_plus
PG_PASSWORD_ENC = quote_plus(PG_PASSWORD)

CONN_STR = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD_ENC}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "csv"

# -----------------------------------------------------------------------------
# Table load order (respects FK dependencies)
# -----------------------------------------------------------------------------
# patients -> organizations -> providers -> encounters -> [children of encounters]
LOAD_ORDER = [
    "patients",
    "organizations",
    "providers",
    "encounters",
    "conditions",
    "medications",
    "procedures",
    "observations",
]

# -----------------------------------------------------------------------------
# Column rename maps: Synthea CSV columns -> schema columns
# -----------------------------------------------------------------------------
RENAME_MAPS = {
    "patients": {
        "Id": "id",
        "BIRTHDATE": "birthdate",
        "DEATHDATE": "deathdate",
        "SSN": "ssn",
        "DRIVERS": "drivers",
        "PASSPORT": "passport",
        "PREFIX": "prefix",
        "FIRST": "first_name",
        "LAST": "last_name",
        "SUFFIX": "suffix",
        "MAIDEN": "maiden",
        "MARITAL": "marital",
        "RACE": "race",
        "ETHNICITY": "ethnicity",
        "GENDER": "gender",
        "BIRTHPLACE": "birthplace",
        "ADDRESS": "address",
        "CITY": "city",
        "STATE": "state",
        "COUNTY": "county",
        "ZIP": "zip",
        "LAT": "lat",
        "LON": "lon",
        "HEALTHCARE_EXPENSES": "healthcare_expenses",
        "HEALTHCARE_COVERAGE": "healthcare_coverage",
        "INCOME": "income",
    },
    "organizations": {
        "Id": "id",
        "NAME": "name",
        "ADDRESS": "address",
        "CITY": "city",
        "STATE": "state",
        "ZIP": "zip",
        "LAT": "lat",
        "LON": "lon",
        "PHONE": "phone",
        "REVENUE": "revenue",
        "UTILIZATION": "utilization",
    },
    "providers": {
        "Id": "id",
        "ORGANIZATION": "organization",
        "NAME": "name",
        "GENDER": "gender",
        "SPECIALITY": "speciality",
        "ADDRESS": "address",
        "CITY": "city",
        "STATE": "state",
        "ZIP": "zip",
        "LAT": "lat",
        "LON": "lon",
        "UTILIZATION": "utilization",
    },
    "encounters": {
        "Id": "id",
        "START": "start_time",
        "STOP": "stop_time",
        "PATIENT": "patient",
        "ORGANIZATION": "organization",
        "PROVIDER": "provider",
        "PAYER": "payer",
        "ENCOUNTERCLASS": "encounter_class",
        "CODE": "code",
        "DESCRIPTION": "description",
        "BASE_ENCOUNTER_COST": "base_encounter_cost",
        "TOTAL_CLAIM_COST": "total_claim_cost",
        "PAYER_COVERAGE": "payer_coverage",
        "REASONCODE": "reason_code",
        "REASONDESCRIPTION": "reason_description",
    },
    "conditions": {
        "START": "start_date",
        "STOP": "stop_date",
        "PATIENT": "patient",
        "ENCOUNTER": "encounter",
        "CODE": "code",
        "DESCRIPTION": "description",
    },
    "medications": {
        "START": "start_time",
        "STOP": "stop_time",
        "PATIENT": "patient",
        "PAYER": "payer",
        "ENCOUNTER": "encounter",
        "CODE": "code",
        "DESCRIPTION": "description",
        "BASE_COST": "base_cost",
        "PAYER_COVERAGE": "payer_coverage",
        "DISPENSES": "dispenses",
        "TOTALCOST": "total_cost",
        "REASONCODE": "reason_code",
        "REASONDESCRIPTION": "reason_description",
    },
    "procedures": {
        "START": "start_time",
        "STOP": "stop_time",
        "PATIENT": "patient",
        "ENCOUNTER": "encounter",
        "SYSTEM": "system",
        "CODE": "code",
        "DESCRIPTION": "description",
        "BASE_COST": "base_cost",
        "REASONCODE": "reason_code",
        "REASONDESCRIPTION": "reason_description",
    },
    "observations": {
        "DATE": "date_time",
        "PATIENT": "patient",
        "ENCOUNTER": "encounter",
        "CATEGORY": "category",
        "CODE": "code",
        "DESCRIPTION": "description",
        "VALUE": "value",
        "UNITS": "units",
        "TYPE": "type",
    },
}

# -----------------------------------------------------------------------------
# Load a single table
# -----------------------------------------------------------------------------
def load_table(engine, table_name: str) -> int:
    csv_path = DATA_DIR / f"{table_name}.csv"
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} does not exist")
        return 0

    print(f"  Loading {table_name} from {csv_path.name}...", end="", flush=True)
    t0 = time.time()

    # Read
    df = pd.read_csv(csv_path)

    # Rename columns
    rename_map = RENAME_MAPS.get(table_name, {})
    df = df.rename(columns=rename_map)

    # Keep only columns that exist in schema (drop any extra Synthea columns)
    schema_cols = list(rename_map.values())
    df = df[[c for c in df.columns if c in schema_cols]]

    # Write
    rowcount = df.to_sql(
        table_name,
        engine,
        if_exists="append",
        index=False,
        chunksize=5000,
        method="multi",
    )

    elapsed = time.time() - t0
    actual_rows = len(df)
    print(f" done. {actual_rows:,} rows in {elapsed:.1f}s")
    return actual_rows


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    print(f"Connecting to: postgresql://{PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}")
    engine = create_engine(CONN_STR)

    # Verify connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        version = result.scalar()
        print(f"Connected. {version[:60]}...")
    print()

    print("Ingesting tables in dependency order:")
    print("-" * 60)
    total = 0
    grand_t0 = time.time()
    for table in LOAD_ORDER:
        n = load_table(engine, table)
        total += n
    grand_elapsed = time.time() - grand_t0
    print("-" * 60)
    print(f"TOTAL: {total:,} rows ingested across {len(LOAD_ORDER)} tables in {grand_elapsed:.1f}s")


if __name__ == "__main__":
    main()