from api.schemas import parse_project

RESOURCE = "/api/v1/projects"


class ProjectsApi:
    def __init__(self, client):
        self.client = client

    def create(self, payload):
        return parse_project(self.client.post(RESOURCE, payload, expected=(201,)).json())

    def get(self, project_id, expected=(200,)):
        return self.client.get(f"{RESOURCE}/{project_id}", expected=expected)

    def fetch(self, project_id):
        return parse_project(self.get(project_id).json())

    def list(self, search=None):
        params = {"q": search} if search else None
        body = self.client.get(RESOURCE, params=params).json()
        return [parse_project(item) for item in body.get("items", body if isinstance(body, list) else [])]

    def delete(self, project_id):
        return self.client.delete(f"{RESOURCE}/{project_id}", expected=(200, 202, 204, 404))
