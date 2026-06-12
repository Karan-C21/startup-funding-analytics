-- Q1 (Part 2): Boom vs bust by industry - 2021 capital vs 2022-2024 annualized average.
-- Dividing the bust period by 3 makes the per-year comparison fair against the single boom year.
WITH boom AS (
    SELECT
        o.industrygrouptype,
        COUNT(*) AS deal_count,
        ROUND(SUM(o.totalamountsold) / 1000000000, 2) AS total_amount
    FROM submissions s
    JOIN offerings o ON s.accession_number = o.accession_number
    WHERE s.filing_year = 2021
    GROUP BY o.industrygrouptype
),
bust AS (
    SELECT
        o.industrygrouptype,
        COUNT(*) AS deal_count,
        ROUND((SUM(o.totalamountsold) / 1000000000) / 3, 2) AS total_amount
    FROM submissions s
    JOIN offerings o ON s.accession_number = o.accession_number
    WHERE s.filing_year BETWEEN 2022 AND 2024
    GROUP BY o.industrygrouptype
)
SELECT
    boom.industrygrouptype,
    boom.total_amount AS boom_capital,
    bust.total_amount AS bust_capital,
    bust.total_amount - boom.total_amount AS change
FROM boom
JOIN bust ON boom.industrygrouptype = bust.industrygrouptype
ORDER BY boom.total_amount DESC;
