WITH state_yearly AS (
    SELECT 
        i.stateorcountrydescription,
        s.filing_year,
        COUNT(*) AS deal_count
    FROM issuers i 
    JOIN submissions s ON i.accession_number = s.accession_number
    JOIN offerings o ON s.accession_number = o.accession_number
    WHERE s.filing_year BETWEEN 2019 AND 2025 
    AND i.stateorcountrydescription IS NOT NULL
    AND o.industrygrouptype != 'Pooled Investment Fund'
    GROUP BY i.stateorcountrydescription, s.filing_year
),
state_summary AS (
    SELECT
        stateorcountrydescription,
        SUM(CASE WHEN filing_year = 2019 THEN deal_count ELSE 0 END) AS deals_2019,
        SUM(CASE WHEN filing_year = 2025 THEN deal_count ELSE 0 END) AS deals_2025,
        SUM(deal_count) AS total_deals_all_years
    FROM state_yearly
    GROUP BY stateorcountrydescription
)
SELECT
    stateorcountrydescription,
    deals_2019,
    deals_2025,
    total_deals_all_years,
    ROUND((deals_2025 - deals_2019) * 100.0 / NULLIF(deals_2019, 0), 1) AS growth_pct_2019_to_2025,
    RANK() OVER (ORDER BY (deals_2025 - deals_2019) * 100.0 / NULLIF(deals_2019, 0) DESC) AS growth_rank
FROM state_summary
WHERE deals_2019 >= 10
ORDER BY growth_rank;