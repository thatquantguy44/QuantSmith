-- ---
-- # SYNTHETIC fixture: a draft that defines utilization differently (conflict).
-- id: sl.utilization.portfolio.draft
-- title: Portfolio utilization (draft)
-- intent: Portfolio-level utilization as on-loan over lendable quantity, summed across securities.
-- review_status: draft
-- tags: [utilization]
-- ---
SELECT SUM(b.on_loan_qty) * 1.0 / NULLIF(SUM(i.lendable_qty), 0) AS utilization
FROM lendable_inventory i
JOIN sec_lending_book b ON b.security_id = i.security_id AND b.business_date = i.business_date
WHERE i.business_date = :as_of
