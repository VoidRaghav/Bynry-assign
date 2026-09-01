import pytest

from api.projects import ProjectsApi
from data.fixtures import payload_cases

pytestmark = [pytest.mark.api, pytest.mark.smoke]

VALID = [pytest.param(payload, id=case) for case, payload, _ in payload_cases("valid")]
INVALID = [pytest.param(payload, status, id=case) for case, payload, status in payload_cases("invalid")]


@pytest.fixture
def projects(api_for, tenant):
    return ProjectsApi(api_for(tenant, "admin"))


@pytest.mark.parametrize("payload", VALID)
def test_accepted_payloads_create_a_project(projects, ledger, payload):
    project = projects.create(payload)
    ledger.track(f"project {project.id}", lambda: projects.delete(project.id))

    assert project.name == payload["name"]
    assert project.status == "active"


@pytest.mark.parametrize("payload, status", INVALID)
def test_rejected_payloads_never_create_a_project(projects, payload, status):
    projects.client.post("/api/v1/projects", payload, expected=(status,))
