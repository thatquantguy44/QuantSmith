-- ---
-- # SYNTHETIC fixture (Oracle dialect).
-- id: sl.rates.fee_by_category.oracle
-- title: Average borrow fee by borrow category (Oracle)
-- intent: Average lending fee in basis points for GC, warm, and special names on a business date.
-- owner: desk-analytics
-- dialect: oracle
-- profile: fixture_db
-- params:
--   - {name: as_of, type: date, required: true}
-- tables: [borrow_rates]
-- pit_columns: [borrow_rates.business_date]
-- grain: borrow_category x business_date
-- concepts: [borrow_fee]
-- viewpoint: lender
-- tags: [rates, daily]
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
SELECT "BR"."BORROW_CATEGORY" AS borrow_category,
       AVG("BR"."FEE_BPS") AS avg_fee_bps
FROM "BORROW_RATES" "BR"
WHERE "BR"."BUSINESS_DATE" = :as_of
GROUP BY "BR"."BORROW_CATEGORY"
FETCH FIRST 100 ROWS ONLY
