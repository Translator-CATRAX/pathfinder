import ast
import logging
import sqlite3
from tqdm import tqdm


def curie_pmids_into_memory(curie_to_pmids_path, version, redis_client):
    redis_version = redis_client.get("version")
    if redis_version is not None:
        redis_version = redis_version.decode("utf-8")
        if redis_version == version:
            return

    redis_client.flushall()
    sqlite_connection = sqlite3.connect(curie_to_pmids_path)
    cursor = sqlite_connection.cursor()

    batch_size = 1000
    pipeline_size = 1000
    offset = 0

    # Get total rows for progress bar
    cursor.execute("SELECT COUNT(*) FROM curie_to_pmids")
    total_rows = cursor.fetchone()[0]

    pbar = tqdm(total=total_rows, desc="Loading CURIE→PMIDs into Redis", unit="rows")

    try:
        while True:
            query = "SELECT curie, pmids FROM curie_to_pmids LIMIT ? OFFSET ?"
            cursor.execute(query, (batch_size, offset))
            rows = cursor.fetchall()

            if not rows:
                break

            pipeline = redis_client.pipeline()

            processed_in_batch = 0

            for curie, pmids_str in rows:
                processed_in_batch += 1

                pmids = ast.literal_eval(pmids_str)
                if not pmids:
                    continue

                pipeline.sadd(curie, *pmids)

                if len(pipeline) >= pipeline_size:
                    pipeline.execute()

            pipeline.execute()

            offset += batch_size
            pbar.update(processed_in_batch)

    except Exception as e:
        logging.error("Exception occurred while inserting CURIE PMIDS into Redis in memory database.")
        logging.error(f"Exception: {e}")
        logging.error(f"Offset: {offset}")
        logging.error(f"Batch size: {batch_size}")
        raise

    finally:
        pbar.close()
        cursor.close()
        sqlite_connection.close()
        redis_client.set("version", version)
        logging.info(f"Version: curie pmids {version} inserted successfully into Redis.")


