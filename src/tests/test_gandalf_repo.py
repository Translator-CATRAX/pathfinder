from pathlib import Path

from pathfinder.core.repo.GandalfRepo import GandalfRepo

HERE = Path(__file__).parent
def test_gandalf_repo_get_neighbors():
    repo = GandalfRepo(HERE / "../../data/processed/gandalf_mmap", None)
    neighbors = repo.get_neighbors_with_edges("MONDO:0004979")
    assert len(neighbors) > 0
