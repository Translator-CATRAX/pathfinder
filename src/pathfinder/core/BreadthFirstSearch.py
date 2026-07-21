import os
import concurrent.futures

from pathfinder.core.model.Node import Node
from pathfinder.core.model.Path import Path


def process_path(path, repo, prune_top_k):
    knowledge_graph = None
    try:
        result = []
        if path.path_limit > 0:
            last_curie = path.last_curie()
            edges, knowledge_graph = repo.get_edges(last_curie)
            for idx, edge in enumerate(edges):
                if edge.target not in path.node_set():
                    if idx < prune_top_k:
                        new_path = path.make_new_path(edge)
                    else:
                        new_path = path.make_new_path(edge, 0)
                    result.append(new_path)

        return path, result, None, knowledge_graph
    except Exception as e:
        return path, None, e, knowledge_graph


def traverse(repo, path_queue, path_container, prune_top_k):
    num_threads = min(os.cpu_count() or 4, 4)
    knowledge_graph = {"nodes": {}, "edges":{}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        while not path_queue.empty():
            paths = []
            for _ in range(4 * num_threads):
                if not path_queue.empty():
                    paths.append(path_queue.get())

            futures = [
                executor.submit(process_path, p, repo, prune_top_k)
                for p in paths
            ]

            for future in concurrent.futures.as_completed(futures):
                original_path, new_paths, exception, kg = future.result()
                if kg is not None:
                    if "nodes" in kg:
                        knowledge_graph["nodes"].update(kg["nodes"])
                    if "edges" in kg:
                        knowledge_graph["edges"].update(kg["edges"])
                if exception:
                    # logger.error(f"Path {original_path} raised an exception: {exception}") todo
                    raise exception
                else:
                    for new_path in new_paths:
                        path_queue.put(new_path)
                        path_container.add_new_path(new_path)

    return knowledge_graph
