-- ---
-- # SYNTHETIC fixture: reuses an id already taken by lending/utilization_by_security.sql.
-- id: sl.utilization.by_security.as_of
-- title: Duplicate
-- intent: Same id as another query.
-- review_status: draft
-- ---
SELECT security_id FROM lendable_inventory WHERE business_date = :as_of
