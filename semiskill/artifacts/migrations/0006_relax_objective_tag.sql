-- semiskill/artifacts/migrations/0006_relax_objective_tag.sql
-- Relax objective_tag to free-text (as in AIOS). L6 sensor readings use setpoint identities beyond
-- the initial vocabulary ('judge_calibration', 'drift', 'skill_safety'). objective_tag is a
-- categorization tag, not the ACL label — permissions_label (the security-relevant one) stays
-- CHECK-constrained.
ALTER TABLE artifacts DROP CONSTRAINT IF EXISTS artifacts_objective_tag_check;
