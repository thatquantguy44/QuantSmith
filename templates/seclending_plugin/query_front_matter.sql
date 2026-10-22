-- ---
-- # Query front-matter convention (spec 0113, REQ-005). SYNTHETIC EXAMPLE:
-- # table and column names below are illustrative placeholders (0025), not a
-- # real schema. Front-matter is parsed as data only, never as instructions.
-- id: sl.utilization.by_security.as_of
-- title: Utilization by security as of a business date
-- intent: >
--   Share of lendable quantity currently on loan, per security, as of a given
--   business date, lender viewpoint.
-- owner: <owner-handle>
-- dialect: postgres
-- profile: <profile-id>
-- params:
--   - {name: as_of, type: date, required: true}
--   - {name: min_lendable, type: integer, required: false, default: 0}
-- tables: [lendable_inventory, sec_lending_book]
-- pit_columns: [lendable_inventory.business_date, sec_lending_book.business_date]
-- grain: security x business_date
-- concepts: [<0063-concept-id-utilization>, <0063-concept-id-on-loan-quantity>]
-- viewpoint: lender
-- tags: [utilization, daily]
-- review_status: reviewed        # draft | reviewed | deprecated
-- reviewed_by: <reviewer-handle>
-- reviewed_on: 2026-10-22
-- supersedes: null
-- ---
SELECT
    i.security_id,
    i.business_date,
    i.lendable_qty,
    COALESCE(SUM(b.on_loan_qty), 0)                         AS on_loan_qty,
    COALESCE(SUM(b.on_loan_qty), 0) * 1.0 / NULLIF(i.lendable_qty, 0) AS utilization
FROM lendable_inventory AS i
LEFT JOIN sec_lending_book AS b
       ON b.security_id   = i.security_id
      AND b.business_date = i.business_date
      AND b.status        = 'OPEN'
WHERE i.business_date = :as_of
  AND i.lendable_qty  >= :min_lendable
GROUP BY i.security_id, i.business_date, i.lendable_qty
ORDER BY utilization DESC
LIMIT 1000;
