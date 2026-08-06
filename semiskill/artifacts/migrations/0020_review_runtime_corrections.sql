-- Forward corrections for runtime-only defects found after 0019 was checksum-tracked.

-- Parenthesize JSON extraction before text concatenation and enforce the shared 64-attempt bound.
DO $$
DECLARE
    definition text;
    corrected text;
BEGIN
    SELECT pg_get_functiondef(
        'public.append_verified_review_contract(uuid,source_system,text,actor_kind,timestamptz,'
        'timestamptz,uuid[],uuid[],text,text,text,numeric,jsonb,numeric,uuid,jsonb)'::regprocedure
    ) INTO definition;
    corrected := replace(
        replace(
            replace(
                definition,
                'contract_payload->>''batch_id''',
                '(contract_payload->>''batch_id'')'
            ),
            'contract_payload->>''run_id''',
            '(contract_payload->>''run_id'')'
        ),
        'IF attempt_value IS NULL',
        'IF attempt_value IS NULL OR attempt_value > 64'
    );
    IF corrected = definition THEN
        RAISE EXCEPTION 'unexpected review-contract wrapper definition';
    END IF;
    EXECUTE corrected;
END
$$;

-- The actual mutating function also carries the membership check, so its owner cannot bypass the
-- public wrapper merely by invoking the renamed implementation directly.
DO $$
DECLARE
    definition text;
    corrected text;
    needle text := E'BEGIN\n    IF contract_source <> ''cli''';
    replacement text := E'BEGIN\n'
        '    IF NOT pg_has_role(session_user, ''semiskill_review_coordinator'', ''MEMBER'') THEN\n'
        '        RAISE EXCEPTION ''review contract issuance requires the coordinator capability''\n'
        '            USING ERRCODE = ''42501'';\n'
        '    END IF;\n'
        '    IF jsonb_typeof(contract_payload->''cells'') IS DISTINCT FROM ''array''\n'
        '       OR jsonb_array_length(contract_payload->''cells'') <> 1 THEN\n'
        '        RAISE EXCEPTION ''review contract authority requires one skill lease''\n'
        '            USING ERRCODE = ''23514'';\n'
        '    END IF;\n'
        '    IF contract_source <> ''cli''';
BEGIN
    SELECT pg_get_functiondef(
        'public.append_verified_review_contract_v1_internal(uuid,source_system,text,actor_kind,'
        'timestamptz,timestamptz,uuid[],uuid[],text,text,text,numeric,jsonb,numeric,uuid,jsonb)'
        ::regprocedure
    ) INTO definition;
    corrected := replace(definition, needle, replacement);
    IF corrected = definition THEN
        RAISE EXCEPTION 'unexpected internal review-contract actuator definition';
    END IF;
    EXECUTE corrected;
END
$$;

DO $$
DECLARE
    definition text;
    corrected text;
BEGIN
    SELECT pg_get_functiondef(
        'public.validate_content_review_v3_policy()'::regprocedure
    ) INTO definition;
    corrected := replace(
        definition,
        'OR attempt_value IS NULL',
        'OR attempt_value IS NULL OR attempt_value > 64'
    );
    IF corrected = definition THEN
        RAISE EXCEPTION 'unexpected content-review policy definition';
    END IF;
    EXECUTE corrected;
END
$$;

DO $$
DECLARE
    definition text;
    corrected text;
BEGIN
    SELECT pg_get_functiondef(
        'public.content_review_publication_safe_v1(uuid)'::regprocedure
    ) INTO definition;
    corrected := replace(
        definition,
        'IF expected_attempt IS NULL OR expected_attempt < 2',
        'IF expected_attempt IS NULL OR expected_attempt < 2 OR expected_attempt > 64'
    );
    IF corrected = definition THEN
        RAISE EXCEPTION 'unexpected publication review-chain validator definition';
    END IF;
    EXECUTE corrected;
END
$$;

DO $$
DECLARE
    governed record;
BEGIN
    FOR governed IN
        SELECT p.oid::pg_catalog.regprocedure AS signature
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prosecdef
        ORDER BY p.oid::regprocedure::text
    LOOP
        EXECUTE pg_catalog.format(
            'ALTER FUNCTION %s SET search_path = pg_catalog, public, pg_temp',
            governed.signature
        );
    END LOOP;
END
$$;
