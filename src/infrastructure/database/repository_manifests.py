from psycopg import Connection


class RenderManifestRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn
