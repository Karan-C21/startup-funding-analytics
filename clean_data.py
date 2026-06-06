import pandas as pd
import numpy as np

US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC"
}

# ---------------------------------------------------------------------------
# 1. Load raw files
# ---------------------------------------------------------------------------
print("Loading raw files...")
subs    = pd.read_csv("processed/master_submissions.csv", low_memory=False)
issuers = pd.read_csv("processed/master_issuers.csv",    low_memory=False)
offs    = pd.read_csv("processed/master_offerings.csv",  low_memory=False)

print(f"  submissions raw:  {len(subs):>9,}")
print(f"  issuers raw:      {len(issuers):>9,}")
print(f"  offerings raw:    {len(offs):>9,}")

# ---------------------------------------------------------------------------
# 2. Filter submissions to original filings only (drop D/A amendments)
# ---------------------------------------------------------------------------
subs = subs[subs["SUBMISSIONTYPE"] == "D"].copy()
print(f"\nAfter keeping SUBMISSIONTYPE='D' only: {len(subs):,} rows")

# ---------------------------------------------------------------------------
# 3. Parse FILING_DATE — two formats in the same column
#    Format A: "2019-04-15 14:32:00"  (pre-2020q3, datetime with timestamp)
#    Format B: "30-SEP-2020"          (2020q3 onward, DD-Mon-YYYY)
# ---------------------------------------------------------------------------
fmt_a = pd.to_datetime(subs["FILING_DATE"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
fmt_b = pd.to_datetime(subs["FILING_DATE"], format="%d-%b-%Y",           errors="coerce")
subs["filing_date"] = fmt_a.fillna(fmt_b).dt.normalize()   # strip time component

still_bad = subs["filing_date"].isna().sum()
print(f"\nFILING_DATE parse: {fmt_a.notna().sum():,} via format-A, "
      f"{fmt_b.notna().sum():,} via format-B, {still_bad} still unparseable")
if still_bad:
    print("  WARNING: unparseable samples:", subs.loc[subs["filing_date"].isna(), "FILING_DATE"].head(5).tolist())

# Drop the rows that could not be parsed at all (should be 0)
subs = subs[subs["filing_date"].notna()].copy()
print(f"After dropping unparseable dates: {len(subs):,}")

# ---------------------------------------------------------------------------
# 4. Reduce issuers to primary issuer per filing only
# ---------------------------------------------------------------------------
primary = issuers[issuers["IS_PRIMARYISSUER_FLAG"] == "YES"].copy()
print(f"\nIssuers after keeping IS_PRIMARYISSUER_FLAG='YES': {len(primary):,}")

# Safety check: if a filing somehow has >1 primary, keep first occurrence only
primary = primary.drop_duplicates(subset="ACCESSIONNUMBER", keep="first")
print(f"After dedup on ACCESSIONNUMBER (should be same):    {len(primary):,}")

# ---------------------------------------------------------------------------
# 5. Join all three tables on ACCESSIONNUMBER
#    submissions → offerings (inner, both started at 609,581)
#    result      → primary issuer (left, so we keep filings even if no issuer row)
# ---------------------------------------------------------------------------
df = subs.merge(offs,    on="ACCESSIONNUMBER", how="inner")
print(f"\nAfter submissions JOIN offerings (inner): {len(df):,}")

df = df.merge(primary, on="ACCESSIONNUMBER", how="left")
print(f"After joining primary issuer (left join): {len(df):,}")

# ---------------------------------------------------------------------------
# 6. Exclude sentinel $1-trillion values in TOTALAMOUNTSOLD
#    (SEC uses 999,999,999,999 to mean "unlimited/no cap")
# ---------------------------------------------------------------------------
before = len(df)
df["TOTALAMOUNTSOLD"] = pd.to_numeric(df["TOTALAMOUNTSOLD"], errors="coerce")
df = df[df["TOTALAMOUNTSOLD"] < 1_000_000_000_000].copy()
print(f"\nAfter dropping TOTALAMOUNTSOLD >= $1T sentinel: {len(df):,}  (removed {before - len(df):,})")

# ---------------------------------------------------------------------------
# 7. Clean TOTALOFFERINGAMOUNT
#    Replace "Indefinite" and any other non-numeric strings with NaN,
#    then cast to float; also cap sentinel $1T values
# ---------------------------------------------------------------------------
raw_offer = df["TOTALOFFERINGAMOUNT"].astype(str).str.strip()
df["totalofferingamount"] = pd.to_numeric(raw_offer.where(raw_offer.str.lower() != "indefinite"), errors="coerce")
df.loc[df["totalofferingamount"] >= 1_000_000_000_000, "totalofferingamount"] = np.nan

indefinite_count = (raw_offer.str.lower() == "indefinite").sum()
print(f"\nTOTALOFFERINGAMOUNT: {indefinite_count:,} 'Indefinite' -> NULL; "
      f"{df['totalofferingamount'].notna().sum():,} numeric values retained")

# ---------------------------------------------------------------------------
# 8. Filter to US issuers only
#    Exclude foreign codes (E9=Cayman, A1, N4, X0, A6, etc.)
#    Rows where STATEORCOUNTRY is null (no issuer match) are also dropped here
# ---------------------------------------------------------------------------
before = len(df)
df = df[df["STATEORCOUNTRY"].isin(US_STATES)].copy()
print(f"\nAfter filtering to US issuers only: {len(df):,}  (removed {before - len(df):,} foreign/null rows)")

# ---------------------------------------------------------------------------
# 9. Standardize city name
# ---------------------------------------------------------------------------
df["city_clean"] = df["CITY"].astype(str).str.strip().str.upper()
# Null CITY → empty string after astype; remap to proper NaN
df["city_clean"] = df["city_clean"].replace({"NAN": np.nan, "": np.nan})

# ---------------------------------------------------------------------------
# 10. Fix boolean nulls — NULL means "not checked", i.e. False
# ---------------------------------------------------------------------------
df["ISEQUITYTYPE"] = df["ISEQUITYTYPE"].fillna(False).astype(bool)
df["ISDEBTTYPE"]   = df["ISDEBTTYPE"].fillna(False).astype(bool)

# ---------------------------------------------------------------------------
# 11. Add time dimension columns
# ---------------------------------------------------------------------------
df["filing_year"]    = df["filing_date"].dt.year.astype("Int64")
df["filing_quarter"] = df["filing_date"].dt.quarter.astype("Int64")

# ---------------------------------------------------------------------------
# 12. Rename remaining columns to lowercase for PostgreSQL hygiene
# ---------------------------------------------------------------------------
rename_map = {
    "ACCESSIONNUMBER":    "accession_number",
    "SUBMISSIONTYPE":     "submission_type",
    "ENTITYNAME":         "entity_name",
    "STATEORCOUNTRY":     "state_code",
    "STATEORCOUNTRYDESCRIPTION": "state_description",
    "CITY":               "city_raw",
    "INDUSTRYGROUPTYPE":  "industry_group",
    "INVESTMENTFUNDTYPE": "fund_type",
    "TOTALAMOUNTSOLD":    "total_amount_sold",
    "SALE_DATE":          "sale_date",
    "ISAMENDMENT":        "is_amendment",
    "ISEQUITYTYPE":       "is_equity",
    "ISDEBTTYPE":         "is_debt",
    "IS_PRIMARYISSUER_FLAG": "is_primary_issuer",
}
df = df.rename(columns=rename_map)

# ---------------------------------------------------------------------------
# 13. Select and order final columns
# ---------------------------------------------------------------------------
final_cols = [
    "accession_number",
    "filing_date",
    "filing_year",
    "filing_quarter",
    "submission_type",
    "entity_name",
    "state_code",
    "state_description",
    "city_raw",
    "city_clean",
    "industry_group",
    "fund_type",
    "totalofferingamount",
    "total_amount_sold",
    "sale_date",
    "is_amendment",
    "is_equity",
    "is_debt",
]
df = df[final_cols]

# ---------------------------------------------------------------------------
# 14. Write output
# ---------------------------------------------------------------------------
out_path = "processed/master_clean.csv"
df.to_csv(out_path, index=False)

# ---------------------------------------------------------------------------
# 15. Summary report
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("FINAL DATASET SUMMARY")
print("=" * 60)
print(f"Total rows:    {len(df):,}")
print(f"Total columns: {len(df.columns)}")
print(f"Output file:   {out_path}")

print("\nColumns:")
for col in df.columns:
    n_null = df[col].isna().sum()
    null_pct = n_null / len(df) * 100
    dtype = str(df[col].dtype)
    print(f"  {col:<25} dtype={dtype:<12} nulls={n_null:,} ({null_pct:.1f}%)")

print("\nFiling year distribution:")
print(df["filing_year"].value_counts().sort_index().to_string())

print("\nTop 10 industry groups:")
print(df["industry_group"].value_counts().head(10).to_string())

print("\nFund type breakdown:")
print(df["fund_type"].value_counts(dropna=False).to_string())

print("\nTop 10 states:")
print(df["state_code"].value_counts().head(10).to_string())

print(f"\nDone. Written to {out_path}")
