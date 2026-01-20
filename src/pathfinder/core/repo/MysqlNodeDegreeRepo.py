import json
from typing import Dict, List, Set, Optional

import mysql.connector
from mysql.connector import Error
from pathfinder.core.repo.mysql_config_utility import parse_mysql_config


class MysqlNodeDegreeRepo:

    @classmethod
    def from_config_string(cls, config_str: str) -> "MysqlNodeDegreeRepo":
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

    def get_node_degree(self, node_id: str) -> int:
        self._ensure_connection()
        try:
            with self._conn.cursor() as cursor:
                query = "SELECT neighbor_counts FROM neighbors WHERE id = %s"
                cursor.execute(query, (node_id,))
                result = cursor.fetchone()
        except Exception as e:
            raise Exception(f"{e}, mysql query failed (get_node_degree)")

        if result and result[0]:
            # neighbor_counts may come back as str, bytes, or dict depending on column type/driver settings
            neighbor_counts = result[0]
            if isinstance(neighbor_counts, (bytes, bytearray)):
                neighbor_counts = neighbor_counts.decode("utf-8")

            if isinstance(neighbor_counts, str):
                degree_by_biolink_type = json.loads(neighbor_counts)
            elif isinstance(neighbor_counts, dict):
                degree_by_biolink_type = neighbor_counts
            else:
                # last resort
                degree_by_biolink_type = json.loads(str(neighbor_counts))

            return int(degree_by_biolink_type.get("biolink:NamedThing", 0))

        return 0

    def get_degrees_by_node(self, curie_ids: List[str], batch_size: int = 10000) -> Dict[str, dict]:
        self._ensure_connection()
        if not curie_ids:
            return {}

        degree_dict: Dict[str, dict] = {}

        try:
            with self._conn.cursor() as cursor:
                for i in range(0, len(curie_ids), batch_size):
                    batch_ids = curie_ids[i : i + batch_size]
                    placeholders = ",".join(["%s"] * len(batch_ids))
                    query = f"""
                        SELECT id, neighbor_counts
                        FROM neighbors
                        WHERE id IN ({placeholders})
                    """
                    cursor.execute(query, tuple(batch_ids))

                    for node_id, neighbor_counts in cursor.fetchall():
                        if isinstance(neighbor_counts, (bytes, bytearray)):
                            neighbor_counts = neighbor_counts.decode("utf-8")

                        if isinstance(neighbor_counts, str):
                            degree_by_biolink_type = json.loads(neighbor_counts)
                        elif isinstance(neighbor_counts, dict):
                            degree_by_biolink_type = neighbor_counts
                        else:
                            degree_by_biolink_type = json.loads(str(neighbor_counts))

                        degree_dict[node_id] = degree_by_biolink_type

        except Exception as e:
            raise Exception(f"{e}, mysql query failed (get_degrees_by_node)")

        for curie in curie_ids:
            degree_dict.setdefault(curie, {})

        return degree_dict

    def get_degree_categories(self, batch_size: int = 10000) -> Set[str]:
        self._ensure_connection()

        degree_category_set: Set[str] = set()
        offset = 0

        try:
            with self._conn.cursor() as cursor:
                while True:
                    query = f"""
                        SELECT neighbor_counts
                        FROM neighbors
                        LIMIT {batch_size} OFFSET {offset}
                    """
                    cursor.execute(query)
                    rows = cursor.fetchall()

                    if not rows:
                        break

                    for (neighbor_counts,) in rows:
                        if isinstance(neighbor_counts, (bytes, bytearray)):
                            neighbor_counts = neighbor_counts.decode("utf-8")

                        if isinstance(neighbor_counts, str):
                            degree_by_biolink_type = json.loads(neighbor_counts)
                        elif isinstance(neighbor_counts, dict):
                            degree_by_biolink_type = neighbor_counts
                        else:
                            degree_by_biolink_type = json.loads(str(neighbor_counts))

                        degree_category_set.update(degree_by_biolink_type.keys())

                    offset += batch_size

        except Exception as e:
            raise Exception(f"{e}, mysql query failed (get_degree_categories)")

        return degree_category_set
