from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.content_models import ContentItem, ContentItemCreate
from src.infrastructure.database.repository_base import BaseRepository


class ContentItemRepository(BaseRepository[ContentItem]):
    def create(self, data: ContentItemCreate) -> ContentItem:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.content_items (
                slug, working_title, lifecycle_status, primary_platform,
                content_format, created_by, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.slug,
                data.working_title,
                data.lifecycle_status,
                data.primary_platform,
                data.content_format,
                data.created_by,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, ContentItem, "content item")

    def get(self, content_item_id: UUID) -> ContentItem:
        row = self.conn.execute(
            "SELECT * FROM football_brief.content_items WHERE id = %s",
            (content_item_id,),
        ).fetchone()
        return self.required(row, ContentItem, "content item")

    def get_by_slug(self, slug: str) -> ContentItem | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.content_items WHERE slug = %s",
            (slug,),
        ).fetchone()
        return ContentItem.model_validate(row) if row else None
