"""
Phase 4: Load clean CSVs into Supabase PostgreSQL.

Loads three files into three separate tables in this order:
  processed/clean_submissions.csv -> submissions
  processed/clean_issuers.csv     -> issuers
  processed/clean_offerings.csv   -> offerings

Connection: reads DATABASE_URL from .env
"""

import os
import pandas as pd
import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env — check your .env file")

BATCH_SIZE     = 1_000   # rows per execute_values call
CHUNK_SIZE     = 10_000  # rows read from CSV at a time
PROGRESS_EVERY = 10_000  # print progress every N rows inserted

SEP = "-" * 55

# ---------------------------------------------------------------------------
# Table configuration
#
# col_map:   {csv_column_name: postgresql_column_name}
# bool_cols: list of DB column names that need string->bool conversion
#            (CSV stores True/False as strings)
# ---------------------------------------------------------------------------
TABLES = [
    {
        "name": "submissions",
        "csv": "processed/clean_submissions.csv",
        "col_map": {
            "ACCESSIONNUMBER": "accession_number",
            "filing_date":     "filing_date",
            "filing_year":     "filing_year",
            "filing_quarter":  "filing_quarter",
            "SUBMISSIONTYPE":  "submissiontype",
        },
        "bool_cols": [],
    },
    {
        "name": "issuers",
        "csv": "processed/clean_issuers.csv",
        "col_map": {
            "ACCESSIONNUMBER":           "accession_number",
            "ENTITYNAME":                "entityname",
            "STATEORCOUNTRY":            "stateorcountry",
            "STATEORCOUNTRYDESCRIPTION": "stateorcountrydescription",
            "CITY":                      "city",
            "city_clean":                "city_clean",
        },
        "bool_cols": [],
    },
    {
        "name": "offerings",
        "csv": "processed/clean_offerings.csv",
        "col_map": {
            "ACCESSIONNUMBER":     "accession_number",
            "INDUSTRYGROUPTYPE":   "industrygrouptype",
            "INVESTMENTFUNDTYPE":  "investmentfundtype",
            "TOTALOFFERINGAMOUNT": "totalofferingamount",
            "TOTALAMOUNTSOLD":     "totalamountsold",
            "ISEQUITYTYPE":        "isequitytype",
            "ISDEBTTYPE":          "isdebttype",
            "ISAMENDMENT":         "isamendment",
            "SALE_DATE":           "sale_date",
        },
        "bool_cols": ["isequitytype", "isdebttype", "isamendment"],
    },
]


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------

# Maps every string representation of a boolean to Python bool
_BOOL_MAP = {
    "true": True, "false": False,
    "True": True, "False": False,
    True:   True, False:   False,
}


def _coerce_bool_series(series):
    """Convert a mixed string/bool series to Python bool, NaN stays NaN."""
    return series.map(_BOOL_MAP)


def prepare_chunk(df, col_map, bool_cols):
    """
    Rename columns to DB names, fix types, convert NaN/empty strings to None.
    Returns (db_column_list, list_of_row_tuples).
    """
    # Rename CSV headers -> DB column names
    df = df.rename(columns=col_map)
    db_cols = list(col_map.values())
    df = df[db_cols].copy()

    # Boolean columns: "True"/"False" string -> Python bool
    for col in bool_cols:
        if col in df.columns:
            df[col] = _coerce_bool_series(df[col])

    # Empty strings on any string/object column -> NaN so they become NULL
    for col in df.select_dtypes(include="str").columns:
        df[col] = df[col].replace("", np.nan)

    # NaN -> None  (psycopg2 maps None to SQL NULL)
    # astype(object) first so that numeric NaN doesn't survive the .where()
    df = df.astype(object).where(pd.notna(df), None)

    rows = list(df.itertuples(index=False, name=None))
    return db_cols, rows


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_table(conn, table_config):
    name      = table_config["name"]
    csv_path  = table_config["csv"]
    col_map   = table_config["col_map"]
    bool_cols = table_config["bool_cols"]

    db_cols    = list(col_map.values())
    col_list   = ", ".join(db_cols)
    insert_sql = f"INSERT INTO {name} ({col_list}) VALUES %s"

    # Truncate first so the script is safely re-runnable
    print(f"  Truncating {name}...")
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {name}")
    conn.commit()

    total_inserted = 0
    pending        = []   # accumulates rows across chunks before flushing in BATCH_SIZE

    print(f"  Streaming {csv_path} -> {name}...")

    for chunk in pd.read_csv(csv_path, chunksize=CHUNK_SIZE, low_memory=False):
        _, rows = prepare_chunk(chunk, col_map, bool_cols)
        pending.extend(rows)

        # Drain pending in BATCH_SIZE increments
        while len(pending) >= BATCH_SIZE:
            batch  = pending[:BATCH_SIZE]
            pending = pending[BATCH_SIZE:]

            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, insert_sql, batch)
            conn.commit()

            total_inserted += BATCH_SIZE
            if total_inserted % PROGRESS_EVERY == 0:
                print(f"    {total_inserted:>9,} rows inserted...")

    # Flush any remaining rows that didn't fill a full batch
    if pending:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, insert_sql, pending)
        conn.commit()
        total_inserted += len(pending)

    print(f"    {total_inserted:>9,} rows inserted  [done]")
    return total_inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Connecting to Supabase...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    print("Connected.\n")

    loaded_counts = {}

    for table in TABLES:
        print(SEP)
        print(f"TABLE: {table['name'].upper()}")
        print(SEP)
        n = load_table(conn, table)
        loaded_counts[table["name"]] = n

    # -------------------------------------------------------------------
    # Verification: query actual row counts from the database
    # -------------------------------------------------------------------
    print()
    print(SEP)
    print("VERIFICATION: Row counts in database")
    print(SEP)

    all_ok = True
    with conn.cursor() as cur:
        for table_name, expected in loaded_counts.items():
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            db_count = cur.fetchone()[0]
            match    = db_count == expected
            status   = "OK" if match else "MISMATCH"
            if not match:
                all_ok = False
            print(f"  {table_name:<15}: {db_count:>9,} rows in DB  (loaded {expected:,})  [{status}]")

    conn.close()

    print()
    if all_ok:
        print("All tables loaded and verified successfully.")
    else:
        print("WARNING: one or more row count mismatches — check output above.")


if __name__ == "__main__":
    main()
