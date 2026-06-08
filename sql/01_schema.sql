-- =============================================================================
-- SEC Form D Capital Markets Analysis
-- Schema: three normalized tables loaded from processed/clean_*.csv
--
-- Join key: accession_number links all three tables (1-to-1-to-1 relationship)
--
-- Load order: submissions -> issuers -> offerings
--   (no FK constraints defined so COPY order doesn't matter, but this is
--    the logical dependency order)
--
-- To load data after creating tables:
--   \COPY submissions FROM 'processed/clean_submissions.csv' CSV HEADER;
--   \COPY issuers     FROM 'processed/clean_issuers.csv'     CSV HEADER;
--   \COPY offerings   FROM 'processed/clean_offerings.csv'   CSV HEADER;
-- =============================================================================


-- ---------------------------------------------------------------------------
-- TABLE: submissions
-- One row per original Form D filing (SUBMISSIONTYPE = 'D' only).
-- Amendments (D/A) have been excluded to avoid double-counting deals.
-- Source: processed/clean_submissions.csv  (~374k rows)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS submissions;

CREATE TABLE submissions (
    accession_number  VARCHAR(25)  NOT NULL,   -- SEC unique filing ID, join key
    filing_date       DATE         NOT NULL,   -- date filing was received by SEC
    filing_year       SMALLINT     NOT NULL,   -- derived from filing_date (2012-2026)
    filing_quarter    SMALLINT     NOT NULL,   -- derived from filing_date (1-4)
    submissiontype    VARCHAR(5)   NOT NULL,   -- always 'D' in this table

    PRIMARY KEY (accession_number)
);


-- ---------------------------------------------------------------------------
-- TABLE: issuers
-- One row per company that filed a Form D (primary issuer only).
-- Filtered to US issuers by 2-letter state code; foreign codes excluded.
-- Source: processed/clean_issuers.csv  (~540k rows)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS issuers;

CREATE TABLE issuers (
    accession_number         VARCHAR(25)   NOT NULL,  -- join key to submissions/offerings
    entityname               TEXT,                    -- company name as filed
    stateorcountry           CHAR(2)       NOT NULL,  -- 2-letter US state code (CA, NY, TX...)
    stateorcountrydescription VARCHAR(100),            -- human-readable state name
    city                     TEXT,                    -- raw city as filed (mixed case, may have typos)
    city_clean               TEXT,                    -- UPPER(TRIM(city)), normalized for grouping

    PRIMARY KEY (accession_number)
);


-- ---------------------------------------------------------------------------
-- TABLE: offerings
-- One row per filing's financial details.
-- Covers all 609k+ raw filings (no SUBMISSIONTYPE filter applied here).
-- The join to submissions naturally restricts to D-only when needed.
-- Source: processed/clean_offerings.csv  (~609k rows)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS offerings;

CREATE TABLE offerings (
    accession_number      VARCHAR(25)    NOT NULL,   -- join key to submissions/issuers
    industrygrouptype     VARCHAR(100)   NOT NULL,   -- SEC industry classification (never null)
    investmentfundtype    VARCHAR(100),              -- fund sub-type; NULL for non-fund companies
                                                     --   values: 'Venture Capital Fund',
                                                     --           'Private Equity Fund',
                                                     --           'Hedge Fund',
                                                     --           'Other Investment Fund'
    totalofferingamount   NUMERIC(20, 2),            -- max raise target; NULL where filed as
                                                     --   'Indefinite' (common for open-ended funds)
    totalamountsold       BIGINT         NOT NULL,   -- actual capital raised; always numeric;
                                                     --   use this as the primary dollar metric
    isequitytype          BOOLEAN        NOT NULL,   -- true = equity offering (NULL coerced to false)
    isdebttype            BOOLEAN        NOT NULL,   -- true = debt offering   (NULL coerced to false)
    isamendment           BOOLEAN        NOT NULL,   -- true = this row is from a D/A filing
    sale_date             DATE,                      -- date of first sale; NULL if not yet occurred

    PRIMARY KEY (accession_number)
);


-- ---------------------------------------------------------------------------
-- Indexes for common join and filter patterns
-- ---------------------------------------------------------------------------

-- Submissions: year/quarter filters are used in every trend query
CREATE INDEX idx_submissions_year    ON submissions (filing_year);
CREATE INDEX idx_submissions_quarter ON submissions (filing_year, filing_quarter);

-- Issuers: geographic filters
CREATE INDEX idx_issuers_state      ON issuers (stateorcountry);
CREATE INDEX idx_issuers_city_clean ON issuers (city_clean);

-- Offerings: industry/fund-type filters used in every business question
CREATE INDEX idx_offerings_industry  ON offerings (industrygrouptype);
CREATE INDEX idx_offerings_fund_type ON offerings (investmentfundtype);
CREATE INDEX idx_offerings_sale_date ON offerings (sale_date);
