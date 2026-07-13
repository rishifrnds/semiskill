-- semiskill/artifacts/migrations/0007_cost.sql
-- L5 cost economics: a COST_LEDGER artifact per governed model call. IRREVERSIBLE ALTER TYPE.
ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'cost_ledger';
