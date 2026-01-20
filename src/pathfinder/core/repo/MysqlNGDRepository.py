import ast
from typing import List, Tuple, Optional

import mysql.connector
from mysql.connector import Error

from pathfinder.core.repo.mysql_config_utility import parse_mysql_config

class MysqlNGDRepository:

    @classmethod
    def from_config_string(cls, config_str: str) -> "MysqlNGDRepository":
        cfg = parse_mysql_config(config_str)

        return cls(
            host=cfg.host,
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            port=cfg.port,
            ssl_required=cfg.ssl_required,
        )

    def __init__(
        self,
        host: str = "arax-databases-mysql.rtx.ai",
        user: str = "public_ro",
        password: Optional[str] = None,
        database: str = "curie_ngd_v1_0_kg2_10_2",
        port: int = 3306,
        ssl_required: bool = True,
        connect_timeout: int = 10,
    ):
        self._conn = self._connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            ssl_required=ssl_required,
            connect_timeout=connect_timeout,
        )

    def _connect(self, **kwargs):
        ssl_required = kwargs.pop("ssl_required", True)
        try:
            conn = mysql.connector.connect(
                **kwargs,
                ssl_disabled=not ssl_required,
                autocommit=True,
            )
            return conn
        except Error as e:
            raise RuntimeError(f"MySQL connection failed: {e}")

    def close(self):
        try:
            if self._conn and self._conn.is_connected():
                self._conn.close()
        except Exception:
            pass

    def _ensure_connection(self):
        if not self._conn or not self._conn.is_connected():
            raise RuntimeError("MySQL connection is not available.")

    def get_curie_ngd(self, curie: str) -> List:
        self._ensure_connection()
        try:
            with self._conn.cursor() as cursor:
                query = "SELECT ngd FROM curie_ngd WHERE curie = %s"
                cursor.execute(query, (curie,))
                row = cursor.fetchone()
        except Exception as e:
            raise Exception(f"{e}, mysql host: {self._conn.server_host if hasattr(self._conn,'server_host') else 'unknown'}")

        if row and row[0] is not None:
            return ast.literal_eval(row[0])

        return []

    def get_curies_pmid_length(self, curies: List[str], limit: int = -1) -> List[Tuple[str, int]]:
        self._ensure_connection()
        if not curies:
            return []

        placeholders = ",".join(["%s"] * len(curies))

        if limit != -1:
            query = f"""
                SELECT curie, pmid_length
                FROM curie_ngd
                WHERE curie IN ({placeholders})
                ORDER BY pmid_length DESC
                LIMIT %s
            """
            params = tuple(curies) + (limit,)
        else:
            query = f"""
                SELECT curie, pmid_length
                FROM curie_ngd
                WHERE curie IN ({placeholders})
                ORDER BY pmid_length DESC
            """
            params = tuple(curies)

        try:
            with self._conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return rows
        except Exception as e:
            raise Exception(f"{e}, mysql query failed")
