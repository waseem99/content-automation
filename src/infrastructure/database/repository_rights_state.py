from psycopg import Connection


class RightsStateRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn
