-- ---
-- # SYNTHETIC fixture.
-- id: sl.revenue.split.agent_owner
-- title: Revenue split between agent lender and beneficial owner
-- intent: Beneficial-owner and agent shares of lending fee income per fund over a period.
-- owner: program-finance
-- dialect: sqlite
-- profile: fixture_db
-- params:
--   - {name: start_date, type: date, required: true}
--   - {name: end_date, type: date, required: true}
-- tables: [program_revenue]
-- pit_columns: [program_revenue.business_date]
-- grain: fund x period
-- concepts: [lending_revenue]
-- viewpoint: beneficial_owner
-- tags: [revenue, split]
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
SELECT fund_id,
       SUM(fee_income * owner_split) AS owner_revenue,
       SUM(fee_income * (1 - owner_split)) AS agent_revenue
FROM program_revenue
WHERE business_date BETWEEN :start_date AND :end_date
GROUP BY fund_id
LIMIT 500;
