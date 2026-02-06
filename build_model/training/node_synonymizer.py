import logging
import pathlib
import sqlite3
import time


class NodeSynonymizer:

    def __init__(self, database_path: str):
        self.database_path = database_path

        if not pathlib.Path(self.database_path).exists():
            raise ValueError(f"Specified synonymizer does not exist locally."
                             f" It should be at: {self.database_path}")
        else:
            self.db_connection = sqlite3.connect(self.database_path)

    def __del__(self):
        if hasattr(self, "db_connection"):
            self.db_connection.close()

    def get_distinct_category_list(self, debug: bool = False) -> list:
        start = time.time()

        sql_query = f"""SELECT DISTINCT category FROM nodes"""
        matching_rows = self._execute_sql_query(sql_query)
        result = []
        for row in matching_rows:
            result.append(row[0])

        if debug:
            logging.info(f"Took {round(time.time() - start, 5)} seconds")
        return result

    def _execute_sql_query(self, sql_query: str) -> list:
        cursor = self.db_connection.cursor()
        cursor.execute(sql_query)
        matching_rows = cursor.fetchall()
        cursor.close()
        return matching_rows
