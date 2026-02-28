import sqlite3
import ast


class NGDRepository:

    def __init__(self, db_path):
        self.db_path = db_path

    def get_curie_ngd(self, curie):
        try:
            sqlite_connection_read = sqlite3.connect(self.db_path)
            cursor = sqlite_connection_read.cursor()
            query = "SELECT ngd FROM curie_ngd WHERE curie = ?"
            cursor.execute(query, (curie,))
            row = cursor.fetchone()
            cursor.close()
            sqlite_connection_read.close()
        except Exception as e:
            raise Exception(f"Error occurred in get_curie_ngd: {e}, db path: {self.db_path}")
        if row:
            ngds = ast.literal_eval(row[0])
            return ngds

        return []

    def get_curies_pmid_length(self, curies, limit=-1):
        try:
            sqlite_connection_read = sqlite3.connect(self.db_path)
            cursor = sqlite_connection_read.cursor()

            all_rows = []
            chunk_size = 900

            for i in range(0, len(curies), chunk_size):
                chunk = curies[i:i + chunk_size]

                query = f"""
                    SELECT curie, pmid_length
                    FROM curie_ngd
                    WHERE curie IN ({','.join('?' for _ in chunk)})
                """

                cursor.execute(query, chunk)
                all_rows.extend(cursor.fetchall())

            cursor.close()
            sqlite_connection_read.close()

            all_rows.sort(key=lambda x: x[1], reverse=True)
            if limit != -1:
                all_rows = all_rows[:limit]

        except Exception as e:
            raise Exception(f"Error occurred in get_curies_pmid_length: {e}, db path: {self.db_path}")

        return all_rows
