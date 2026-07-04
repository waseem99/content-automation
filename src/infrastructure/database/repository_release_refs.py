from psycopg import Connection


class ReleaseReferenceRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn
