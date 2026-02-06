import re
import requests
from typing import Optional


def get_kg2_version_from_plover(
        url: str,
        timeout: int = 10,
) -> Optional[str]:
    """
    Fetch the KG2 version (e.g., '2.10.2') from the Plover /code_version endpoint.

    Returns:
        str | None: KG2 version if found, otherwise None
    """
    resp = requests.get(f"{url}/code_version", timeout=timeout)
    resp.raise_for_status()

    data = resp.json()

    try:
        description = data["endpoint_build_nodes"]["kg2c"]["description"]
    except KeyError as e:
        raise KeyError("Unexpected JSON structure in Plover response") from e

    # Look for patterns like: kg2c-2.10.2-v1.0
    match = re.search(r"kg2c-(\d+\.\d+\.\d+)", description)
    if not match:
        return None

    return match.group(1)
