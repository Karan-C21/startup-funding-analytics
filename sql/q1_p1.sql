SELECT s.filing_year, COUNT(*) AS deal_count, ROUND(SUM(o.totalamountsold)/1000000000,2) AS total_amount_bn
FROM submissions s JOIN offerings o ON 
s.accession_number = o.accession_number
WHERE s.filing_year BETWEEN 2014 AND 2025
GROUP BY s.filing_year
ORDER BY s.filing_year