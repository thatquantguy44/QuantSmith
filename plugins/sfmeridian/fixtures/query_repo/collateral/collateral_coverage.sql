-- ---
-- # SYNTHETIC fixture.
-- id: sl.collateral.coverage.by_loan
-- title: Collateral coverage ratio by loan
-- intent: Collateral value held against each open loan divided by its on-loan value, as of a business date.
-- owner: collateral-ops
-- dialect: sqlite
-- profile: fixture_db
-- params:
--   - {name: as_of, type: date, required: true}
-- tables: [collateral, sec_lending_book]
-- pit_columns: [collateral.business_date, sec_lending_book.business_date]
-- grain: loan x business_date
-- concepts: [collateral_value, on_loan_value]
-- viewpoint: lender
-- tags: [collateral, daily]
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
SELECT bk.loan_id,
       SUM(cl.collateral_value) / NULLIF(SUM(bk.on_loan_value), 0) AS collateral_coverage
FROM collateral cl
JOIN sec_lending_book bk ON bk.loan_id = cl.loan_id AND bk.business_date = cl.business_date
WHERE cl.business_date = :as_of
GROUP BY bk.loan_id
LIMIT 5000;
