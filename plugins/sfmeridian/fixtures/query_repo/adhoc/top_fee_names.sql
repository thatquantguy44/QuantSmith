-- SYNTHETIC fixture: no front-matter, indexed as unreviewed.
select security_id, fee_bps from borrow_rates where business_date = :as_of order by fee_bps desc limit 20
