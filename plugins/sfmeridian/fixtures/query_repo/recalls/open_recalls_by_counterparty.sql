-- ---
-- # SYNTHETIC fixture (Databricks dialect).
-- id: sl.recalls.open.by_counterparty
-- title: Open recalls by borrower counterparty
-- intent: Outstanding recall quantity per borrower and reason as of a business date.
-- owner: desk-analytics
-- dialect: databricks
-- profile: fixture_db
-- params:
--   - {name: as_of, type: date, required: true}
-- tables: [lending.recalls, lending.counterparties]
-- pit_columns: [lending.recalls.recall_date]
-- grain: counterparty x reason
-- concepts: [recall_quantity]
-- viewpoint: lender
-- tags: [recalls, risk]
-- review_status: reviewed
-- reviewed_by: lending-lead
-- reviewed_on: 2026-10-22
-- ---
SELECT `c`.`counterparty_id`, `rc`.`reason`, SUM(`rc`.`recall_qty`) AS recall_qty
FROM `lending`.`recalls` AS `rc`
INNER JOIN `lending`.`counterparties` AS `c` USING (counterparty_id)
WHERE `rc`.`recall_date` <= :as_of AND `rc`.`status` = 'OPEN'
GROUP BY `c`.`counterparty_id`, `rc`.`reason`
LIMIT 500
