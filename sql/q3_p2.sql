-- Q3 (Part 2): Year-by-year deal count per state, 2019-2025.
-- Tableau feed for trend line visualization. Excludes Pooled Investment Funds
-- for consistency with the state growth ranking in q3_p1.sql.
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
ORDER BY i.stateorcountrydescription, s.filing_year;
