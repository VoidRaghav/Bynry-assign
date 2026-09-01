import pytest
from playwright.sync_api import expect

from api.projects import ProjectsApi
from config.settings import device_suite
from core.errors import TenantLeakError
from data.factories import project_payload
from pages.project_detail_page import ProjectDetailPage
from pages.projects_page import ProjectsPage

pytestmark = [pytest.mark.integration, pytest.mark.smoke]
HANDSETS = [pytest.param(item, id=item["name"]) for item in device_suite("smoke") if item.get("real_mobile")]


@pytest.fixture
def seeded_project(api_for, ledger, tenants):
    owner = tenants["company1"]
    projects = ProjectsApi(api_for(owner, "admin"))
    payload = project_payload(members=[owner.user("manager").email, owner.user("employee").email])
    project = projects.create(payload)
    ledger.track(f"project {project.id} on {owner.key}", lambda: projects.delete(project.id))
    return owner, project, payload


def test_project_creation_flow(seeded_project, tenants, environment, api_for, signed_in_page, mobile_page):
    owner, project, payload = seeded_project
    outsider = tenants["company2"]

    # 1. API first, so a broken contract never gets misread as a UI bug
    assert project.status == "active"
    assert project.name == payload["name"]
    assert ProjectsApi(api_for(owner, "admin")).fetch(project.id).name == payload["name"]

    # 2. Web UI, read back through the product the way a manager would
    desktop = signed_in_page(owner, "manager")
    board = ProjectsPage(desktop, environment, owner).open()
    expect(board.wait_for_project(project.name)).to_contain_text("Active")

    detail = board.open_project(project.name)
    expect(detail.title).to_have_text(project.name)
    expect(detail.description).to_have_text(payload["description"])
    expect(detail.members).to_have_count(len(payload["team_members"]))

    # 3. Mobile on a real device, where the nav sits behind the drawer
    handset = mobile_page(owner, "manager")
    mobile_board = ProjectsPage(handset, environment, owner).open()
    assert mobile_board.is_compact_layout()
    expect(mobile_board.wait_for_project(project.name)).to_be_visible()

    # 4. Isolation, checked at the API and again in the UI because they can fail apart
    stranger = api_for(outsider, "admin")
    assert ProjectsApi(stranger).get(project.id, expected=(403, 404)).status_code in (403, 404)

    spoofed = stranger.as_tenant(owner)
    assert ProjectsApi(spoofed).get(project.id, expected=(401, 403, 404)).status_code in (401, 403, 404)

    intruder_page = signed_in_page(outsider, "admin")
    intruder_board = ProjectsPage(intruder_page, environment, outsider).open()
    intruder_board.search(project.name)
    if project.name in intruder_board.visible_project_names():
        raise TenantLeakError(f"{outsider.key} can list project {project.id} owned by {owner.key}")

    forced = ProjectDetailPage(intruder_page, environment, outsider, project.id)
    intruder_page.goto(forced.url, wait_until="domcontentloaded")
    expect(forced.access_denied).to_be_visible()
    expect(forced.title).to_have_count(0)


@pytest.mark.mobile
@pytest.mark.parametrize("device", HANDSETS)
def test_project_reads_on_each_handset(seeded_project, environment, mobile_page, device):
    owner, project, _ = seeded_project
    handset = mobile_page(owner, "employee", device=device)
    board = ProjectsPage(handset, environment, owner).open()
    expect(board.wait_for_project(project.name)).to_be_visible()
