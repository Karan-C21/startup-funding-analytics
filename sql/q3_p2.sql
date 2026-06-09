SELECT 
    i.stateorcountrydescription,
    s.filing_year,
    COUNT(*) AS deal_count
FROM issuers i 
JOIN submissions s ON i.accession_number = s.accession_number
WHERE s.filing_year BETWEEN 2019 AND 2025
AND i.stateorcountrydescription IS NOT NULL
GROUP BY i.stateorcountrydescription, s.filing_year
ORDER BY i.stateorcountrydescription, s.filing_year;