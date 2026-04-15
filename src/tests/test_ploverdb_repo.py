from pathlib import Path

from pathfinder.core.repo.PloverDBRepo import PloverDBRepo

HERE = Path(__file__).parent
def test_ploverdb_repo_get_neighbors():
    repo = PloverDBRepo("https://kg2cploverdb.ci.transltr.io", None)
    neighbors = repo.get_neighbors_with_edges("CHEBI:31690")
    assert len(neighbors) > 0
