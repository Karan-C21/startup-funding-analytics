"""
Phase 3: Clean master CSVs into three separate table-ready files.

Produces:
  processed/clean_submissions.csv  -- one row per original D filing
  processed/clean_issuers.csv      -- one row per US primary issuer
  processed/clean_offerings.csv    -- one row per deal's financial details

Tables are kept separate so joins happen in SQL, not here.
Join key across all three: ACCESSIONNUMBER
"""

import pandas as pd
import numpy as np

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

SEP = "-" * 55


# ===========================================================================
# TABLE 1: SUBMISSIONS
# ===========================================================================
print(SEP)
print("TABLE 1: SUBMISSIONS")
print(SEP)

subs = pd.read_csv("processed/master_submissions.csv", low_memory=False)
print(f"Loaded:                               {len(subs):>9,} rows")

# -- Filter: original filings only, drop D/A amendments --------------------
subs = subs[subs["SUBMISSIONTYPE"] == "D"].copy()
print(f"After keeping SUBMISSIONTYPE='D':     {len(subs):>9,} rows  (-{609581 - len(subs):,} amendments)")

# -- Fix FILING_DATE: two formats in the same column -----------------------
#    Format A: "2019-04-15 14:32:00"  (pre-2020q3, datetime with timestamp)
#    Format B: "30-SEP-2020"          (2020q3 onward, DD-Mon-YYYY)
fmt_a = pd.to_datetime(subs["FILING_DATE"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
fmt_b = pd.to_datetime(subs["FILING_DATE"], format="%d-%b-%Y",           errors="coerce")
subs["filing_date"] = fmt_a.fillna(fmt_b).dt.normalize()

parsed_a = fmt_a.notna().sum()
parsed_b = fmt_b.notna().sum()
unparsed  = subs["filing_date"].isna().sum()
print(f"FILING_DATE: {parsed_a:,} via YYYY-MM-DD HH:MM:SS, "
      f"{parsed_b:,} via DD-Mon-YYYY, {unparsed} still unparseable")

if unparsed > 0:
    print("  WARNING unparseable samples:",
          subs.loc[subs["filing_date"].isna(), "FILING_DATE"].head(5).tolist())
    subs = subs[subs["filing_date"].notna()].copy()
    print(f"  After dropping unparseable:           {len(subs):>9,} rows")

# -- Derive time columns ---------------------------------------------------
subs["filing_year"]    = subs["filing_date"].dt.year.astype("Int64")
subs["filing_quarter"] = subs["filing_date"].dt.quarter.astype("Int64")

# -- Select and order final columns ----------------------------------------
subs_out = subs[["ACCESSIONNUMBER", "filing_date", "filing_year",
                  "filing_quarter", "SUBMISSIONTYPE"]].copy()

# Output date as plain YYYY-MM-DD string (not datetime object)
subs_out["filing_date"] = subs_out["filing_date"].dt.strftime("%Y-%m-%d")

subs_out.to_csv("processed/clean_submissions.csv", index=False)
print(f"Saved clean_submissions.csv:          {len(subs_out):>9,} rows, "
      f"{len(subs_out.columns)} columns")
print(f"  Columns: {list(subs_out.columns)}")


# ===========================================================================
# TABLE 2: ISSUERS
# ===========================================================================
print()
print(SEP)
print("TABLE 2: ISSUERS")
print(SEP)

iss = pd.read_csv("processed/master_issuers.csv", low_memory=False)
print(f"Loaded:                               {len(iss):>9,} rows")

# -- Filter: primary issuer per filing only --------------------------------
before = len(iss)
iss = iss[iss["IS_PRIMARYISSUER_FLAG"] == "YES"].copy()
print(f"After keeping IS_PRIMARYISSUER_FLAG:  {len(iss):>9,} rows  (-{before - len(iss):,} co-issuers)")

# Deduplicate: if a filing somehow has >1 primary row, keep first
before = len(iss)
iss = iss.drop_duplicates(subset="ACCESSIONNUMBER", keep="first")
removed = before - len(iss)
if removed:
    print(f"After dedup on ACCESSIONNUMBER:       {len(iss):>9,} rows  (-{removed} dupes)")

# -- Filter: US issuers only -----------------------------------------------
before = len(iss)
iss = iss[iss["STATEORCOUNTRY"].isin(US_STATES)].copy()
print(f"After filtering to US states only:    {len(iss):>9,} rows  (-{before - len(iss):,} foreign/non-US)")

# -- Add city_clean --------------------------------------------------------
iss["city_clean"] = (
    iss["CITY"]
    .astype(str)
    .str.strip()
    .str.upper()
    .replace({"NAN": np.nan, "": np.nan})
)

# -- Select and order final columns ----------------------------------------
iss_out = iss[["ACCESSIONNUMBER", "ENTITYNAME", "STATEORCOUNTRY",
               "STATEORCOUNTRYDESCRIPTION", "CITY", "city_clean"]].copy()

iss_out.to_csv("processed/clean_issuers.csv", index=False)
print(f"Saved clean_issuers.csv:              {len(iss_out):>9,} rows, "
      f"{len(iss_out.columns)} columns")
print(f"  Columns: {list(iss_out.columns)}")


# ===========================================================================
# TABLE 3: OFFERINGS
# ===========================================================================
print()
print(SEP)
print("TABLE 3: OFFERINGS")
print(SEP)

offs = pd.read_csv("processed/master_offerings.csv", low_memory=False)
print(f"Loaded:                               {len(offs):>9,} rows")

# -- Clean TOTALOFFERINGAMOUNT: "Indefinite" and non-numeric -> NULL --------
raw = offs["TOTALOFFERINGAMOUNT"].astype(str).str.strip()
indefinite_count = (raw.str.lower() == "indefinite").sum()
offs["TOTALOFFERINGAMOUNT"] = pd.to_numeric(
    raw.where(raw.str.lower() != "indefinite"),
    errors="coerce"
)
# Also null out the $1T sentinel in offering amount
offs.loc[offs["TOTALOFFERINGAMOUNT"] >= 1_000_000_000_000, "TOTALOFFERINGAMOUNT"] = np.nan

numeric_offer = offs["TOTALOFFERINGAMOUNT"].notna().sum()
print(f"TOTALOFFERINGAMOUNT: {indefinite_count:,} 'Indefinite' -> NULL; "
      f"{numeric_offer:,} numeric values retained")

# -- Drop $1T sentinel rows in TOTALAMOUNTSOLD -----------------------------
offs["TOTALAMOUNTSOLD"] = pd.to_numeric(offs["TOTALAMOUNTSOLD"], errors="coerce")
before = len(offs)
offs = offs[offs["TOTALAMOUNTSOLD"] < 1_000_000_000_000].copy()
print(f"After dropping TOTALAMOUNTSOLD >= $1T:{len(offs):>9,} rows  (-{before - len(offs):,} sentinel rows)")

# -- Fix boolean nulls: NULL means unchecked (False) -----------------------
offs["ISEQUITYTYPE"] = offs["ISEQUITYTYPE"].fillna(False).astype(bool)
offs["ISDEBTTYPE"]   = offs["ISDEBTTYPE"].fillna(False).astype(bool)

# -- Parse SALE_DATE to clean YYYY-MM-DD -----------------------------------
offs["SALE_DATE"] = pd.to_datetime(offs["SALE_DATE"], errors="coerce").dt.strftime("%Y-%m-%d")

# -- Select and order final columns ----------------------------------------
offs_out = offs[[
    "ACCESSIONNUMBER",
    "INDUSTRYGROUPTYPE",
    "INVESTMENTFUNDTYPE",
    "TOTALOFFERINGAMOUNT",
    "TOTALAMOUNTSOLD",
    "ISEQUITYTYPE",
    "ISDEBTTYPE",
    "ISAMENDMENT",
    "SALE_DATE",
]].copy()

offs_out.to_csv("processed/clean_offerings.csv", index=False)
print(f"Saved clean_offerings.csv:            {len(offs_out):>9,} rows, "
      f"{len(offs_out.columns)} columns")
print(f"  Columns: {list(offs_out.columns)}")


# ===========================================================================
# FINAL SUMMARY
# ===========================================================================
print()
print(SEP)
print("FINAL SUMMARY")
print(SEP)

print(f"clean_submissions.csv : {len(subs_out):>9,} rows")
print(f"clean_issuers.csv     : {len(iss_out):>9,} rows")
print(f"clean_offerings.csv   : {len(offs_out):>9,} rows")

print()
print("Join key check (ACCESSIONNUMBER present in all 3 outputs):")
print(f"  submissions : {'ACCESSIONNUMBER' in subs_out.columns}")
print(f"  issuers     : {'ACCESSIONNUMBER' in iss_out.columns}")
print(f"  offerings   : {'ACCESSIONNUMBER' in offs_out.columns}")

subs_keys = set(subs_out["ACCESSIONNUMBER"])
iss_keys  = set(iss_out["ACCESSIONNUMBER"])
offs_keys = set(offs_out["ACCESSIONNUMBER"])

print()
print("Cross-table key coverage:")
print(f"  submissions keys in offerings : "
      f"{len(subs_keys & offs_keys):,} / {len(subs_keys):,}")
print(f"  submissions keys in issuers   : "
      f"{len(subs_keys & iss_keys):,} / {len(subs_keys):,}  "
      f"(gap = foreign issuers excluded)")
print(f"  issuers keys in offerings     : "
      f"{len(iss_keys & offs_keys):,} / {len(iss_keys):,}")

print()
print("Filing year distribution (submissions):")
print(subs_out["filing_year"].value_counts().sort_index().to_string())
