-- Q5: Equity vs debt offering structure for operating companies, 2019-2025.
-- Excludes Pooled Investment Funds (which are equity by structure) to isolate
-- the financing choice signal from operating companies.
-- 3-year rolling average smooths year-to-year noise in the debt percentage.
WITH yearly_structure AS (
    SELECT
        s.filing_year,
        COUNT(*) AS total_deals,
        SUM(CASE WHEN o.isequitytype = true THEN 1 ELSE 0 END) AS equity_deals,
        SUM(CASE WHEN o.isdebttype = true THEN 1 ELSE 0 END) AS debt_deals,
        SUM(CASE WHEN o.isequitytype = true AND o.isdebttype = true THEN 1 ELSE 0 END) AS both_deals
    FROM submissions s
    JOIN offerings o ON s.accession_number = o.accession_number
    WHERE s.filing_year BETWEEN 2019 AND 2025
      AND o.industrygrouptype != 'Pooled Investment Fund'
    GROUP BY s.filing_year
),
with_percentages AS (
    SELECT
        filing_year,
        total_deals,
        equity_deals,
        debt_deals,
        both_deals,
        ROUND(equity_deals * 100.0 / NULLIF(total_deals, 0), 1) AS equity_pct,
        ROUND(debt_deals * 100.0 / NULLIF(total_deals, 0), 1) AS debt_pct,
        ROUND(both_deals * 100.0 / NULLIF(total_deals, 0), 1) AS both_pct
    FROM yearly_structure
)
SELECT
    filing_year,
    total_deals,
    equity_deals,
    equity_pct,
    debt_deals,
    debt_pct,
    both_deals,
    both_pct,
    ROUND(AVG(debt_pct) OVER (
        ORDER BY filing_year
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 1) AS debt_pct_3yr_rolling_avg
FROM with_percentages
ORDER BY filing_year;
