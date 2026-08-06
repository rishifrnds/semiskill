-- Catalog authority is an append-only actuator projection, never a human-looking JSON claim.
-- Raw approval artifacts remain immutable audit history. Only a role-scoped activation of a
-- deterministic, exact-version evidence chain can make an approval visible to catalog readers.

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_approval_actuator') THEN
        CREATE ROLE semiskill_approval_actuator NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO semiskill_approval_actuator;
REVOKE ALL ON artifacts FROM semiskill_approval_actuator;
-- Deployment must grant this role only to a dedicated actuator login. The migration/schema owner
-- and ordinary runtime role are deliberately not made members.
REVOKE semiskill_approval_actuator FROM CURRENT_USER;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'artifacts'::regclass AND conname = 'artifact_payload_is_object'
    ) THEN
        ALTER TABLE artifacts ADD CONSTRAINT artifact_payload_is_object
            CHECK (jsonb_typeof(payload) = 'object') NOT VALID;
    END IF;
END $$;
ALTER TABLE artifacts VALIDATE CONSTRAINT artifact_payload_is_object;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'semiskill_acl_reader') THEN
        CREATE ROLE semiskill_acl_reader NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO semiskill_acl_reader;
REVOKE ALL ON artifacts FROM semiskill_acl_reader;

CREATE TABLE IF NOT EXISTS publication_trust_policy (
    policy_id boolean PRIMARY KEY DEFAULT true CHECK (policy_id),
    environment text NOT NULL CHECK (environment IN ('development', 'test', 'production')),
    database_name text NOT NULL UNIQUE,
    policy_version text NOT NULL CHECK (btrim(policy_version) <> ''),
    approve_threshold numeric NOT NULL CHECK (approve_threshold >= 0 AND approve_threshold <= 1),
    entra_issuer text,
    entra_tenant_id text,
    enabled boolean NOT NULL DEFAULT false,
    allow_unregistered_test_fixtures boolean NOT NULL DEFAULT false
    ,CHECK (
        environment <> 'production'
        OR (
            nullif(btrim(entra_issuer), '') IS NOT NULL
            AND nullif(btrim(entra_tenant_id), '') IS NOT NULL
        )
    ),
    CHECK (NOT allow_unregistered_test_fixtures OR environment = 'test')
);
REVOKE ALL ON publication_trust_policy FROM PUBLIC, semiskill_app, semiskill_submitter;

