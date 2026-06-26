"""
Inspect encounters.csv from the Synthea generation.

This is the central table for ED-twin. Before designing schema,
we need to understand column structure, dtypes, and the encounter
class distribution to confirm we have a usable ED slice.
"""

import pandas as pd
from pathlib import Path

# Path to the Synthea CSV output
DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "csv"
ENCOUNTERS_CSV = DATA_DIR / "encounters.csv"

print(f"Reading: {ENCOUNTERS_CSV}")
print(f"File exists: {ENCOUNTERS_CSV.exists()}")
print()

# Load
df = pd.read_csv(ENCOUNTERS_CSV)

# Basic shape
print("=" * 60)
print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")
print("=" * 60)
print()

# Columns and dtypes
print("Columns and dtypes:")
print("-" * 60)
print(df.dtypes.to_string())
print()

# Encounter class distribution
print("Encounter class distribution:")
print("-" * 60)
if "ENCOUNTERCLASS" in df.columns:
    class_counts = df["ENCOUNTERCLASS"].value_counts()
    class_pct = df["ENCOUNTERCLASS"].value_counts(normalize=True) * 100
    summary = pd.DataFrame({"count": class_counts, "pct": class_pct.round(2)})
    print(summary.to_string())
else:
    print("WARNING: ENCOUNTERCLASS column not found")
print()

# Null check on critical columns
print("Null counts on key columns:")
print("-" * 60)
key_cols = ["Id", "START", "STOP", "PATIENT", "ENCOUNTERCLASS", "REASONCODE"]
for col in key_cols:
    if col in df.columns:
        null_count = df[col].isnull().sum()
        print(f"  {col}: {null_count:,} nulls ({null_count/len(df)*100:.2f}%)")
print()

# Sample row
print("Sample row (first encounter):")
print("-" * 60)
print(df.iloc[0].to_string())