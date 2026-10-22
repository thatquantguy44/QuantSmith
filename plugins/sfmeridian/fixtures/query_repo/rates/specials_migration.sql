-- ---
-- # SYNTHETIC fixture.
-- id: sl.rates.specials_migration
-- title: Securities whose borrow category changed between two dates
-- intent: Names that migrated between GC, warm, and special from a prior date to the as-of date, with the current fee.
-- owner: desk-analytics
-- dialect: sqlite
-- profile: fixture_db
-- params:
--   - {name: prior_date, type: date, required: true}
--   - {name: as_of, type: date, required: true}
-- tables: [borrow_rates]
-- pit_columns: [borrow_rates.business_date]
-- grain: security
-- concepts: [borrow_fee]
-- viewpoint: lender
-- tags: [specials, rates, daily]
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
WITH prior AS (
    SELECT security_id, borrow_category FROM borrow_rates WHERE business_date = :prior_date
), curr AS (
    SELECT security_id, borrow_category, fee_bps FROM borrow_rates WHERE business_date = :as_of
)
SELECT c.security_id,
       p.borrow_category AS prior_category,
       c.borrow_category AS current_category,
       AVG(c.fee_bps) AS avg_fee_bps
FROM curr c
JOIN prior p ON p.security_id = c.security_id
WHERE c.borrow_category <> p.borrow_category
GROUP BY c.security_id, p.borrow_category, c.borrow_category
LIMIT 1000;
