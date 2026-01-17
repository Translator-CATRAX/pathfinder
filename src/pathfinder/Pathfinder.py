from pathfinder.core.BidirectionalPathFinder import BidirectionalPathFinder

from pathfinder.converter.EdgeExtractorFromPloverDB import EdgeExtractorFromPloverDB
from pathfinder.converter.ResultPerPathConverter import ResultPerPathConverter


class Pathfinder:

    def __init__(
            self,
            repository_name,
            plover_url,
            ngd_url,
            degree_url,
            blocked_curies,
            blocked_synonyms,
            logger
    ):
        self.repo_name = repository_name
        self.plover_url = plover_url
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.blocked_curies = blocked_curies
        self.blocked_synonyms = blocked_synonyms
        self.logger = logger

    def get_paths(
            self,
            src_node_id,
            dst_node_id,
            src_pinned_node,
            dst_pinned_node,
            hops_numbers=4,
            max_hops_to_explore=6,
            limit=500,
            category_constraints=[]
    ):
        self.logger.info(f"Model release date: 12/01/2025")
        path_finder = BidirectionalPathFinder(
            "MLRepo",
            self.plover_url,
            self.ngd_url,
            self.degree_url,
            self.logger
        )
        paths = path_finder.find_all_paths(
            src_node_id,
            dst_node_id,
            hops_numbers=max_hops_to_explore
        )

        paths = self.remove_block_list(paths, hops_numbers)

        if len(category_constraints) > 0:
            paths = self.filter_with_constraint(paths, category_constraints)

        paths = paths[:limit]
        self.logger.info(f"PathFinder found {len(paths)} paths")

        edge_extractor = EdgeExtractorFromPloverDB(
            self.plover_url
        )
        return ResultPerPathConverter(
            paths,
            src_node_id,
            dst_node_id,
            src_pinned_node,
            dst_pinned_node,
            "aux",
            edge_extractor
        ).convert(self.logger)


    def filter_with_constraint(self, paths, category_constraints):
        result = []
        for path in paths:
            path_length = len(path.links)
            if path_length > 2:
                for i in range(1, path_length - 1):
                    node = path.links[i]
                    if node.category in category_constraints:
                        result.append(path)
                        break
        return result

    def remove_block_list(self, paths, hops_numbers):
        result = []
        for path in paths:
            append = True
            path_length = len(path.links)
            if path_length > hops_numbers + 1:
                continue
            if path_length > 2:
                for i in range(1, path_length - 1):
                    node = path.links[i]
                    if node.id in self.blocked_curies:
                        append = False
                        break
                    if node.name is not None:
                        if node.name.lower() in self.blocked_synonyms:
                            append = False
                            break
                        if node.name.lower().startswith("cyp"):
                            append = False
                            break
            if append:
                result.append(path)
        return result
