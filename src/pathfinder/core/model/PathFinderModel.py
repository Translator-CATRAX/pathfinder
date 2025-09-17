import pickle


class PathFinderModel:

    def __init__(self, repo_name, path, plover_url, ngd_url, degree_url):
        self.repo_name = repo_name
        self.path = path
        self.plover_url = plover_url
        self.ngd_url = ngd_url
        self.degree_url = degree_url

    def serialize(self):
        return pickle.dumps(self)

    @staticmethod
    def deserialize(data):
        return pickle.loads(data)
