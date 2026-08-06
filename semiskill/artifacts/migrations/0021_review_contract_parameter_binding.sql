-- Qualify the actuator parameter where projection tables also expose contract_id.
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
            definition,
            'WHERE projected.contract_id = contract_id',
            'WHERE projected.contract_id = append_verified_review_contract.contract_id'
        ),
        'prior_contract.artifact_id <> contract_id',
        'prior_contract.artifact_id <> append_verified_review_contract.contract_id'
    );
    IF corrected = definition THEN
        RAISE EXCEPTION 'unexpected review-contract parameter binding';
    END IF;
    EXECUTE corrected;
END
$$;
