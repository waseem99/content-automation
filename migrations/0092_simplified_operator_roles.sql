-- Present three simple roles in Creator Studio while preserving the internal
-- producer/publisher capability rows required by existing workflow services.

BEGIN;

ALTER TABLE football_brief.operator_user_roles
    DROP CONSTRAINT operator_user_roles_role_check;

ALTER TABLE football_brief.operator_user_roles
    ADD CONSTRAINT operator_user_roles_role_check
    CHECK (role IN ('super_admin', 'admin', 'reviewer', 'producer', 'publisher'));

-- Existing producers and publishers become reviewers in the simplified model.
INSERT INTO football_brief.operator_user_roles
    (operator_user_id, role, assigned_by)
SELECT DISTINCT operator_user_id, 'reviewer', 'migration-0092'
FROM football_brief.operator_user_roles
WHERE role IN ('producer', 'publisher')
ON CONFLICT DO NOTHING;

-- Admin must genuinely be able to complete every current workflow, including
-- services that still enforce the historical exact producer/publisher roles.
INSERT INTO football_brief.operator_user_roles
    (operator_user_id, role, assigned_by)
SELECT operator_user_id, capability.role, 'migration-0092'
FROM football_brief.operator_user_roles admins
CROSS JOIN (VALUES ('reviewer'), ('producer'), ('publisher')) AS capability(role)
WHERE admins.role = 'admin'
ON CONFLICT DO NOTHING;

COMMENT ON TABLE football_brief.operator_user_roles IS
    'Public roles are super_admin, admin and reviewer. Producer and publisher are retained as internal compatibility capabilities.';

COMMIT;
