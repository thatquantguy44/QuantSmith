-- ---
-- # SYNTHETIC fixture: uses :end_date without declaring it.
-- id: sl.broken.undeclared_param
-- title: Revenue with an undeclared parameter
-- intent: Revenue between two dates.
-- owner: program-finance
-- dialect: sqlite
-- profile: fixture_db
-- params:
--   - {name: start_date, type: date, required: true}
-- tables: [program_revenue]
-- pit_columns: [program_revenue.business_date]
-- grain: period
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
SELECT SUM(fee_income) AS lending_revenue FROM program_revenue
WHERE business_date BETWEEN :start_date AND :end_date