CREATE TABLE IF NOT EXISTS publication_skill_registry (
    slug text PRIMARY KEY CHECK (btrim(slug) <> ''),
    role text NOT NULL CHECK (btrim(role) <> ''),
    level text NOT NULL CHECK (btrim(level) <> ''),
    permissions_label text NOT NULL CHECK (
        permissions_label IN ('public', 'team', 'need-to-know', 'regulated')
    ),
    active boolean NOT NULL,
    judge_required boolean NOT NULL,
    registry_sha256 text NOT NULL CHECK (registry_sha256 ~ '^[0-9a-f]{64}$')
);
REVOKE ALL ON publication_skill_registry FROM PUBLIC, semiskill_app, semiskill_submitter;
INSERT INTO publication_skill_registry (
    slug, role, level, permissions_label, active, judge_required, registry_sha256
) VALUES
('dv-ams-convergence-triage','ams-verification-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-ams-view-binding-audit','ams-verification-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-artifact-redaction-egress','applications-engineer','fresher','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-asset-flow-property-authoring','security-verification-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-build-filelist-hygiene','dv-infra-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-cdc-rdc-triage','static-signoff-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-compliance-test-authoring','vip-engineer','fresher','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-compute-license-efficiency','dv-infra-engineer','principal','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-config-space-coverage','ip-dv-engineer','principal','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-connectivity-table-checks','soc-dv-engineer','fresher','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-connect-module-discipline-debug','ams-verification-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-coverage-hole-closure','ip-dv-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-coverage-hole-disposition','dv-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-coverage-merge-report','dv-infra-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-cross-tool-mismatch-adjudication','eda-product-validation-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-crypto-kat-coverage-audit','security-verification-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-csr-warl-access-audit','processor-ip-dv-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-customer-defect-handoff','applications-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-customer-escalation-isolation','applications-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-customer-flow-deployment','applications-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-custom-instruction-verification-plan','processor-ip-dv-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-dfi-boundary-blame','memory-ip-dv-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-emulation-bringup','emulation-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-emulation-dump-strategy','emulation-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-emulation-sim-mismatch-triage','emulation-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-emulation-test-porting-audit','emulation-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-emulation-throughput-triage','emulation-engineer','senior-staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-error-injection-ras','ip-dv-engineer','senior-staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-escalation-ownership','verification-lead','director','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-escape-analysis','verification-lead','senior-manager','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-fault-campaign-iso26262','safety-verification-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-formal-apps','formal-verification','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-formal-convergence','formal-verification','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-formal-overconstraint-credit','formal-verification','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-formal-property-authoring','formal-verification','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-formal-target-scoping','formal-verification','senior-staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-gls-bringup','ip-dv-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-isa-step-compare','processor-ip-dv-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-lint-triage','static-signoff-engineer','fresher','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-lrm-conformance-matrix','eda-product-validation-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-memory-model-training','memory-ip-dv-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-memory-ordering-litmus','processor-ip-dv-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-memory-perf-bandwidth','memory-ip-dv-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-mem-refresh-lowpower-audit','memory-ip-dv-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-mem-timing-check-triage','memory-ip-dv-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-minimal-reproducer','dv-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-power-aware-sim-debug','static-signoff-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-protocol-checker-rule','vip-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-ral-bringup','soc-dv-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-real-signal-behavioural-checks','ams-verification-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-regression-runtime-tuning','applications-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-regression-tiering-farm','dv-infra-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-regression-triage-routing','ip-dv-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-release-gate','verification-lead','manager','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-repo-orientation','dv-infra-engineer','fresher','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-reset-clock-scenario-matrix','soc-dv-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-rnm-authoring-correlation','ams-verification-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-safety-manual-aou','safety-verification-engineer','principal','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-safety-mechanism-verification-map','safety-verification-engineer','senior-staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-safety-req-trace-audit','safety-verification-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-secure-register-policy-audit','security-verification-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-security-build-divergence-audit','security-verification-engineer','principal','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-security-negative-tests','security-verification-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-signal-trace-localisation','dv-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-sim-log-first-error','dv-engineer','fresher','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-soc-scenario-boot','soc-dv-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-spec-ecn-delta','vip-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-spec-feature-extract','vip-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-spec-interpretation-ledger','vip-engineer','principal','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-status-rollup','verification-lead','lead','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-tb-architecture-record','dv-engineer','principal','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-testplan-traceability-review','verification-lead','lead','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-tool-bug-testcase-extraction','eda-product-validation-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-tool-feature-testplan','eda-product-validation-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-tool-release-behaviour-diff','eda-product-validation-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-tool-version-migration','dv-infra-engineer','staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-trap-exception-triage','processor-ip-dv-engineer','junior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-undetected-fault-closure','safety-verification-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-uvm-agent-checker','ip-dv-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-vip-coverage-model','vip-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-vip-integration','soc-dv-engineer','intermediate','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-vip-release-compat','vip-engineer','senior-staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-waiver-corpus-audit','static-signoff-engineer','senior-staff','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b'),
('dv-xprop-triage','static-signoff-engineer','senior','public',true,true,'05b613e745f4fdbae62dd1d68bb37959e2ae341401c7d166165723167c02c74b')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS verified_publication_events (
    approval_id uuid PRIMARY KEY,
    skill_version_id uuid NOT NULL,
    automated_review_id uuid NOT NULL,
    content_review_id uuid NOT NULL,
    corrects_ref uuid,
    decision text NOT NULL CHECK (decision IN ('approve', 'unpublish')),
    slug text NOT NULL,
    version text NOT NULL,
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    permissions_label text NOT NULL,
    environment text NOT NULL CHECK (environment IN ('development', 'test', 'production')),
    policy_version text NOT NULL,
    approve_threshold numeric NOT NULL,
    chain_sha256 text NOT NULL CHECK (chain_sha256 ~ '^[0-9a-f]{64}$'),
    activated_at timestamptz NOT NULL DEFAULT now(),
    activated_by text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_verified_correction_per_head
ON verified_publication_events (corrects_ref) WHERE corrects_ref IS NOT NULL;
REVOKE ALL ON verified_publication_events FROM PUBLIC, semiskill_app, semiskill_submitter;

CREATE OR REPLACE FUNCTION reject_verified_publication_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'verified publication projection is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS verified_publication_events_append_only ON verified_publication_events;
CREATE TRIGGER verified_publication_events_append_only
BEFORE UPDATE OR DELETE ON verified_publication_events
FOR EACH ROW EXECUTE FUNCTION reject_verified_publication_mutation();

CREATE OR REPLACE FUNCTION semiskill_canonical_json_v1(doc jsonb) RETURNS text
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE
SET search_path = pg_catalog, public AS $$
DECLARE
    out_text text;
BEGIN
    CASE jsonb_typeof(doc)
        WHEN 'object' THEN
            SELECT '{' || coalesce(string_agg(
                to_jsonb(entry.key)::text || ':' || semiskill_canonical_json_v1(entry.value),
                ',' ORDER BY entry.key COLLATE "C"), '') || '}'
            INTO out_text
            FROM jsonb_each(doc) entry;
        WHEN 'array' THEN
            SELECT '[' || coalesce(string_agg(
                semiskill_canonical_json_v1(entry.value), ',' ORDER BY entry.ordinality), '') || ']'
            INTO out_text
            FROM jsonb_array_elements(doc) WITH ORDINALITY entry(value, ordinality);
        ELSE
            out_text := doc::text;
    END CASE;
    RETURN out_text;
END;
$$;

CREATE OR REPLACE FUNCTION skill_payload_sha256_v1(payload jsonb) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path = pg_catalog, public AS $$
    SELECT encode(sha256(convert_to(semiskill_canonical_json_v1(jsonb_build_object(
        'slug', payload->'slug',
        'name', payload->'name',
        'description', payload->'description',
        'version', payload->'version',
        'function', payload->'function',
        'role', payload->'role',
        'level', payload->'level',
        'tags', payload->'tags',
        'allowed_tools', payload->'allowed_tools',
        'skill_md', payload->'skill_md',
        'body', payload->'body',
        'files', payload->'files'
    )), 'UTF8')), 'hex');
$$;

CREATE OR REPLACE FUNCTION semiskill_positive_int_v1(doc jsonb) RETURNS integer
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    value_text text;
BEGIN
    IF doc IS NULL OR jsonb_typeof(doc) <> 'number' THEN
        RETURN NULL;
    END IF;
    value_text := doc#>>'{}';
    IF value_text !~ '^[1-9][0-9]*$' OR length(value_text) > 9 THEN
        RETURN NULL;
    END IF;
    RETURN value_text::integer;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION semiskill_number_v1(doc jsonb) RETURNS numeric
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    value_text text;
BEGIN
    IF doc IS NULL OR jsonb_typeof(doc) <> 'number' THEN
        RETURN NULL;
    END IF;
    value_text := doc#>>'{}';
    IF length(value_text) > 64 THEN
        RETURN NULL;
    END IF;
    RETURN value_text::numeric;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION semiskill_semver_valid_v1(candidate text)
RETURNS boolean
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    candidate_parts text[];
BEGIN
    IF candidate IS NULL
       OR candidate !~ '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' THEN
        RETURN false;
    END IF;
    candidate_parts := string_to_array(candidate, '.');
    RETURN NOT EXISTS (
        SELECT 1 FROM unnest(candidate_parts) part WHERE length(part) > 18
    );
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION semiskill_semver_greater_v1(candidate text, predecessor text)
RETURNS boolean
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    candidate_parts text[];
    predecessor_parts text[];
    candidate_numbers numeric[];
    predecessor_numbers numeric[];
BEGIN
    IF NOT semiskill_semver_valid_v1(candidate)
       OR NOT semiskill_semver_valid_v1(predecessor) THEN
        RETURN false;
    END IF;
    candidate_parts := string_to_array(candidate, '.');
    predecessor_parts := string_to_array(predecessor, '.');
    candidate_numbers := ARRAY[
        candidate_parts[1]::numeric, candidate_parts[2]::numeric, candidate_parts[3]::numeric
    ];
    predecessor_numbers := ARRAY[
        predecessor_parts[1]::numeric, predecessor_parts[2]::numeric, predecessor_parts[3]::numeric
    ];
    RETURN candidate_numbers > predecessor_numbers;
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION content_review_ready_v1(content_id uuid, skill_id uuid)
RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    sv artifacts%ROWTYPE;
    cr artifacts%ROWTYPE;
    prior artifacts%ROWTYPE;
    fingerprint text;
    top_id uuid := content_id;
    expected_attempt integer;
    current_attempt integer;
    candidate_count integer;
    check_name text;
    check_value jsonb;
    finding jsonb;
    newer_finding jsonb;
    finding_id text;
    finding_ids text[] := ARRAY[]::text[];
    seen_run_ids text[] := ARRAY[]::text[];
    seen_reviewers text[] := ARRAY[]::text[];
    seen_fixers text[] := ARRAY[]::text[];
    effective_findings jsonb := '{}'::jsonb;
BEGIN
    SELECT * INTO sv FROM artifacts
    WHERE artifact_id = skill_id AND artifact_type = 'skill_version';
    IF NOT FOUND THEN RETURN false; END IF;
    fingerprint := skill_payload_sha256_v1(sv.payload);
    SELECT * INTO cr FROM artifacts
    WHERE artifact_id = content_id AND artifact_type = 'review';
    IF NOT FOUND THEN RETURN false; END IF;
    expected_attempt := semiskill_positive_int_v1(cr.payload->'attempt');
    IF expected_attempt IS NULL THEN RETURN false; END IF;

    SELECT count(*) INTO candidate_count
    FROM artifacts candidate
    WHERE candidate.artifact_type = 'review'
      AND candidate.payload->>'review_kind' = 'content_review'
      AND cardinality(candidate.input_refs) >= 1
      AND candidate.input_refs[1] = skill_id;
    IF candidate_count <> expected_attempt THEN RETURN false; END IF;

    LOOP
        current_attempt := semiskill_positive_int_v1(cr.payload->'attempt');
        IF current_attempt IS DISTINCT FROM expected_attempt
           OR cr.payload->>'review_kind' IS DISTINCT FROM 'content_review'
           OR cr.payload->>'schema_version' IS DISTINCT FROM '1'
           OR cr.source_system IS DISTINCT FROM 'cli'
           OR cr.actor_kind IS DISTINCT FROM 'agent'
           OR cr.objective_tag IS DISTINCT FROM 'safety'
           OR cr.permissions_label IS DISTINCT FROM sv.permissions_label
           OR coalesce(sv.timestamp_end, sv.timestamp_start) > cr.timestamp_start
           OR cardinality(cr.input_refs) < 1
           OR cr.input_refs[1] IS DISTINCT FROM skill_id
           OR cr.payload->>'skill_payload_sha256' IS DISTINCT FROM fingerprint
           OR cr.ground_truth_ref IS DISTINCT FROM fingerprint
           OR cr.payload->>'slug' IS DISTINCT FROM sv.payload->>'slug'
           OR cr.payload->>'version' IS DISTINCT FROM sv.payload->>'version'
           OR cr.payload->>'role' IS DISTINCT FROM sv.payload->>'role'
           OR cr.payload->>'level' IS DISTINCT FROM sv.payload->>'level'
           OR nullif(btrim(cr.payload->>'prompt_version'), '') IS NULL
           OR nullif(btrim(cr.payload->>'run_id'), '') IS NULL
           OR nullif(btrim(cr.payload->>'batch_id'), '') IS NULL
           OR nullif(btrim(cr.payload->>'reviewer_identity'), '') IS NULL
           OR nullif(btrim(cr.payload->>'fixer_identity'), '') IS NULL
           OR cr.payload->>'reviewer_identity' = cr.payload->>'fixer_identity'
           OR cr.actor IS DISTINCT FROM cr.payload->>'reviewer_identity'
           OR jsonb_typeof(cr.payload->'checks') IS DISTINCT FROM 'object'
           OR jsonb_typeof(cr.payload->'findings') IS DISTINCT FROM 'array' THEN
            RETURN false;
        END IF;
        IF cr.artifact_id = top_id AND (
            cr.payload->>'phase' IS DISTINCT FROM 'recheck'
            OR cr.payload->>'prompt_version' !~ '^P5-RECHECK-CALIBRATED@[1-9][0-9]*$'
        ) THEN
            RETURN false;
        END IF;
        IF cr.payload->>'run_id' = ANY(seen_run_ids)
           OR cr.payload->>'reviewer_identity' = ANY(seen_reviewers)
           OR cr.payload->>'reviewer_identity' = ANY(seen_fixers)
           OR cr.payload->>'fixer_identity' = ANY(seen_reviewers) THEN
            RETURN false;
        END IF;
        seen_run_ids := array_append(seen_run_ids, cr.payload->>'run_id');
        seen_reviewers := array_append(seen_reviewers, cr.payload->>'reviewer_identity');
        seen_fixers := array_append(seen_fixers, cr.payload->>'fixer_identity');

        FOREACH check_name IN ARRAY ARRAY[
            'strict_lint', 'consistency', 'source_hash', 'artifact_reconciliation'
        ] LOOP
            check_value := cr.payload->'checks'->check_name;
            IF jsonb_typeof(check_value) IS DISTINCT FROM 'object'
               OR jsonb_typeof(check_value->'passed') IS DISTINCT FROM 'boolean'
               OR nullif(btrim(check_value->>'evidence'), '') IS NULL
               OR (cr.artifact_id = top_id AND check_value->'passed' IS DISTINCT FROM 'true'::jsonb)
            THEN
                RETURN false;
            END IF;
        END LOOP;

        finding_ids := ARRAY[]::text[];
        FOR finding IN SELECT value FROM jsonb_array_elements(cr.payload->'findings') LOOP
            IF jsonb_typeof(finding) IS DISTINCT FROM 'object'
               OR nullif(btrim(finding->>'finding_id'), '') IS NULL
               OR nullif(btrim(finding->>'category'), '') IS NULL
               OR nullif(btrim(finding->>'severity'), '') IS NULL
               OR finding->>'severity' NOT IN ('blocking', 'non_blocking')
               OR nullif(btrim(finding->>'evidence'), '') IS NULL
               OR nullif(btrim(finding->>'location'), '') IS NULL
               OR nullif(btrim(finding->>'required_change'), '') IS NULL
               OR nullif(btrim(finding->>'disposition'), '') IS NULL
               OR finding->>'disposition' NOT IN ('open', 'resolved', 'disputed') THEN
                RETURN false;
            END IF;
            finding_id := finding->>'finding_id';
            IF finding_id = ANY(finding_ids) THEN RETURN false; END IF;
            finding_ids := array_append(finding_ids, finding_id);
            newer_finding := effective_findings->finding_id;
            IF newer_finding IS NULL THEN
                effective_findings := effective_findings || jsonb_build_object(finding_id, finding);
            ELSIF newer_finding->>'category' IS DISTINCT FROM finding->>'category'
               OR newer_finding->>'severity' IS DISTINCT FROM finding->>'severity'
               OR (
                    finding->>'disposition' = 'resolved'
                    AND newer_finding->>'disposition' <> 'resolved'
               ) THEN
                RETURN false;
            END IF;
        END LOOP;

        IF expected_attempt = 1 THEN
            IF cardinality(cr.input_refs) <> 1 OR cr.payload->'prior_review_ref' <> 'null'::jsonb THEN
                RETURN false;
            END IF;
            EXIT;
        END IF;
        IF cardinality(cr.input_refs) <> 2
           OR cr.payload->>'prior_review_ref' IS DISTINCT FROM cr.input_refs[2]::text THEN
            RETURN false;
        END IF;
        SELECT * INTO prior FROM artifacts
        WHERE artifact_id = cr.input_refs[2] AND artifact_type = 'review';
        IF NOT FOUND
           OR coalesce(prior.timestamp_end, prior.timestamp_start) > cr.timestamp_start THEN
            RETURN false;
        END IF;
        cr := prior;
        expected_attempt := expected_attempt - 1;
    END LOOP;
    FOR finding IN SELECT value FROM jsonb_each(effective_findings) LOOP
        IF finding->>'severity' = 'blocking'
           AND finding->>'disposition' IN ('open', 'disputed') THEN
            RETURN false;
        END IF;
    END LOOP;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION approval_v1_projection_valid(approval_id_to_check uuid)
RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    ap artifacts%ROWTYPE;
    sv artifacts%ROWTYPE;
    automated artifacts%ROWTYPE;
    content artifacts%ROWTYPE;
    scan artifacts%ROWTYPE;
    parent_event verified_publication_events%ROWTYPE;
    parent_ap artifacts%ROWTYPE;
    policy publication_trust_policy%ROWTYPE;
    registry_entry publication_skill_registry%ROWTYPE;
    decision text;
    environment_name text;
    provider text;
    subject text;
    context jsonb;
    fingerprint text;
    expected_scan_ids jsonb;
    scan_ref uuid;
    scan_ordinal bigint;
    stage integer;
    seen_stages integer[] := ARRAY[]::integer[];
    safety numeric;
    measured_min numeric := NULL;
    judge_required boolean;
    judge_required_by_policy boolean;
BEGIN
    SELECT * INTO ap FROM artifacts
    WHERE artifact_id = approval_id_to_check AND artifact_type = 'approval';
    IF NOT FOUND THEN RETURN false; END IF;
    decision := ap.payload->>'decision';
    environment_name := ap.payload->>'environment';
    provider := ap.payload#>>'{authentication,provider}';
    subject := ap.payload#>>'{authentication,subject}';
    context := ap.payload#>'{authentication,context}';

    SELECT * INTO policy FROM publication_trust_policy configured
    WHERE configured.policy_id = true
      AND configured.enabled
      AND configured.database_name = current_database()
      AND configured.environment = environment_name;
    IF NOT FOUND THEN RETURN false; END IF;

    IF ap.actor_kind IS DISTINCT FROM 'human'
       OR ap.objective_tag IS DISTINCT FROM 'safety'
       OR ap.payload->>'schema_version' IS DISTINCT FROM 'approval/v1'
       OR decision NOT IN ('approve', 'unpublish')
       OR jsonb_typeof(ap.payload->'published') IS DISTINCT FROM 'boolean'
       OR ap.payload->'published' IS DISTINCT FROM
          (CASE WHEN decision = 'approve' THEN 'true'::jsonb ELSE 'false'::jsonb END)
       OR nullif(btrim(ap.payload->>'reason'), '') IS NULL
       OR environment_name NOT IN ('development', 'test', 'production')
       OR cardinality(ap.input_refs) <> 3
       OR jsonb_typeof(ap.payload->'skill') IS DISTINCT FROM 'object'
       OR jsonb_typeof(ap.payload->'evidence') IS DISTINCT FROM 'object'
       OR ap.payload#>>'{skill,artifact_id}' IS DISTINCT FROM ap.input_refs[1]::text
       OR ap.payload#>>'{evidence,automated_review_id}' IS DISTINCT FROM ap.input_refs[2]::text
       OR ap.payload#>>'{evidence,content_review_id}' IS DISTINCT FROM ap.input_refs[3]::text
       OR jsonb_typeof(ap.payload->'authentication') IS DISTINCT FROM 'object'
       OR ap.payload#>>'{authentication,actor}' IS DISTINCT FROM ap.actor
       OR jsonb_typeof(ap.rollback_ref) IS DISTINCT FROM 'object'
       OR nullif(btrim(subject), '') IS NULL
       OR jsonb_typeof(context) IS DISTINCT FROM 'object' THEN
        RETURN false;
    END IF;

    IF environment_name = 'test' AND current_database() !~* '_test$' THEN RETURN false; END IF;
    IF environment_name <> 'test' AND current_database() ~* '_test$' THEN RETURN false; END IF;
    IF provider = 'local_os' THEN
        IF environment_name = 'production' OR ap.source_system IS DISTINCT FROM 'cli'
           OR context->>'account' IS DISTINCT FROM ap.actor
           OR (
               (nullif(btrim(context->>'sid'), '') IS NOT NULL
                AND subject = (context->>'sid'))
               OR
               (jsonb_typeof(context->'uid') = 'number'
                AND context->>'uid' ~ '^(0|[1-9][0-9]*)$'
                AND subject = ('uid:' || (context->>'uid')))
           ) IS NOT TRUE THEN
            RETURN false;
        END IF;
    ELSIF provider = 'entra_oidc' THEN
        IF ap.source_system IS DISTINCT FROM 'web'
           OR nullif(btrim(context->>'issuer'), '') IS NULL
           OR nullif(btrim(context->>'tenant_id'), '') IS NULL
           OR nullif(btrim(context->>'object_id'), '') IS NULL
           OR subject IS DISTINCT FROM context->>'object_id' THEN
            RETURN false;
        END IF;
        IF environment_name = 'production' AND (
            policy.entra_issuer IS DISTINCT FROM context->>'issuer'
            OR policy.entra_tenant_id IS DISTINCT FROM context->>'tenant_id'
        ) THEN
            RETURN false;
        END IF;
    ELSE
        RETURN false;
    END IF;

    SELECT * INTO sv FROM artifacts
    WHERE artifact_id = ap.input_refs[1] AND artifact_type = 'skill_version';
    SELECT * INTO automated FROM artifacts
    WHERE artifact_id = ap.input_refs[2] AND artifact_type = 'review';
    SELECT * INTO content FROM artifacts
    WHERE artifact_id = ap.input_refs[3] AND artifact_type = 'review';
    IF sv.artifact_id IS NULL OR automated.artifact_id IS NULL OR content.artifact_id IS NULL THEN
        RETURN false;
    END IF;
    SELECT * INTO registry_entry FROM publication_skill_registry registered
    WHERE registered.slug = sv.payload->>'slug' AND registered.active;
    IF NOT FOUND THEN
        IF NOT (
            environment_name = 'test'
            AND policy.allow_unregistered_test_fixtures
            AND current_database() ~* '_test$'
        ) THEN
            RETURN false;
        END IF;
        judge_required_by_policy := true;
    ELSE
        IF registry_entry.role IS DISTINCT FROM sv.payload->>'role'
           OR registry_entry.level IS DISTINCT FROM sv.payload->>'level'
           OR registry_entry.permissions_label IS DISTINCT FROM sv.permissions_label THEN
            RETURN false;
        END IF;
        judge_required_by_policy := registry_entry.judge_required;
    END IF;
    fingerprint := skill_payload_sha256_v1(sv.payload);
    IF sv.payload->>'payload_sha256' IS DISTINCT FROM fingerprint
       OR NOT semiskill_semver_valid_v1(sv.payload->>'version')
       OR ap.payload#>>'{skill,slug}' IS DISTINCT FROM sv.payload->>'slug'
       OR ap.payload#>>'{skill,version}' IS DISTINCT FROM sv.payload->>'version'
       OR ap.payload#>>'{skill,payload_sha256}' IS DISTINCT FROM fingerprint
       OR ap.permissions_label IS DISTINCT FROM sv.permissions_label
       OR automated.permissions_label IS DISTINCT FROM sv.permissions_label
       OR content.permissions_label IS DISTINCT FROM sv.permissions_label
       OR coalesce(sv.timestamp_end, sv.timestamp_start) > automated.timestamp_start
       OR coalesce(sv.timestamp_end, sv.timestamp_start) > content.timestamp_start
       OR coalesce(automated.timestamp_end, automated.timestamp_start) > ap.timestamp_start
       OR coalesce(content.timestamp_end, content.timestamp_start) > ap.timestamp_start
       OR NOT content_review_ready_v1(content.artifact_id, sv.artifact_id) THEN
        RETURN false;
    END IF;
    IF decision = 'approve' AND ap.rollback_ref IS DISTINCT FROM jsonb_build_object(
        'action', 'unpublish',
        'skill_version_id', sv.artifact_id::text,
        'approval_id', ap.artifact_id::text
    ) THEN
        RETURN false;
    END IF;

    IF automated.payload->>'review_kind' IS DISTINCT FROM 'security_aggregate'
       OR automated.payload->>'schema_version' IS DISTINCT FROM '1'
       OR automated.payload->>'stage' IS DISTINCT FROM '6'
       OR automated.payload->>'verdict' IS DISTINCT FROM 'approve'
       OR cardinality(automated.input_refs) <> 6
       OR automated.input_refs[1] IS DISTINCT FROM sv.artifact_id
       OR jsonb_typeof(automated.payload->'scan_artifact_ids') IS DISTINCT FROM 'array'
       OR jsonb_typeof(ap.payload#>'{evidence,scan_artifact_ids}') IS DISTINCT FROM 'array'
       OR jsonb_typeof(automated.payload->'judge_required') IS DISTINCT FROM 'boolean'
       OR automated.eval_score IS NULL
       OR automated.eval_score IS DISTINCT FROM
          semiskill_number_v1(automated.payload->'aggregate_safety')
       OR semiskill_number_v1(automated.payload->'aggregate_safety') IS DISTINCT FROM
          round(semiskill_number_v1(automated.payload->'aggregate_safety'), 3) THEN
        RETURN false;
    END IF;
    SELECT coalesce(jsonb_agg(ref::text ORDER BY ordinality), '[]'::jsonb)
    INTO expected_scan_ids
    FROM unnest(automated.input_refs[2:6]) WITH ORDINALITY refs(ref, ordinality);
    IF automated.payload->'scan_artifact_ids' IS DISTINCT FROM expected_scan_ids
       OR ap.payload#>'{evidence,scan_artifact_ids}' IS DISTINCT FROM expected_scan_ids THEN
        RETURN false;
    END IF;
    judge_required := (automated.payload->>'judge_required')::boolean;
    IF judge_required IS DISTINCT FROM judge_required_by_policy THEN RETURN false; END IF;

    FOR scan_ref, scan_ordinal IN
        SELECT ref, ordinality
        FROM unnest(automated.input_refs[2:6]) WITH ORDINALITY refs(ref, ordinality)
    LOOP
        SELECT * INTO scan FROM artifacts WHERE artifact_id = scan_ref;
        IF NOT FOUND THEN RETURN false; END IF;
        stage := semiskill_positive_int_v1(scan.payload->'stage');
        safety := semiskill_number_v1(scan.payload->'safety_score');
        IF stage IS NULL OR stage NOT BETWEEN 1 AND 5 OR stage = ANY(seen_stages)
           OR scan.artifact_type IS DISTINCT FROM
              (CASE WHEN stage = 3 THEN 'injection_test'::artifact_type
                    ELSE 'scan_run'::artifact_type END)
           OR cardinality(scan.input_refs) <> 1
           OR scan.input_refs[1] IS DISTINCT FROM sv.artifact_id
           OR scan.permissions_label IS DISTINCT FROM sv.permissions_label
           OR coalesce(sv.timestamp_end, sv.timestamp_start) > scan.timestamp_start
           OR coalesce(scan.timestamp_end, scan.timestamp_start) > automated.timestamp_start
           OR scan.payload->>'status' NOT IN ('passed', 'failed', 'not_run', 'not_sampled')
           OR jsonb_typeof(scan.payload->'sampled') IS DISTINCT FROM 'boolean'
           OR jsonb_typeof(scan.payload->'hard_fail') IS DISTINCT FROM 'boolean'
           OR safety IS NULL OR safety < 0 OR safety > 1
           OR safety IS DISTINCT FROM round(safety, 3)
           OR scan.eval_score IS NULL OR scan.eval_score IS DISTINCT FROM safety THEN
            RETURN false;
        END IF;
        IF (
            scan.payload->>'status' IN ('passed', 'failed')
            AND scan.payload->'sampled' IS DISTINCT FROM 'true'::jsonb
        ) OR (
            scan.payload->>'status' IN ('not_run', 'not_sampled')
            AND scan.payload->'sampled' IS DISTINCT FROM 'false'::jsonb
        ) THEN
            RETURN false;
        END IF;
        seen_stages := array_append(seen_stages, stage);
        IF scan.payload->'hard_fail' IS DISTINCT FROM 'false'::jsonb THEN RETURN false; END IF;
        IF stage BETWEEN 1 AND 4 AND (
            scan.payload->>'status' IS DISTINCT FROM 'passed'
            OR scan.payload->'sampled' IS DISTINCT FROM 'true'::jsonb
        ) THEN
            RETURN false;
        END IF;
        IF stage = 5 AND (
            (judge_required AND (
                scan.payload->>'status' IS DISTINCT FROM 'passed'
                OR scan.payload->'sampled' IS DISTINCT FROM 'true'::jsonb
            )) OR
            (NOT judge_required AND NOT (
                (scan.payload->>'status' = 'passed' AND scan.payload->'sampled' = 'true'::jsonb)
                OR (scan.payload->>'status' = 'not_sampled'
                    AND scan.payload->'sampled' = 'false'::jsonb)
            ))
        ) THEN
            RETURN false;
        END IF;
        IF scan.payload->'sampled' = 'true'::jsonb THEN
            measured_min := CASE WHEN measured_min IS NULL THEN safety
                                 ELSE least(measured_min, safety) END;
        END IF;
    END LOOP;
    IF seen_stages @> ARRAY[1,2,3,4,5] IS NOT TRUE OR cardinality(seen_stages) <> 5
       OR measured_min IS NULL
       OR semiskill_number_v1(automated.payload->'aggregate_safety') IS DISTINCT FROM measured_min
       OR measured_min < policy.approve_threshold THEN
        RETURN false;
    END IF;

    IF decision = 'approve' AND EXISTS (
        SELECT 1 FROM verified_publication_events historical
        WHERE historical.decision = 'approve'
          AND historical.slug = sv.payload->>'slug'
          AND NOT semiskill_semver_greater_v1(
              sv.payload->>'version', historical.version
          )
    ) THEN
        RETURN false;
    END IF;

    IF decision = 'approve' AND ap.corrects_ref IS NOT NULL THEN
        SELECT * INTO parent_event FROM verified_publication_events parent
        WHERE parent.approval_id = ap.corrects_ref AND parent.decision = 'approve';
        IF NOT FOUND THEN RETURN false; END IF;
        SELECT * INTO parent_ap FROM artifacts WHERE artifact_id = parent_event.approval_id;
        IF parent_event.slug IS DISTINCT FROM sv.payload->>'slug'
           OR parent_event.permissions_label IS DISTINCT FROM ap.permissions_label
           OR NOT semiskill_semver_greater_v1(
               sv.payload->>'version', parent_event.version
           )
           OR ap.timestamp_start < coalesce(parent_ap.timestamp_end, parent_ap.timestamp_start) THEN
            RETURN false;
        END IF;
    ELSIF decision = 'unpublish' THEN
        IF ap.corrects_ref IS NULL THEN RETURN false; END IF;
        SELECT * INTO parent_event FROM verified_publication_events parent
        WHERE parent.approval_id = ap.corrects_ref AND parent.decision = 'approve';
        IF NOT FOUND THEN RETURN false; END IF;
        SELECT * INTO parent_ap FROM artifacts WHERE artifact_id = parent_event.approval_id;
        IF ap.input_refs IS DISTINCT FROM parent_ap.input_refs
           OR ap.payload->'skill' IS DISTINCT FROM parent_ap.payload->'skill'
           OR ap.payload->'evidence' IS DISTINCT FROM parent_ap.payload->'evidence'
           OR ap.rollback_ref IS DISTINCT FROM jsonb_build_object(
               'action', 'reapprove', 'approval_id', parent_event.approval_id::text
           )
           OR ap.permissions_label IS DISTINCT FROM parent_ap.permissions_label
           OR ap.timestamp_start < coalesce(parent_ap.timestamp_end, parent_ap.timestamp_start) THEN
            RETURN false;
        END IF;
    END IF;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION activate_verified_publication(approval_id_to_activate uuid)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    ap artifacts%ROWTYPE;
    existing verified_publication_events%ROWTYPE;
    policy publication_trust_policy%ROWTYPE;
    decision text;
    slug_value text;
    chain_material text;
BEGIN
    IF NOT pg_has_role(session_user, 'semiskill_approval_actuator', 'MEMBER') THEN
        RAISE EXCEPTION 'verified publication activation requires actuator role'
            USING ERRCODE = '42501';
    END IF;
    SELECT * INTO existing FROM verified_publication_events
    WHERE approval_id = approval_id_to_activate;
    IF FOUND THEN RETURN existing.approval_id; END IF;
    SELECT * INTO ap FROM artifacts WHERE artifact_id = approval_id_to_activate;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval does not satisfy the verified publication contract'
            USING ERRCODE = '23514';
    END IF;
    decision := ap.payload->>'decision';
    slug_value := ap.payload#>>'{skill,slug}';
    SELECT * INTO policy FROM publication_trust_policy configured
    WHERE configured.policy_id = true AND configured.enabled
      AND configured.database_name = current_database()
      AND configured.environment = ap.payload->>'environment'
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'publication environment policy is unavailable' USING ERRCODE = '23514';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(slug_value, 0));
    SELECT * INTO existing FROM verified_publication_events
    WHERE approval_id = approval_id_to_activate;
    IF FOUND THEN RETURN existing.approval_id; END IF;
    IF NOT approval_v1_projection_valid(approval_id_to_activate) THEN
        RAISE EXCEPTION 'approval does not satisfy the verified publication contract'
            USING ERRCODE = '23514';
    END IF;
    IF decision = 'approve' AND ap.corrects_ref IS NULL AND EXISTS (
        SELECT 1 FROM verified_publication_events active
        WHERE active.decision = 'approve' AND active.slug = slug_value
          AND NOT EXISTS (
              SELECT 1 FROM verified_publication_events child
              WHERE child.corrects_ref = active.approval_id
          )
    ) THEN
        RAISE EXCEPTION 'slug already has an active verified publication'
            USING ERRCODE = '23505';
    END IF;
    chain_material := semiskill_canonical_json_v1(ap.payload)
        || '|' || array_to_string(ap.input_refs, ',')
        || '|' || coalesce(ap.corrects_ref::text, '');
    INSERT INTO verified_publication_events (
        approval_id, skill_version_id, automated_review_id, content_review_id,
        corrects_ref, decision, slug, version, payload_sha256, permissions_label,
        environment, policy_version, approve_threshold, chain_sha256, activated_at, activated_by
    ) VALUES (
        ap.artifact_id, ap.input_refs[1], ap.input_refs[2], ap.input_refs[3],
        ap.corrects_ref, decision, slug_value, ap.payload#>>'{skill,version}',
        ap.payload#>>'{skill,payload_sha256}', ap.permissions_label,
        ap.payload->>'environment', policy.policy_version, policy.approve_threshold,
        encode(sha256(convert_to(
            chain_material || '|' || policy.policy_version || '|' || policy.approve_threshold::text,
            'UTF8'
        )), 'hex'),
        greatest(clock_timestamp(), coalesce(ap.timestamp_end, ap.timestamp_start)),
        session_user
    );
    RETURN ap.artifact_id;
END;
$$;

CREATE OR REPLACE FUNCTION validate_approval_v1() RETURNS trigger AS $$
DECLARE
    decision text;
    environment_name text;
    provider text;
    context jsonb;
    policy publication_trust_policy%ROWTYPE;
BEGIN
    IF NEW.artifact_type <> 'approval'
       OR NEW.payload->>'schema_version' IS DISTINCT FROM 'approval/v1' THEN
        RETURN NEW;
    END IF;
    decision := NEW.payload->>'decision';
    environment_name := NEW.payload->>'environment';
    provider := NEW.payload#>>'{authentication,provider}';
    context := NEW.payload#>'{authentication,context}';
    IF NEW.actor_kind <> 'human'
       OR NEW.objective_tag IS DISTINCT FROM 'safety'
       OR decision NOT IN ('approve', 'reject', 'unpublish')
       OR nullif(btrim(NEW.payload->>'reason'), '') IS NULL
       OR cardinality(NEW.input_refs) <> 3
       OR jsonb_typeof(NEW.payload->'published') IS DISTINCT FROM 'boolean'
       OR NEW.payload->'published' IS DISTINCT FROM
          (CASE WHEN decision = 'approve' THEN 'true'::jsonb ELSE 'false'::jsonb END)
       OR NEW.payload#>>'{skill,artifact_id}' IS DISTINCT FROM NEW.input_refs[1]::text
       OR NEW.payload#>>'{evidence,automated_review_id}' IS DISTINCT FROM NEW.input_refs[2]::text
       OR NEW.payload#>>'{evidence,content_review_id}' IS DISTINCT FROM NEW.input_refs[3]::text
       OR NEW.payload#>>'{authentication,actor}' IS DISTINCT FROM NEW.actor
       OR nullif(btrim(NEW.payload#>>'{authentication,subject}'), '') IS NULL
       OR jsonb_typeof(context) IS DISTINCT FROM 'object'
       OR environment_name NOT IN ('development', 'test', 'production')
       OR (decision = 'reject' AND NEW.corrects_ref IS NOT NULL)
       OR (decision = 'unpublish' AND NEW.corrects_ref IS NULL)
       OR NOT EXISTS (
           SELECT 1 FROM artifacts evidence
           WHERE evidence.artifact_id = NEW.input_refs[1]
             AND evidence.artifact_type = 'skill_version'
             AND evidence.permissions_label = NEW.permissions_label
       )
       OR NOT EXISTS (
           SELECT 1 FROM artifacts evidence
           WHERE evidence.artifact_id = NEW.input_refs[2]
             AND evidence.artifact_type = 'review'
             AND evidence.payload->>'review_kind' = 'security_aggregate'
             AND evidence.permissions_label = NEW.permissions_label
       )
       OR NOT EXISTS (
           SELECT 1 FROM artifacts evidence
           WHERE evidence.artifact_id = NEW.input_refs[3]
             AND evidence.artifact_type = 'review'
             AND evidence.payload->>'review_kind' = 'content_review'
             AND evidence.permissions_label = NEW.permissions_label
       ) THEN
        RAISE EXCEPTION 'approval/v1 violates its bound decision contract'
            USING ERRCODE = '23514';
    END IF;
    IF provider = 'local_os' THEN
        IF environment_name = 'production' OR NEW.source_system IS DISTINCT FROM 'cli'
           OR context->>'account' IS DISTINCT FROM NEW.actor OR (
            (nullif(btrim(context->>'sid'), '') IS NOT NULL
             AND (NEW.payload#>>'{authentication,subject}') = (context->>'sid'))
            OR
            (jsonb_typeof(context->'uid') = 'number'
             AND context->>'uid' ~ '^(0|[1-9][0-9]*)$'
             AND (NEW.payload#>>'{authentication,subject}') = ('uid:' || (context->>'uid')))
        ) IS NOT TRUE THEN
            RAISE EXCEPTION 'approval/v1 local identity is not OS-bound' USING ERRCODE = '23514';
        END IF;
    ELSIF provider = 'entra_oidc' THEN
        IF NEW.source_system IS DISTINCT FROM 'web'
           OR nullif(btrim(context->>'issuer'), '') IS NULL
           OR nullif(btrim(context->>'tenant_id'), '') IS NULL
           OR NEW.payload#>>'{authentication,subject}' IS DISTINCT FROM context->>'object_id' THEN
            RAISE EXCEPTION 'approval/v1 Entra identity is not claim-bound' USING ERRCODE = '23514';
        END IF;
    ELSE
        RAISE EXCEPTION 'approval/v1 identity provider is invalid' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO policy FROM publication_trust_policy configured
    WHERE configured.policy_id = true
      AND configured.enabled
      AND configured.database_name = current_database()
      AND configured.environment = environment_name;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval/v1 database environment policy is not configured'
            USING ERRCODE = '23514';
    END IF;
    IF environment_name = 'production' AND (
        provider IS DISTINCT FROM 'entra_oidc'
        OR policy.entra_issuer IS DISTINCT FROM context->>'issuer'
        OR policy.entra_tenant_id IS DISTINCT FROM context->>'tenant_id'
    ) THEN
        RAISE EXCEPTION 'approval/v1 Entra identity does not match database policy'
            USING ERRCODE = '23514';
    END IF;
    IF (environment_name = 'test') IS DISTINCT FROM (current_database() ~* '_test$') THEN
        RAISE EXCEPTION 'approval/v1 environment does not match database identity'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public;

CREATE OR REPLACE FUNCTION append_verified_approval(
    approval_id uuid,
    source source_system,
    approval_actor text,
    approval_actor_kind actor_kind,
    started_at timestamptz,
    ended_at timestamptz,
    approval_input_refs uuid[],
    approval_output_refs uuid[],
    approval_permissions_label text,
    approval_objective_tag text,
    approval_ground_truth_ref text,
    approval_eval_score numeric,
    approval_rollback_ref jsonb,
    approval_cost_usd numeric,
    approval_corrects_ref uuid,
    approval_payload jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    decision text;
    activated uuid;
    existing_approval_id uuid;
    slug_value text;
BEGIN
    IF NOT pg_has_role(session_user, 'semiskill_approval_actuator', 'MEMBER') THEN
        RAISE EXCEPTION 'approval append requires actuator role' USING ERRCODE = '42501';
    END IF;
    decision := approval_payload->>'decision';
    slug_value := approval_payload#>>'{skill,slug}';
    IF nullif(btrim(slug_value), '') IS NULL THEN
        RAISE EXCEPTION 'approval append requires a skill slug' USING ERRCODE = '23514';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(slug_value, 0));
    SELECT candidate.artifact_id INTO existing_approval_id
    FROM artifacts candidate
    WHERE candidate.artifact_type = 'approval'
      AND candidate.source_system = source
      AND candidate.actor = approval_actor
      AND candidate.actor_kind = approval_actor_kind
      AND candidate.input_refs = approval_input_refs
      AND candidate.output_refs = approval_output_refs
      AND candidate.permissions_label = approval_permissions_label
      AND candidate.objective_tag = approval_objective_tag
      AND candidate.ground_truth_ref IS NOT DISTINCT FROM approval_ground_truth_ref
      AND candidate.eval_score IS NOT DISTINCT FROM approval_eval_score
      AND candidate.cost_usd IS NOT DISTINCT FROM approval_cost_usd
      AND candidate.corrects_ref IS NOT DISTINCT FROM approval_corrects_ref
      AND candidate.payload->>'schema_version' IS NOT DISTINCT FROM approval_payload->>'schema_version'
      AND candidate.payload->>'decision' IS NOT DISTINCT FROM decision
      AND candidate.payload->>'reason' IS NOT DISTINCT FROM approval_payload->>'reason'
      AND candidate.payload->'skill' IS NOT DISTINCT FROM approval_payload->'skill'
      AND candidate.payload->'evidence' IS NOT DISTINCT FROM approval_payload->'evidence'
      AND candidate.payload->'authentication' IS NOT DISTINCT FROM approval_payload->'authentication'
      AND (
          decision NOT IN ('approve', 'unpublish')
          OR EXISTS (
              SELECT 1 FROM verified_publication_events projected
              WHERE projected.approval_id = candidate.artifact_id
          )
      )
    ORDER BY candidate.timestamp_start, candidate.artifact_id
    LIMIT 1;
    IF existing_approval_id IS NOT NULL THEN RETURN existing_approval_id; END IF;
    INSERT INTO artifacts (
        artifact_id, artifact_type, source_system, actor, actor_kind,
        timestamp_start, timestamp_end, input_refs, output_refs, permissions_label,
        objective_tag, ground_truth_ref, eval_score, rollback_ref, cost_usd,
        corrects_ref, payload
    ) VALUES (
        approval_id, 'approval', source, approval_actor, approval_actor_kind,
        started_at, ended_at, approval_input_refs, approval_output_refs,
        approval_permissions_label, approval_objective_tag, approval_ground_truth_ref,
        approval_eval_score, approval_rollback_ref, approval_cost_usd,
        approval_corrects_ref, approval_payload
    );
    IF decision IN ('approve', 'unpublish') THEN
        activated := activate_verified_publication(approval_id);
        IF activated IS DISTINCT FROM approval_id THEN
            RAISE EXCEPTION 'verified publication actuator did not confirm approval'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN approval_id;
END;
$$;

CREATE OR REPLACE FUNCTION verified_active_publication_heads_v1()
RETURNS TABLE (
    approval_id uuid, skill_version_id uuid, automated_review_id uuid,
    content_review_id uuid, slug text, permissions_label text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH active AS (
        SELECT event.*
        FROM verified_publication_events event
        JOIN artifacts approval ON approval.artifact_id = event.approval_id
            AND approval.artifact_type = 'approval'
        JOIN artifacts skill ON skill.artifact_id = event.skill_version_id
            AND skill.artifact_type = 'skill_version'
        JOIN artifacts automated ON automated.artifact_id = event.automated_review_id
            AND automated.artifact_type = 'review'
        JOIN artifacts content ON content.artifact_id = event.content_review_id
            AND content.artifact_type = 'review'
        WHERE event.decision = 'approve'
          AND approval.input_refs = ARRAY[
              event.skill_version_id, event.automated_review_id, event.content_review_id
          ]::uuid[]
          AND approval.corrects_ref IS NOT DISTINCT FROM event.corrects_ref
          AND approval.payload->>'decision' = event.decision
          AND approval.payload#>>'{skill,slug}' = event.slug
          AND approval.payload#>>'{skill,version}' = event.version
          AND approval.payload#>>'{skill,payload_sha256}' = event.payload_sha256
          AND approval.payload->>'environment' = event.environment
          AND approval.permissions_label = event.permissions_label
          AND skill.payload->>'slug' = event.slug
          AND skill.payload->>'version' = event.version
          AND skill.payload->>'payload_sha256' = event.payload_sha256
          AND skill_payload_sha256_v1(skill.payload) = event.payload_sha256
          AND skill.permissions_label = event.permissions_label
          AND automated.permissions_label = event.permissions_label
          AND content.permissions_label = event.permissions_label
          AND event.chain_sha256 = encode(sha256(convert_to(
              semiskill_canonical_json_v1(approval.payload)
              || '|' || array_to_string(approval.input_refs, ',')
              || '|' || coalesce(approval.corrects_ref::text, '')
              || '|' || event.policy_version
              || '|' || event.approve_threshold::text,
              'UTF8'
          )), 'hex')
          AND NOT EXISTS (
              SELECT 1 FROM verified_publication_events child
              WHERE child.corrects_ref = event.approval_id
          )
    ), counted AS (
        SELECT active.*, count(*) OVER (PARTITION BY active.slug) AS head_count
        FROM active
    )
    SELECT counted.approval_id, counted.skill_version_id, counted.automated_review_id,
           counted.content_review_id, counted.slug, counted.permissions_label
    FROM counted
    WHERE counted.head_count = 1;
$$;

CREATE OR REPLACE FUNCTION publication_registry_entry_v1(target_slug text)
RETURNS TABLE (
    slug text, role text, level text, permissions_label text,
    active boolean, judge_required boolean, registry_sha256 text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT registered.slug, registered.role, registered.level,
           registered.permissions_label, registered.active,
           registered.judge_required, registered.registry_sha256
    FROM publication_skill_registry registered
    WHERE registered.slug = target_slug;
$$;

CREATE OR REPLACE FUNCTION semiskill_effective_labels_v1(requested text[])
RETURNS text[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT CASE
        WHEN current_setting('role', true) = 'semiskill_acl_reader'
             AND pg_has_role(session_user, 'semiskill_acl_reader', 'MEMBER') THEN
            coalesce(ARRAY(
                SELECT DISTINCT label
                FROM unnest(coalesce(requested, ARRAY[]::text[])) label
                WHERE label IN ('public', 'team', 'need-to-know', 'regulated')
                ORDER BY label
            ), ARRAY[]::text[])
        ELSE ARRAY['public']::text[]
    END;
$$;

CREATE OR REPLACE FUNCTION artifact_get(target uuid, allowed_labels text[])
RETURNS TABLE (
    artifact_id uuid, artifact_type artifact_type, source_system source_system,
    permissions_label text, objective_tag text, eval_score numeric, payload jsonb
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH effective AS (
        SELECT semiskill_effective_labels_v1(allowed_labels) AS labels
    )
    SELECT artifact.artifact_id, artifact.artifact_type, artifact.source_system,
           artifact.permissions_label, artifact.objective_tag, artifact.eval_score,
           artifact.payload
    FROM effective
    CROSS JOIN artifacts artifact
    WHERE artifact.artifact_id = target
      AND artifact.permissions_label = ANY(effective.labels);
$$;

CREATE OR REPLACE FUNCTION catalog_search(
    q text, allowed_labels text[],
    f_function text DEFAULT NULL, f_role text DEFAULT NULL, f_level text DEFAULT NULL,
    limit_n int DEFAULT 100)
RETURNS TABLE (artifact_id uuid, slug text, name text, description text, version text,
               skill_function text, skill_role text, skill_level text,
               permissions_label text, payload jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH effective AS (
        SELECT semiskill_effective_labels_v1(allowed_labels) AS labels
    )
    SELECT sv.artifact_id,
           sv.payload->>'slug', sv.payload->>'name', sv.payload->>'description',
           sv.payload->>'version', sv.payload->>'function', sv.payload->>'role',
           sv.payload->>'level', sv.permissions_label, sv.payload
    FROM effective
    CROSS JOIN verified_active_publication_heads_v1() head
    JOIN artifacts sv ON sv.artifact_id = head.skill_version_id
    WHERE head.permissions_label = ANY(effective.labels)
      AND sv.artifact_type = 'skill_version'
      AND sv.permissions_label = ANY(effective.labels)
      AND (f_function IS NULL OR sv.payload->>'function' = f_function)
      AND (f_role IS NULL OR sv.payload->>'role' = f_role)
      AND (f_level IS NULL OR sv.payload->>'level' = f_level)
      AND (q IS NULL OR q = '' OR sv.payload->>'name' ILIKE '%' || q || '%'
           OR sv.payload->>'slug' ILIKE '%' || q || '%'
           OR sv.payload->>'description' ILIKE '%' || q || '%'
           OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(
                      coalesce(sv.payload->'tags', '[]'::jsonb)) tag
                      WHERE tag ILIKE '%' || q || '%'))
    ORDER BY sv.payload->>'slug'
    LIMIT greatest(0, least(coalesce(limit_n, 100), 1000));
$$;

CREATE OR REPLACE FUNCTION skill_scan_report(skill_id uuid, allowed_labels text[])
RETURNS TABLE (verdict text, aggregate_safety numeric, stages jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH effective AS (
        SELECT semiskill_effective_labels_v1(allowed_labels) AS labels
    ), projected AS (
        SELECT head.*
        FROM effective
        CROSS JOIN verified_active_publication_heads_v1() head
        WHERE head.skill_version_id = skill_id
          AND head.permissions_label = ANY(effective.labels)
    ), automated AS (
        SELECT review.* FROM projected
        JOIN artifacts review ON review.artifact_id = projected.automated_review_id
        CROSS JOIN effective
        WHERE review.permissions_label = ANY(effective.labels)
    ), frozen_stages AS (
        SELECT coalesce(jsonb_agg(jsonb_build_object(
            'artifact_id', scan.artifact_id, 'stage', scan.payload->'stage',
            'status', scan.payload->'status', 'sampled', scan.payload->'sampled',
            'safety', scan.payload->'safety_score', 'hard_fail', scan.payload->'hard_fail'
        ) ORDER BY refs.ordinality), '[]'::jsonb) AS value
        FROM automated
        CROSS JOIN effective
        CROSS JOIN LATERAL unnest(automated.input_refs[2:6])
            WITH ORDINALITY refs(scan_id, ordinality)
        JOIN artifacts scan ON scan.artifact_id = refs.scan_id
        WHERE scan.permissions_label = ANY(effective.labels)
    )
    SELECT automated.payload->>'verdict',
           semiskill_number_v1(automated.payload->'aggregate_safety'),
           frozen_stages.value
    FROM automated CROSS JOIN frozen_stages;
$$;

CREATE OR REPLACE FUNCTION lineage(start uuid, allowed_labels text[], max_depth int)
RETURNS TABLE (artifact_id uuid, artifact_type artifact_type, permissions_label text,
               payload jsonb, depth int, parent_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH RECURSIVE effective AS (
        SELECT semiskill_effective_labels_v1(allowed_labels) AS labels
    ), published_starts AS (
        SELECT head.approval_id AS artifact_id
        FROM verified_active_publication_heads_v1() head
      UNION
        SELECT head.skill_version_id FROM verified_active_publication_heads_v1() head
      UNION
        SELECT head.automated_review_id FROM verified_active_publication_heads_v1() head
      UNION
        SELECT head.content_review_id FROM verified_active_publication_heads_v1() head
      UNION
        SELECT scans.scan_ref
        FROM verified_active_publication_heads_v1() head
        JOIN artifacts automated ON automated.artifact_id = head.automated_review_id
        CROSS JOIN LATERAL unnest(automated.input_refs[2:6]) AS scans(scan_ref)
    ), walk(artifact_id, parent_id, depth) AS (
        SELECT artifact.artifact_id, NULL::uuid, 0
        FROM effective
        CROSS JOIN artifacts artifact
        WHERE artifact.artifact_id = start
          AND EXISTS (
              SELECT 1 FROM published_starts published
              WHERE published.artifact_id = artifact.artifact_id
          )
          AND artifact.permissions_label = ANY(effective.labels)
      UNION
        SELECT child.artifact_id, walked.artifact_id, walked.depth + 1
        FROM walk walked
        JOIN artifacts parent ON parent.artifact_id = walked.artifact_id
        CROSS JOIN LATERAL unnest(parent.input_refs) AS ref(id)
        JOIN artifacts child ON child.artifact_id = ref.id
        CROSS JOIN effective
        WHERE walked.depth < greatest(0, least(coalesce(max_depth, 0), 100))
          AND child.permissions_label = ANY(effective.labels)
    )
    SELECT walked.artifact_id, artifact.artifact_type, artifact.permissions_label,
           artifact.payload, walked.depth, walked.parent_id
    FROM walk walked JOIN artifacts artifact USING (artifact_id);
$$;

CREATE OR REPLACE FUNCTION reuse_events_for_skill(skill_id uuid, allowed_labels text[])
RETURNS TABLE (artifact_id uuid, actor text, method text, ts timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    WITH effective AS (
        SELECT semiskill_effective_labels_v1(allowed_labels) AS labels
    ), visible AS (
        SELECT 1
        FROM effective
        CROSS JOIN verified_active_publication_heads_v1() head
        JOIN artifacts skill ON skill.artifact_id = head.skill_version_id
        WHERE head.skill_version_id = skill_id
          AND skill.artifact_type = 'skill_version'
          AND head.permissions_label = ANY(effective.labels)
          AND skill.permissions_label = ANY(effective.labels)
    )
    SELECT reuse.artifact_id, reuse.actor, reuse.payload->>'method', reuse.timestamp_start
    FROM effective
    CROSS JOIN artifacts reuse
    WHERE EXISTS (SELECT 1 FROM visible)
      AND reuse.artifact_type = 'reuse_event'
      AND skill_id = ANY(reuse.input_refs)
      AND reuse.permissions_label = ANY(effective.labels)
    ORDER BY reuse.timestamp_start;
$$;

REVOKE ALL ON FUNCTION semiskill_canonical_json_v1(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION skill_payload_sha256_v1(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION semiskill_positive_int_v1(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION semiskill_number_v1(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION semiskill_semver_valid_v1(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION semiskill_semver_greater_v1(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION content_review_ready_v1(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION approval_v1_projection_valid(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION activate_verified_publication(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION append_verified_approval(
    uuid, source_system, text, actor_kind, timestamptz, timestamptz, uuid[], uuid[],
    text, text, text, numeric, jsonb, numeric, uuid, jsonb
) FROM PUBLIC;
REVOKE ALL ON FUNCTION verified_active_publication_heads_v1() FROM PUBLIC;
REVOKE ALL ON FUNCTION publication_registry_entry_v1(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION semiskill_effective_labels_v1(text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION artifact_get(uuid, text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION lineage(uuid, text[], int) FROM PUBLIC;
REVOKE ALL ON FUNCTION reuse_events_for_skill(uuid, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION activate_verified_publication(uuid) TO semiskill_approval_actuator;
GRANT EXECUTE ON FUNCTION append_verified_approval(
    uuid, source_system, text, actor_kind, timestamptz, timestamptz, uuid[], uuid[],
    text, text, text, numeric, jsonb, numeric, uuid, jsonb
) TO semiskill_approval_actuator;
GRANT EXECUTE ON FUNCTION publication_registry_entry_v1(text)
TO semiskill_app, semiskill_submitter, semiskill_approval_actuator;
GRANT EXECUTE ON FUNCTION catalog_search(text, text[], text, text, text, int) TO semiskill_app;
GRANT EXECUTE ON FUNCTION skill_scan_report(uuid, text[]) TO semiskill_app;
GRANT EXECUTE ON FUNCTION artifact_get(uuid, text[]) TO semiskill_app;
GRANT EXECUTE ON FUNCTION catalog_search(text, text[], text, text, text, int)
TO semiskill_acl_reader;
GRANT EXECUTE ON FUNCTION skill_scan_report(uuid, text[]) TO semiskill_acl_reader;
GRANT EXECUTE ON FUNCTION artifact_get(uuid, text[]) TO semiskill_acl_reader;
GRANT EXECUTE ON FUNCTION lineage(uuid, text[], int) TO semiskill_acl_reader;
GRANT EXECUTE ON FUNCTION reuse_events_for_skill(uuid, text[]) TO semiskill_acl_reader;
