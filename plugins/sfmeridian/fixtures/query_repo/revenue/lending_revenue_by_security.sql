-- ---
-- # SYNTHETIC fixture.
-- id: sl.revenue.by_security.period
-- title: Lending revenue by security over a period
-- intent: Fee income earned by the lending program per security between two business dates, split GC versus specials.
-- owner: program-finance
-- dialect: sqlite
-- profile: fixture_db
-- params:
--   - {name: start_date, type: date, required: true}
--   - {name: end_date, type: date, required: true}
-- tables: [program_revenue, borrow_rates]
-- pit_columns: [program_revenue.business_date, borrow_rates.business_date]
-- grain: security x period
-- concepts: [lending_revenue]
-- viewpoint: lender
-- tags: [revenue, attribution]
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
/* Fee income accrues ACT/360 upstream (0066); this query only sums it. */
SELECT r.security_id,
       br.borrow_category,
       SUM(r.fee_income) AS lending_revenue
FROM program_revenue r
JOIN borrow_rates br
  ON br.security_id = r.security_id
 AND br.business_date = r.business_date
WHERE r.business_date BETWEEN :start_date AND :end_date
GROUP BY r.security_id, br.borrow_category
LIMIT 5000;
