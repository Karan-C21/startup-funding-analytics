WITH qualified_industries AS (
    SELECT o.industrygrouptype
    FROM submissions s
    JOIN offerings o ON s.accession_number = o.accession_number
    WHERE s.filing_year BETWEEN 2019 AND 2025
    GROUP BY o.industrygrouptype
    HAVING COUNT(*) / 7.0 >= 200
),
median_by_industry AS (
    SELECT 
        o.industrygrouptype,
        s.filing_year,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY o.totalamountsold)::NUMERIC / 1000000, 2) AS median_deal_size_m
    FROM submissions s
    JOIN offerings o ON s.accession_number = o.accession_number
    WHERE s.filing_year BETWEEN 2019 AND 2025
    AND o.industrygrouptype IN (SELECT industrygrouptype FROM qualified_industries)
    GROUP BY o.industrygrouptype, s.filing_year
)
SELECT
    industrygrouptype,
    filing_year,
    median_deal_size_m,
    LAG(median_deal_size_m) OVER (
        PARTITION BY industrygrouptype
        ORDER BY filing_year
    ) AS prev_year_median,
    ROUND(
        median_deal_size_m - LAG(median_deal_size_m) OVER (
            PARTITION BY industrygrouptype
            ORDER BY filing_year
        ), 2
    ) AS yoy_change
FROM median_by_industry
ORDER BY industrygrouptype, filing_year;