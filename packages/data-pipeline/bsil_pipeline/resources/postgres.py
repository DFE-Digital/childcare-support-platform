from contextlib import contextmanager

import psycopg
from dagster import ConfigurableResource


class BsilPostgresResource(ConfigurableResource):
    host: str
    port: int = 5432
    user: str
    password: str
    dbname: str

    @contextmanager
    def get_connection(self):
        conn = psycopg.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.dbname,
            autocommit=False,
        )
        try:
            yield conn
        finally:
            conn.close()
