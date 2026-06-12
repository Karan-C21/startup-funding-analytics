# Startup Funding Analytics
**PostgreSQL · Tableau Public · SEC EDGAR**

## What This Is

An end-to-end SQL analytics project analyzing US private capital markets using SEC EDGAR Form D filings — the legally required disclosures every US company must submit within 15 days of raising private capital. This is the authoritative primary source for private fundraising activity in the United States, covering venture capital, private equity, hedge funds, real estate, and operating companies across all 50 states.

The project was built to demonstrate production-level SQL skills (CTEs, window functions, multi-table joins, rolling averages, NTILE) on a real financial dataset with genuine business questions — not a tutorial dataset.

## Data Source

**SEC EDGAR Form D Data Sets**
- URL: https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets
- Coverage: 2012 Q1 through 2026 Q1 (50 quarterly files)
- Final dataset: 374,388 original filings after cleaning

Every US company raising private capital from investors is legally required to file Form D with the SEC. This makes the dataset complete and authoritative — not a sample, not a scrape, not a Kaggle upload.

## Database Schema

Three normalized PostgreSQL tables hosted on Supabase, joined on `accession_number`:

| Table | Rows | Description |
|---|---|---|
| `submissions` | 374,388 | One row per original filing. Contains filing date, year, quarter. Amendments excluded to avoid double-counting. |
| `issuers` | 531,660 | One row per company. Contains entity name, state, city. Filtered to US issuers only. |
| `offerings` | 609,581 | One row per deal's financial details. Contains industry, fund type, amount raised, offering structure. |

**Why three tables instead of one flat file:** The joins happen in SQL, not Python. Every business question requires joining at least two tables, which demonstrates the join patterns that show up in DA screening tests.

## Data Pipeline

**Step 1 — Download:** `setup_data.py` downloads all quarterly ZIP files directly from SEC EDGAR using the required User-Agent header.

**Step 2 — Clean:** A separate cleaning script produces three normalized CSVs with the following decisions applied:
- Amendments (SUBMISSIONTYPE = D/A) excluded to count unique capital raises only
- Foreign issuers excluded, keeping US-only filings
- TOTALOFFERINGAMOUNT nullified where filed as "Indefinite"
- TOTALAMOUNTSOLD used as the primary dollar metric (0% null, always numeric)
- Dual date formats unified to YYYY-MM-DD
- Sentinel values ($1T+ offerings) removed

**Step 3 — Load:** `load_to_supabase.py` loads all three CSVs into PostgreSQL on Supabase using psycopg2 with batch inserts.

## Business Questions and Key Findings

**Q1: How did the 2021 venture boom and 2022-2024 contraction reshape US private capital?**

The 2021 boom was historic — $1.13 trillion raised in a single year, nearly double any prior year, with 42,494 deals compared to 28,126 in 2020. The contraction was broad and severe. Average annual capital raised in 2022-2024 dropped more than 40% across most industries. Pooled Investment Funds (hedge funds, PE, VC) dominated both the boom and the bust, accounting for 61% of all capital raised in 2021. The industries that showed modest growth during the contraction — insurance, hospitals, restaurants — reflect post-COVID recovery rather than genuine capital rotation.

**Q2: How has the typical deal size changed by industry since 2019?**

Biotech and Pharma median deal sizes nearly doubled during the 2021 boom (Biotech: $2.16M to $4.16M, Pharma: $2.49M to $4.30M) before contracting sharply. Other Energy is the outlier — median deal size grew steadily from $0.50M in 2019 to $1.77M in 2025 with no crash, reflecting consistent investment in clean energy infrastructure. Other Banking and Financial Services (fintech) had the sharpest contraction — median deal size fell 90% from $2.00M in 2021 to $0.20M in 2023.

**Q3: Which states have emerged as new private capital hubs since 2019?**

Washington state is the strongest genuine growth story at 104% deal count growth, driven by the Seattle tech ecosystem. Florida (+79%) and Texas (+32%) confirm the post-COVID geographic migration narrative. California is declining at -8.1% and Massachusetts at -12.7%, suggesting the traditional coastal hubs are losing ground. Delaware's 1,360% growth is a data artifact — most US companies incorporate in Delaware for legal reasons, inflating its filing count without reflecting genuine economic activity. Utah's Silicon Slopes narrative did not hold up — down 38% from 2019 to 2025 despite a 128% spike in 2021.

**Q4: Is private capital becoming more concentrated in fewer deals?**

The top 10% of deals by size have consistently captured 85-89% of all private capital every single year from 2019 to 2025. Concentration slightly increased during the 2021 boom (88.7%) and remained elevated through the contraction (89.0% in 2023) before beginning to normalize in 2024-2025 (85-86%). This suggests the boom disproportionately benefited the largest deals while smaller raises grew more slowly, and the contraction hit smaller deals harder before gradually normalizing.

**Q5: Has the equity vs debt mix shifted since interest rates rose in 2022?**

Among original Form D filings from operating companies (excluding pooled investment funds), debt-structured offerings declined from 15.8% of all raises in 2019-2020 to 10.7% in 2025. This contradicts the mainstream narrative that companies shifted toward debt financing after interest rates rose in 2022. The 3-year rolling average confirms this is a structural decline, not year-to-year noise. Note: this measures initial filing intent from original filings only — amendments which may reflect updated offering structures are excluded by design.

## SQL Techniques Demonstrated

| Technique | Query |
|---|---|
| Multi-table JOINs | All queries |
| 3-table JOIN (issuers + submissions + offerings) | Q3 |
| CTEs (chained) | Q1, Q2, Q3, Q4, Q5 |
| LAG window function | Q2 |
| RANK window function | Q3 |
| NTILE | Q4 |
| PERCENTILE_CONT | Q2 |
| CASE WHEN inside aggregations | Q1, Q5 |
| Rolling averages (ROWS BETWEEN) | Q5 |
| NULLIF | Q3, Q4, Q5 |

## Repository Structure

```
startup-funding-analytics/
├── sql/
│   ├── 01_schema.sql   -- PostgreSQL schema, three tables
│   ├── q1_p1.sql       -- Q1: boom and bust by year
│   ├── q1_p2.sql       -- Q1: industry drivers of each phase
│   ├── q2.sql          -- Q2: median deal size by industry
│   ├── q3_p1.sql       -- Q3: state growth ranking
│   ├── q3_p2.sql       -- Q3: year-by-year state trajectory
│   ├── q4.sql          -- Q4: top decile capital share
│   └── q5.sql          -- Q5: equity vs debt mix over time
├── tableau-data/
│   └── (query result CSVs exported for Tableau Public)
├── processed/
│   └── (clean CSVs excluded from version control)
├── raw-data/
│   └── data_sources.md                  -- Data provenance and download date
├── setup_data.py                        -- SEC EDGAR bulk download script
├── load_to_supabase.py                  -- PostgreSQL data loading script
└── README.md
```

## Methodology Notes

**Why original filings only:** Form D amendments (D/A) update prior filings rather than representing new capital raises. Including them would double-count deals. All analysis uses SUBMISSIONTYPE = 'D' only, counting each capital raise exactly once.

**Why TOTALAMOUNTSOLD over TOTALOFFERINGAMOUNT:** 42.8% of offering amounts were filed as "Indefinite" — common for open-ended funds with no fixed raise cap. TOTALAMOUNTSOLD represents actual capital raised and is fully numeric across all rows.

**Why US issuers only:** 32,687 foreign issuers (primarily Cayman Islands fund vehicles) were excluded. The analysis focuses on US private capital markets specifically.

**On the equity vs debt finding:** The dataset captures initial filing intent, not final capital structure. Companies may amend their offering type after the original filing. The finding reflects how companies structured their raises at inception, which is a meaningful signal of fundraising strategy even if not the complete picture.