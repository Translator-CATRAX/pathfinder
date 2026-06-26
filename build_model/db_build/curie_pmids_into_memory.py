import ast
import logging
import sqlite3
from tqdm import tqdm


def curie_pmids_into_memory(curie_to_pmids_path, version, redis_client):
    redis_version = redis_client.get("version")
    if redis_version is not None:
        redis_version = redis_version.decode("utf-8")
        if redis_version == version:
            logging.info(f"Version {version} already loaded. Skipping.")
            return

    logging.info("Flushing existing Redis data...")
    redis_client.flushall()

    sqlite_connection = sqlite3.connect(curie_to_pmids_path)
    cursor = sqlite_connection.cursor()

    pipeline_size = 1000

    cursor.execute("SELECT COUNT(*) FROM curie_to_pmids")
    total_rows = cursor.fetchone()[0]

    pbar = tqdm(total=total_rows, desc="Loading CURIE→PMIDs into Redis", unit="rows")
    pipeline = redis_client.pipeline()

    try:
        cursor.execute("SELECT curie, pmids FROM curie_to_pmids")

        processed_in_batch = 0

        for curie, pmids_str in cursor:
            pmids = ast.literal_eval(pmids_str)
            if pmids:
                chunk_size = 10000
                if len(pmids) > chunk_size:
                    logging.warning(f"Found massive row! CURIE: {curie} has {len(pmids)} PMIDs. Chunking...")
                    for i in range(0, len(pmids), chunk_size):
                        pipeline.sadd(curie, *pmids[i:i + chunk_size])
                else:
                    pipeline.sadd(curie, *pmids)

            processed_in_batch += 1

            if len(pipeline) >= pipeline_size:
                pipeline.execute()
                pbar.update(processed_in_batch)
                processed_in_batch = 0

        if len(pipeline) > 0:
            pipeline.execute()
            pbar.update(processed_in_batch)

        redis_client.set("version", version)
        logging.info(f"Version: curie pmids {version} inserted successfully into Redis.")

    except Exception as e:
        logging.error("Exception occurred while inserting CURIE PMIDS into Redis.")
        logging.error(f"Exception: {e}")
        raise

    finally:
        pbar.close()
        cursor.close()
        sqlite_connection.close()