import copy
import math
import queue
from concurrent.futures import ProcessPoolExecutor

from pathfinder.core.BreadthFirstSearch import traverse
from pathfinder.core.model.Node import Node
from pathfinder.core.model.Edge import Edge
from pathfinder.core.model.Path import Path
from pathfinder.core.model.PathContainer import PathContainer
from pathfinder.core.repo.repo_factory import get_repo
from pathfinder.telemetry import tracer, inject_context, child_bootstrap, flush_child


def run_bfs_process(hops_numbers, node_id, repo_args, prune_top_k, degree_threshold, otel_carrier):
    child_tracer, parent_ctx = child_bootstrap(otel_carrier)
    try:
        with child_tracer.start_as_current_span(
            "pathfinder.bfs_worker",
            context=parent_ctx,
            attributes={
                "pathfinder.node_id": node_id,
                "pathfinder.hops_numbers": hops_numbers,
            },
        ):
            repo = get_repo(*repo_args)

            path_container = PathContainer()
            path_queue = queue.Queue()

            new_path = Path.from_curie(hops_numbers, Node(curie=node_id))
            if hops_numbers != 0:
                path_queue.put(new_path)
            path_container.add_new_path(new_path)


            knowledge_graph = traverse(repo, path_queue, path_container, prune_top_k)

            return path_container, knowledge_graph
    finally:
        flush_child()


class BidirectionalPathFinder:

    def __init__(self, repo_uri, ngd_url, degree_url, prune_top_k, degree_threshold, logger):
        self.repo_uri = repo_uri
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.prune_top_k = prune_top_k
        self.degree_threshold = degree_threshold
        self.logger = logger


    def find_all_paths(self, node_id_1, node_id_2, hops_numbers=1):
        self.logger.info("Finding paths process has started")
        with tracer.start_as_current_span(
            "pathfinder.find_all_paths",
            attributes={
                "pathfinder.hops_numbers": hops_numbers,
                "pathfinder.prune_top_k": self.prune_top_k,
                "pathfinder.degree_threshold": self.degree_threshold,
            },
        ) as span:
            result = set()
            if hops_numbers == 0:
                return result
            if node_id_1 == node_id_2:
                return result

            hops_numbers_1 = math.floor((hops_numbers + 1) / 2)
            hops_numbers_2 = math.floor(hops_numbers / 2)

            repo_args = (self.repo_uri, self.ngd_url, self.degree_url, self.degree_threshold)
            otel_carrier = inject_context()
            with tracer.start_as_current_span("pathfinder.collect_bfs_results"):
                with ProcessPoolExecutor(max_workers=2) as ex:
                    f1 = ex.submit(run_bfs_process, hops_numbers_1, node_id_1, repo_args, self.prune_top_k, self.degree_threshold, otel_carrier)
                    f2 = ex.submit(run_bfs_process, hops_numbers_2, node_id_2, repo_args, self.prune_top_k, self.degree_threshold, otel_carrier)

                    try:
                        path_container_1, kg_1 = f1.result()
                    except Exception as e:
                        self.logger.error(f"Process 1 with curie id: {node_id_1} failed with exception: {e}")
                        path_container_1, kg_1 = None, None

                    try:
                        path_container_2, kg_2 = f2.result()
                    except Exception as e:
                        self.logger.error(f"Process 2 with curie id: {node_id_2} failed with exception: {e}")
                        path_container_2, kg_2 = None, None

                if path_container_1 is None or path_container_2 is None:
                    failed = [
                        node_id for node_id, container in (
                            (node_id_1, path_container_1),
                            (node_id_2, path_container_2),
                        ) if container is None
                    ]
                    raise RuntimeError(
                        f"BidirectionalPathFinder could not find paths: BFS failed for "
                        f"curie(s) {failed} -- see the error logged above for the underlying "
                        f"exception (e.g. the endpoint was unreachable)."
                    )

            kg = self.aggregate_kg(kg_1, kg_2)

            with tracer.start_as_current_span("pathfinder.merge_intersecting_paths") as merge_span:
                intersection_list = path_container_1.path_dict.keys() & path_container_2.path_dict.keys()
                merge_span.set_attribute("pathfinder.intersection_node_count", len(intersection_list))

                for node in intersection_list:
                    for path_1 in path_container_1.path_dict[node]:
                        for path_2 in path_container_2.path_dict[node]:
                            temp_path_1 = copy.deepcopy(path_1)
                            for i in range(len(path_2.edges) - 1, -1, -1):
                                new_edge = Edge(path_2.edges[i].target, path_2.edges[i].source, path_2.edges[i].weight_bar, path_2.edges[i].weight)
                                temp_path_1.edges.append(new_edge)

                            if len(temp_path_1.node_list()) == len(temp_path_1.node_set()):
                                result.add(Path(0, temp_path_1.edges))

                result = sorted(list(result), key=lambda path: path.compute_weight(), reverse=True)
                merge_span.set_attribute("pathfinder.result_count", len(result))

            span.set_attribute("pathfinder.result_count", len(result))
            return result, kg

    def aggregate_kg(self, kg_1, kg_2):
        if kg_1 is None:
            kg_1 = {"edges": {}, "nodes": {}}
        if kg_2 is None:
            kg_2 = {"edges": {}, "nodes": {}}

        if "edges" not in kg_1 and "nodes" not in kg_1:
            kg_1 = {"edges": {}, "nodes": {}}
        elif "edges" not in kg_1:
            kg_1["edges"] = {}
        elif "nodes" not in kg_1:
            kg_1["nodes"] = {}
        if "edges" in kg_2:
            kg_1["edges"].update(kg_2["edges"])
        if "nodes" in kg_2:
            kg_1["nodes"].update(kg_2["nodes"])

        return kg_1
