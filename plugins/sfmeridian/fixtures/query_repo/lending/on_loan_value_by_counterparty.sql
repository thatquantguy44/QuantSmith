-- ---
-- # SYNTHETIC fixture.
-- id: sl.on_loan_value.by_counterparty.as_of
-- title: On-loan value by borrower counterparty
-- intent: Market value on loan to each borrower as of a business date, with the counterparty's credit tier.
-- owner: desk-analytics
-- dialect: sqlite
-- profile: fixture_db
-- params:
--   - {name: as_of, type: date, required: true}
-- tables: [sec_lending_book, counterparties]
-- pit_columns: [sec_lending_book.business_date]
-- grain: counterparty x business_date
-- concepts: [on_loan_value]
-- viewpoint: lender
-- tags: [exposure, counterparty, daily]
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
SELECT c.counterparty_id,
       c.credit_tier,
       SUM(bk.on_loan_value) AS on_loan_value
FROM sec_lending_book bk
JOIN counterparties c ON c.counterparty_id = bk.counterparty_id
WHERE bk.business_date = :as_of
  AND bk.status = 'OPEN'
GROUP BY c.counterparty_id, c.credit_tier
LIMIT 500;
