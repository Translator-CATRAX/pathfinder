from typing import Set
from importlib.metadata import version, PackageNotFoundError

from pathfinder.converter.EdgeExtractorFromTRAPIResponse import EdgeExtractorFromTRAPIResponse
from pathfinder.core.BidirectionalPathFinder import BidirectionalPathFinder
from pathfinder.converter.ResultPerPathConverter import ResultPerPathConverter
from pathfinder.core.ThreeHopsPathfinder import ThreeHopsPathfinder


class Pathfinder:

    def __init__(
            self,
            repo_uri: str,
            ngd_url: str,
            degree_url: str,
            blocked_curies: Set[str],
            blocked_synonyms: Set[str],
            logger
    ):
        self.repo_uri = repo_uri
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.blocked_curies = blocked_curies
        self.blocked_synonyms = blocked_synonyms
        self.logger = logger

    def get_paths(
            self,
            src_node_id: str,
            dst_node_id: str,
            src_pinned_node: str,
            dst_pinned_node: str,
            hops_numbers: int = 4,
            max_hops_to_explore: int = 6,
            limit: int = 500,
            prune_top_k: int = 30,
            degree_threshold: int = 30000,
            category_constraints: Set[str] = None
    ):
        try:
            pkg_version = version("catrax-pathfinder")
        except PackageNotFoundError:
            pkg_version = "unknown (not installed)"
        self.logger.info(f"Calling get_paths() from catrax-pathfinder version: {pkg_version}")
        if category_constraints is None:
            category_constraints = set()
        path_finder = BidirectionalPathFinder(
            self.repo_uri,
            self.ngd_url,
            self.degree_url,
            prune_top_k,
            degree_threshold,
            self.logger
        )
        paths, kg = path_finder.find_all_paths(
            src_node_id,
            dst_node_id,
            hops_numbers=max_hops_to_explore
        )

        return self.post_paths_process(
            paths,
            src_node_id,
            dst_node_id,
            src_pinned_node,
            dst_pinned_node,
            hops_numbers,
            limit,
            category_constraints,
            kg
        )

    def filter_with_constraint(self, paths, category_constraints):
        result = []
        for path in paths:
            if len(path.edges) > 1:
                for i in range(1, len(path.edges) - 1):
                    src_node = path.edges[i].source
                    trg_node = path.edges[i].target
                    if src_node.category in category_constraints:
                        result.append(path)
                        break
                    if trg_node.category in category_constraints:
                        result.append(path)
                        break
        return result

    def remove_block_list(self, paths, hops_numbers):
        result = []
        for path in paths:
            append = True
            path_length = len(path.edges)
            if path_length > hops_numbers:
                continue
            if len(path.edges) > 1:
                for i in range(1, len(path.edges) - 1):
                    src_node = path.edges[i].source
                    trg_node = path.edges[i].target
                    if src_node.id in self.blocked_curies or trg_node.id in self.blocked_curies:
                        append = False
                        break
                    if src_node.name is not None:
                        if src_node.name.lower() in self.blocked_synonyms:
                            append = False
                            break
                    if trg_node.name is not None:
                        if trg_node.name.lower() in self.blocked_synonyms:
                            append = False
                            break
            if append:
                result.append(path)
        return result

    def get_three_hops_paths(
            self,
            src_node_id: str,
            dst_node_id: str,
            src_pinned_node: str,
            dst_pinned_node: str,
            limit: int = 500,
            degree_threshold: int = 5000,
            category_constraints: Set[str] = None,
            min_information_content: int = 69
    ):
        try:
            pkg_version = version("catrax-pathfinder")
        except PackageNotFoundError:
            pkg_version = "unknown (not installed)"
        self.logger.info(f"Calling get_paths() from catrax-pathfinder version: {pkg_version}")

        if category_constraints is None:
            category_constraints = set()
        pathfinder = ThreeHopsPathfinder(
            self.repo_uri,
            self.ngd_url,
            self.degree_url,
            degree_threshold,
            limit,
            self.logger
        )
        paths, kg = pathfinder.find_three_hops_paths(
            src_node_id,
            dst_node_id,
            src_pinned_node,
            dst_pinned_node,
            min_information_content
        )

        return self.post_paths_process(
            paths,
            src_node_id,
            dst_node_id,
            src_pinned_node,
            dst_pinned_node,
            3,
            limit,
            category_constraints,
            kg
        )

    def post_paths_process(
            self,
            paths,
            src_node_id,
            dst_node_id,
            src_pinned_node,
            dst_pinned_node,
            hops_numbers,
            limit,
            category_constraints,
            kg
    ):
        paths = self.remove_block_list(paths, hops_numbers)

        if len(category_constraints) > 0:
            paths = self.filter_with_constraint(paths, category_constraints)

        paths = paths[:limit]
        self.logger.info(f"PathFinder found {len(paths)} paths")
        edge_extractor = EdgeExtractorFromTRAPIResponse(kg, self.logger)
        return ResultPerPathConverter(
            paths,
            src_node_id,
            dst_node_id,
            src_pinned_node,
            dst_pinned_node,
            "aux",
            edge_extractor
        ).convert(self.logger)
