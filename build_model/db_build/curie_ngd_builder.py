import argparse
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path

import redis

from check_plover_url_compatibility import get_kg2_version_from_plover
from download_script import ensure_downloaded_and_verified, remote_file_exist
from upload_script import upload_file
from curie_pmids_into_memory import curie_pmids_into_memory
from ngd_calculation_process import run_ngd_calculation_process


# -----------------------------
# CLI
# -----------------------------

def kg_version_validator(value: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise argparse.ArgumentTypeError("KG version must look like X.Y.Z (e.g. 2.10.2)")
    return value


def parse_args():
    parser = argparse.ArgumentParser(
        description="Builds curie_ngd sqlite database for a given KG version."
    )

    parser.add_argument(
        "--kg-version",
        type=kg_version_validator,
        required=True,
        metavar="VERSION",
        help="Knowledge graph version (e.g. 2.10.2)",
    )

    parser.add_argument(
        "--plover-url",
        type=str,
        required=True,
        help="PloverDB URL",
    )

    parser.add_argument(
        "--db-host",
        default="arax-databases.rtx.ai",
        type=str,
        help="Database file host (default: arax-databases.rtx.ai)",
    )

    parser.add_argument(
        "--db-username",
        default="rtxconfig",
        type=str,
        help="Database file username (default: rtxconfig)",
    )

    parser.add_argument(
        "--db-port",
        default=22,
        type=int,
        help="Database file port (default: 22)",
    )

    parser.add_argument(
        "--ssh-key",
        default=None,
        help="Path to SSH private key (optional). If omitted, uses SSH agent/default keys.",
    )

    parser.add_argument(
        "--ssh-password",
        default=None,
        help="SSH password (optional; prefer key/agent). You can also set SSH_PASSWORD env var.",
    )

    parser.add_argument(
        "--redis-host",
        default="localhost",
        type=str,
        help="Redis host (default: localhost)",
    )

    parser.add_argument(
        "--redis-port",
        default=6379,
        type=int,
        help="Redis port (default: 6379)",
    )

    parser.add_argument(
        "--redis-db",
        default=0,
        type=int,
        help="Redis database index (default: 0)",
    )

    parser.add_argument(
        "--num-pubmed-articles",
        default=3.5e7,
        type=float,
        help="Number of PubMed citations and abstracts (default: 3.5e7)",
    )

    parser.add_argument(
        "--avg-mesh-terms-per-article",
        default=20,
        type=int,
        help="Average number of MeSH terms per article (default: 20)",
    )

    # Optional: choose output dir for downloads
    parser.add_argument(
        "--out-dir",
        default=".",
        type=str,
        help="Where to store downloaded DB files (default: current directory)",
    )

    return parser.parse_args()


# -----------------------------
# Main
# -----------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.info(f"Start time: {datetime.now()}")


    args = parse_args()

    version = args.kg_version
    curie_ngd_db_name = f"curie_ngd_v1.0_KG{version}.sqlite"
    logging.info(f"This script will try to build curie_ngd database: {curie_ngd_db_name}")

    plover_url = args.plover_url

    redis_host = args.redis_host
    redis_port = args.redis_port
    redis_db = args.redis_db

    num_pubmed = args.num_pubmed_articles
    avg_mesh = args.avg_mesh_terms_per_article
    NGD_normalizer = num_pubmed * avg_mesh
    log_NGD_normalizer = math.log(NGD_normalizer)

    db_host = args.db_host
    db_username = args.db_username
    db_port = args.db_port
    ssh_key = args.ssh_key
    ssh_password = args.ssh_password or os.getenv("SSH_PASSWORD")


    remote_path_curie_ngd = f"~/KG{version}/{curie_ngd_db_name}"
    out_dir = Path(args.out_dir)

    version_already_exist = remote_file_exist(
        host=db_host,
        username=db_username,
        port=db_port,
        remote_path=remote_path_curie_ngd,
        key_path=ssh_key,
        password=ssh_password,
    )
    if not version_already_exist:
        logging.error(f"{curie_ngd_db_name} already exist at: {db_username}@{db_host}:{remote_path_curie_ngd}")
        exit(0)

    curie_to_pmids_path = f"curie_to_pmids_v1.0_KG{version}.sqlite"
    local_path_curie_pmids = out_dir / curie_to_pmids_path
    remote_path_curie_pmids = f"~/KG{version}/{curie_to_pmids_path}"

    ensure_downloaded_and_verified(
        host=db_host,
        username=db_username,
        port=db_port,
        remote_path=remote_path_curie_pmids,
        local_path=local_path_curie_pmids,
        key_path=ssh_key,
        password=ssh_password,
    )

    plover_version = get_kg2_version_from_plover(plover_url)

    if plover_version is None:
        logging.error(f"Could not get KG2 version from PloverDB URL: {plover_url}")
        exit(0)
    if plover_version != version:
        logging.error(f"KG2 version mismatch: Plover version is {plover_version}, but expected {version}")
        exit(0)

    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
    curie_pmids_into_memory(curie_to_pmids_path, version, redis_client)
    run_ngd_calculation_process(plover_url, curie_to_pmids_path, curie_ngd_db_name, log_NGD_normalizer, redis_host, redis_port, redis_db)

    local_path_curie_ngd = out_dir / curie_ngd_db_name

    upload_file(
        host=db_host,
        username=db_username,
        port=db_port,
        remote_path=remote_path_curie_ngd,
        local_path=str(local_path_curie_ngd),
        key_path=ssh_key,
        password=ssh_password,
    )
