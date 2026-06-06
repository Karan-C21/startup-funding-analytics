"""
SEC Form D Data Pipeline
Phase 2: Combine already-downloaded quarterly filings into master CSVs

The ZIPs have already been downloaded and extracted. This script:
1. Navigates the correct subfolder structure (e.g. raw-data/form-d/2024q1/2024Q1_d/)
2. Reads the .tsv files (not .txt)
3. Combines FORMDSUBMISSION, ISSUERS, and OFFERING across all quarters
4. Saves 3 master CSVs to /processed/
5. Prints a sanity check

Requirements: pip install pandas
"""

import os
import pandas as pd

PROCESSED_DIR = "processed"
RAW_DIR = os.path.join("raw-data", "form-d")

os.makedirs(PROCESSED_DIR, exist_ok=True)

# ── COMBINE INTO MASTER CSVs ──────────────────────────────────────────────────

print("Scanning downloaded quarters...")

submissions_list = []
issuers_list = []
offerings_list = []

skipped = []
loaded = []

quarter_dirs = sorted([
    d for d in os.listdir(RAW_DIR)
    if os.path.isdir(os.path.join(RAW_DIR, d))
])

print(f"Found {len(quarter_dirs)} quarter folders: {quarter_dirs[:3]}...{quarter_dirs[-3:]}\n")

for quarter in quarter_dirs:
    quarter_path = os.path.join(RAW_DIR, quarter)

    # The ZIP extracts into a subfolder like 2024Q1_d inside the quarter folder
    # Find that subfolder automatically regardless of exact casing
    subfolders = [
        f for f in os.listdir(quarter_path)
        if os.path.isdir(os.path.join(quarter_path, f))
    ]

    if not subfolders:
        print(f"  Warning: No subfolder found in {quarter}, skipping")
        skipped.append(quarter)
        continue

    data_path = os.path.join(quarter_path, subfolders[0])

    # Files are .tsv not .txt
    sub_file = os.path.join(data_path, "FORMDSUBMISSION.tsv")
    iss_file = os.path.join(data_path, "ISSUERS.tsv")
    off_file = os.path.join(data_path, "OFFERING.tsv")

    if not all(os.path.exists(f) for f in [sub_file, iss_file, off_file]):
        print(f"  Warning: Missing files in {quarter}/{subfolders[0]}, skipping")
        skipped.append(quarter)
        continue

    try:
        sub = pd.read_csv(sub_file, sep="\t", encoding="utf-8", low_memory=False)
        sub["QUARTER"] = quarter
        submissions_list.append(sub)

        iss = pd.read_csv(iss_file, sep="\t", encoding="utf-8", low_memory=False)
        iss["QUARTER"] = quarter
        issuers_list.append(iss)

        off = pd.read_csv(off_file, sep="\t", encoding="utf-8", low_memory=False)
        off["QUARTER"] = quarter
        offerings_list.append(off)

        loaded.append(quarter)
        print(f"  ✓ {quarter} ({subfolders[0]})")

    except Exception as e:
        print(f"  Warning: Error reading {quarter}: {e}")
        skipped.append(quarter)

print(f"\nLoaded {len(loaded)} quarters, skipped {len(skipped)}")

if not submissions_list:
    print("\n✗ No data loaded. Check that your raw-data/form-d folders contain extracted ZIPs.")
    exit(1)

print("\nMerging all quarters into master CSVs...")
submissions = pd.concat(submissions_list, ignore_index=True)
issuers = pd.concat(issuers_list, ignore_index=True)
offerings = pd.concat(offerings_list, ignore_index=True)

submissions.to_csv(os.path.join(PROCESSED_DIR, "master_submissions.csv"), index=False)
issuers.to_csv(os.path.join(PROCESSED_DIR, "master_issuers.csv"), index=False)
offerings.to_csv(os.path.join(PROCESSED_DIR, "master_offerings.csv"), index=False)

print(f"✓ Master CSVs saved to /processed/")

# ── SANITY CHECK ──────────────────────────────────────────────────────────────

print("\n" + "="*50)
print("SANITY CHECK")
print("="*50)

print(f"\nRow counts:")
print(f"  master_submissions : {len(submissions):>10,}")
print(f"  master_issuers     : {len(issuers):>10,}")
print(f"  master_offerings   : {len(offerings):>10,}")

print(f"\nColumns in submissions:")
print(f"  {list(submissions.columns)}")

print(f"\nDate range in submissions:")
date_col = next((c for c in submissions.columns if "DATE" in c.upper()), None)
if date_col:
    submissions[date_col] = pd.to_datetime(submissions[date_col], errors="coerce")
    print(f"  Column: {date_col}")
    print(f"  Earliest: {submissions[date_col].min()}")
    print(f"  Latest:   {submissions[date_col].max()}")
else:
    print("  No date column found - check column names above")

print(f"\nColumns in offerings:")
print(f"  {list(offerings.columns)}")

print(f"\nTop 10 industry types in offerings:")
industry_col = next((c for c in offerings.columns if "INDUSTRY" in c.upper()), None)
if industry_col:
    print(offerings[industry_col].value_counts().head(10).to_string())
else:
    print("  No industry column found - check column names above")

print(f"\nTop states in issuers:")
state_col = next((c for c in issuers.columns if "STATE" in c.upper() and "COUNTRY" in c.upper()), None)
if state_col:
    print(issuers[state_col].value_counts().head(15).to_string())
else:
    print("  No state column found - check column names above")

print("\n" + "="*50)
print("Phase 2 complete.")
print("Review row counts and column names above before moving to Phase 3.")
print("="*50)