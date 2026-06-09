WITH deal_deciles AS (
    SELECT
        s.filing_year,
        o.totalamountsold,
        NTILE(10) OVER (
            PARTITION BY s.filing_year
            ORDER BY o.totalamountsold
        ) AS deal_decile
    FROM submissions s
    JOIN offerings o ON s.accession_number = o.accession_number
    WHERE s.filing_year BETWEEN 2019 AND 2025
    AND o.totalamountsold > 0
),
yearly_concentration AS (
    SELECT
        filing_year,
        ROUND(SUM(totalamountsold) / 1000000000, 2) AS total_capital_b,
        ROUND(SUM(CASE WHEN deal_decile = 10 THEN totalamountsold ELSE 0 END) / 1000000000, 2) AS top_decile_capital_b,
        COUNT(*) AS total_deals,
        SUM(CASE WHEN deal_decile = 10 THEN 1 ELSE 0 END) AS top_decile_deals
    FROM deal_deciles
    GROUP BY filing_year
)
SELECT
    filing_year,
    total_capital_b,
    top_decile_capital_b,
    total_deals,
    top_decile_deals,
    ROUND(top_decile_capital_b / NULLIF(total_capital_b, 0) * 100, 1) AS top_decile_pct_of_capital
FROM yearly_concentration
ORDER BY filing_year;