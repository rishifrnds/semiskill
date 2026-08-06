-- Extend approval/v1 with an authenticated append-only unpublish correction. Kept separate from
-- 0009 because migrations are immutable once applied.
CREATE OR REPLACE FUNCTION validate_approval_v1() RETURNS trigger AS $$
DECLARE
    skill_id uuid;
    automated_id uuid;
    content_id uuid;
    decision text;
    provider text;
BEGIN
    IF NEW.artifact_type <> 'approval'
       OR NEW.payload->>'schema_version' IS DISTINCT FROM 'approval/v1' THEN
        RETURN NEW;
    END IF;
    IF NEW.actor_kind <> 'human' THEN
        RAISE EXCEPTION 'approval/v1 actor_kind must be human';
    END IF;
    decision := NEW.payload->>'decision';
    IF decision NOT IN ('approve', 'reject', 'unpublish') THEN
        RAISE EXCEPTION 'approval/v1 decision must be approve, reject, or unpublish';
    END IF;
    IF nullif(btrim(NEW.payload->>'reason'), '') IS NULL THEN
        RAISE EXCEPTION 'approval/v1 reason is required';
    END IF;
    provider := NEW.payload#>>'{authentication,provider}';
    IF provider NOT IN ('local_os', 'entra_oidc')
       OR nullif(btrim(NEW.payload#>>'{authentication,subject}'), '') IS NULL THEN
        RAISE EXCEPTION 'approval/v1 authenticated subject/provider is required';
    END IF;
    IF cardinality(NEW.input_refs) <> 3 THEN
        RAISE EXCEPTION 'approval/v1 requires exact skill, automated review, content review refs';
    END IF;
    skill_id := (NEW.payload#>>'{skill,artifact_id}')::uuid;
    automated_id := (NEW.payload#>>'{evidence,automated_review_id}')::uuid;
    content_id := (NEW.payload#>>'{evidence,content_review_id}')::uuid;
    IF NEW.input_refs[1] <> skill_id OR NEW.input_refs[2] <> automated_id
       OR NEW.input_refs[3] <> content_id THEN
        RAISE EXCEPTION 'approval/v1 payload refs disagree with input_refs';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM artifacts WHERE artifact_id=skill_id
                   AND artifact_type='skill_version')
       OR NOT EXISTS (SELECT 1 FROM artifacts WHERE artifact_id=automated_id
                      AND artifact_type='review' AND payload->>'review_kind'='security_aggregate')
       OR NOT EXISTS (SELECT 1 FROM artifacts WHERE artifact_id=content_id
                      AND artifact_type='review' AND payload->>'review_kind'='content_review') THEN
        RAISE EXCEPTION 'approval/v1 evidence artifact types are invalid';
    END IF;
    IF ((NEW.payload->>'published')::boolean) IS DISTINCT FROM (decision = 'approve') THEN
        RAISE EXCEPTION 'approval/v1 published state disagrees with decision';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
