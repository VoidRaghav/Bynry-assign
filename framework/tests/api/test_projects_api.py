import pytest

from api.projects import ProjectsApi
from data.factories import project_payload

pytestmark = pytest.mark.api


@pytest.fixture
def projects(api_for, tenant):
    return ProjectsApi(api_for(tenant, "admin"))


def test_created_project_shows_up_in_the_list(projects, ledger):
    payload = project_payload()
    project = projects.create(payload)
    ledger.track(f"project {project.id}", lambda: projects.delete(project.id))

    assert project.name in [item.name for item in projects.list(search=payload["name"])]


def test_call_without_tenant_header_is_refused(projects):
    headers = projects.client.session.headers
    tenant_id = headers.pop("X-Tenant-ID")
    try:
        projects.client.get("/api/v1/projects", expected=(400, 403))
    finally:
        headers["X-Tenant-ID"] = tenant_id


@pytest.mark.parametrize("role, status", [("admin", 201), ("manager", 201), ("employee", 403)])
def test_creation_follows_the_role_matrix(api_for, tenant, ledger, role, status):
    client = api_for(tenant, role)
    response = client.post("/api/v1/projects", project_payload(), expected=(status,))

    if response.status_code == 201:
        project_id = response.json()["id"]
        ledger.track(f"project {project_id}", lambda: ProjectsApi(client).delete(project_id))
