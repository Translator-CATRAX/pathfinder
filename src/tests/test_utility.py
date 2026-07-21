import json
from pathlib import Path

import requests


def download_file(url: str, out_path: Path, overwrite: bool = False) -> Path:
    out_path = Path(out_path)

    if out_path.exists() and not overwrite:
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    r = requests.get(url, timeout=60)
    r.raise_for_status()

    out_path.write_bytes(r.content)
    return out_path

def get_blocked_list():
    download_file("https://raw.githubusercontent.com/RTXteam/RTX/master/code/ARAX/KnowledgeSources/general_concepts.json", "general_concepts.json", False)

    with open("general_concepts.json", "r") as file:
        json_block_list = json.load(file)
    synonyms = set(s.lower() for s in json_block_list["synonyms"])
    return set(json_block_list["curies"]), synonyms