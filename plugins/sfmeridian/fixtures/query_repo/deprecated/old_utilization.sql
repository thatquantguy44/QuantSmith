-- ---
-- # SYNTHETIC fixture: deprecated, never served.
-- id: sl.utilization.legacy
-- title: Legacy utilization (deprecated)
-- intent: Old utilization by security using quantity on loan over quantity lendable.
-- review_status: deprecated
-- tags: [utilization]
-- ---
SELECT security_id, on_loan_qty * 1.0 / lendable_qty AS utilization FROM legacy_utilization WHERE business_date = :as_of
