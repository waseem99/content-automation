-- Operational review workspace for scripts, narration, storyboards, and local previews.

BEGIN;

CREATE TABLE football_brief.portfolio_content_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_content_id uuid NOT NULL REFERENCES football_brief.portfolio_content(id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN (
        'voiceover', 'keyframe', 'preview', 'premium_clip', 'thumbnail', 'final_video', 'package'
    )),
    label text NOT NULL,
    version integer NOT NULL CHECK (version >= 1),
    local_locator text NOT NULL,
    mime_type text NOT NULL,
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    size_bytes bigint CHECK (size_bytes IS NULL OR size_bytes >= 0),
    review_status text NOT NULL DEFAULT 'pending' CHECK (
        review_status IN ('pending', 'approved', 'changes_requested', 'rejected', 'superseded')
    ),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (portfolio_content_id, kind, version, local_locator),
    CHECK (local_locator ~ '^content://[A-Za-z0-9._/-]+$')
);

CREATE INDEX portfolio_content_artifacts_review_idx
    ON football_brief.portfolio_content_artifacts (portfolio_content_id, kind, version, created_at DESC);

COMMENT ON TABLE football_brief.portfolio_content_artifacts IS
    'Metadata for locally stored review media. The operator API resolves content:// locators only inside its configured media root.';

COMMIT;
