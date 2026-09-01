import pytest

from api.projects import ProjectsApi
from data.factories import project_payload

pytestmark = [pytest.mark.security, pytest.mark.api]
DENIED = (401, 403, 404)


@pytest.fixture
def company1_project(api_for, ledger, tenants):
    owner = tenants["company1"]
    projects = ProjectsApi(api_for(owner, "admin"))
    project = projects.create(project_payload())
    ledger.track(f"project {project.id}", lambda: projects.delete(project.id))
    return project


@pytest.mark.parametrize("role", ["admin", "employee"])
def test_other_tenant_cannot_read_the_project(api_for, tenants, company1_project, role):
    stranger = ProjectsApi(api_for(tenants["company2"], role))

    assert stranger.get(company1_project.id, expected=DENIED).status_code in DENIED


def test_other_tenant_cannot_delete_the_project(api_for, tenants, company1_project):
    stranger = api_for(tenants["company2"], "admin")

    assert stranger.delete(f"/api/v1/projects/{company1_project.id}", expected=DENIED).status_code in DENIED


def test_swapping_the_tenant_header_does_not_grant_access(api_for, tenants, company1_project):
    spoofed = api_for(tenants["company2"], "admin").as_tenant(tenants["company1"])

    assert ProjectsApi(spoofed).get(company1_project.id, expected=DENIED).status_code in DENIED


def test_project_list_never_mixes_tenants(api_for, tenants, company1_project):
    listing = ProjectsApi(api_for(tenants["company2"], "admin")).list()

    assert company1_project.id not in [item.id for item in listing]
