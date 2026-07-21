-- Football Brief operator identities, roles, and brand assignments.
-- API keys remain outside PostgreSQL; this migration stores only named access records.

BEGIN;

CREATE TABLE football_brief.operator_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id text NOT NULL UNIQUE CHECK (operator_id ~ '^[A-Za-z0-9._-]{3,120}$'),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 200),
    active boolean NOT NULL DEFAULT true,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER operator_users_touch_updated_at
BEFORE UPDATE ON football_brief.operator_users
FOR EACH ROW EXECUTE FUNCTION football_brief.touch_updated_at();

CREATE TABLE football_brief.operator_user_roles (
    operator_user_id uuid NOT NULL REFERENCES football_brief.operator_users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('admin', 'reviewer', 'producer', 'publisher')),
    assigned_by text NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (operator_user_id, role)
);

CREATE TABLE football_brief.operator_brand_assignments (
    operator_user_id uuid NOT NULL REFERENCES football_brief.operator_users(id) ON DELETE CASCADE,
    brand_id uuid NOT NULL REFERENCES football_brief.brands(id) ON DELETE CASCADE,
    assigned_by text NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (operator_user_id, brand_id)
);

CREATE INDEX operator_user_roles_role_idx
ON football_brief.operator_user_roles (role, operator_user_id);

CREATE INDEX operator_brand_assignments_brand_idx
ON football_brief.operator_brand_assignments (brand_id, operator_user_id);

COMMENT ON TABLE football_brief.operator_users IS
    'Named operators. Authentication secrets are external; inactive operators fail closed.';
COMMENT ON TABLE football_brief.operator_user_roles IS
    'Application roles used for least-privilege action checks.';
COMMENT ON TABLE football_brief.operator_brand_assignments IS
    'Brand scope for non-admin operators. Admins are portfolio-wide.';

COMMIT;
