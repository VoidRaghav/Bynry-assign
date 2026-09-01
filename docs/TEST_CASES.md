# Test Cases

Cases are grouped by area with a stable id, so a failure in CI, a defect ticket and a line in this catalogue all refer to the same thing. Automated cases name the file that implements them. Everything marked backlog is a deliberate gap, not a miss.

Priority: P1 blocks a release, P2 fixed in the cycle, P3 backlog.

## Authentication, AUTH

| ID | Case | Priority | Layer | Automated in |
| --- | --- | --- | --- | --- |
| AUTH-01 | Admin signs in and lands on the dashboard for the right tenant | P1 | UI | `part1_flaky_login/test_login_fixed.py`, `framework/tests/web/test_login.py` |
| AUTH-02 | Manager and Employee sign in and see their own name and tenant badge | P1 | UI | `framework/tests/web/test_login.py` |
| AUTH-03 | A user with 2FA enabled is challenged and completes login with a TOTP code | P1 | UI | `framework/pages/login_page.py` drives it, exercised by AUTH-01 in the demo environment |
| AUTH-04 | A wrong password shows an error and keeps the user on the login page | P1 | UI | `framework/tests/web/test_login.py` |
| AUTH-05 | API issues a token for valid credentials and rejects invalid ones | P1 | API | `framework/core/auth.py`, exercised by every API test |
| AUTH-06 | A token request without a tenant header is refused | P2 | API | `framework/tests/api/test_projects_api.py` |
| AUTH-07 | Session expiry returns the user to login without a broken screen | P2 | UI | backlog |
| AUTH-08 | Account lockout after repeated failures | P3 | API | backlog, needs the platform policy first |

## Projects API, PROJ

| ID | Case | Priority | Layer | Automated in |
| --- | --- | --- | --- | --- |
| PROJ-01 | A created project is returned by the list endpoint | P1 | API | `framework/tests/api/test_projects_api.py` |
| PROJ-02 | Minimal payload creates an active project | P1 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-03 | Payload with team members creates the project and keeps the members | P1 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-04 | Non latin project name is accepted and returned unchanged | P2 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-05 | Empty name is rejected with 422 | P1 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-06 | Name longer than 200 characters is rejected | P2 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-07 | Missing name key is rejected | P2 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-08 | team_members of the wrong type is rejected | P2 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-09 | A member outside the tenant is rejected | P1 | API | `framework/tests/api/test_project_validation.py` |
| PROJ-10 | Admin can create, Manager can create, Employee cannot | P1 | API | `framework/tests/api/test_projects_api.py` |
| PROJ-11 | Response matches the documented contract | P1 | API | `framework/api/schemas.py`, enforced on every parse |
| PROJ-12 | Deleting a project twice is safe for cleanup | P2 | API | `framework/api/projects.py` accepts 404 on delete |

## Web UI, UI

| ID | Case | Priority | Layer | Automated in |
| --- | --- | --- | --- | --- |
| UI-01 | A project created over the API appears in the list without a manual refresh | P1 | UI | `framework/tests/integration/test_project_creation_flow.py` |
| UI-02 | Project detail shows name, description, status and the exact member count | P1 | UI | `framework/tests/integration/test_project_creation_flow.py` |
| UI-03 | Search finds a project by exact name | P1 | UI | `framework/pages/projects_page.py`, used by UI-01 |
| UI-04 | An empty result shows the empty state rather than a blank list | P2 | UI | `framework/pages/projects_page.py`, asserted in the isolation step |
| UI-05 | Archived projects are labelled differently from active ones | P3 | UI | backlog |
| UI-06 | Project creation through the UI dialog | P1 | UI | backlog, the API path is covered, the dialog is not |

## Mobile, MOB

| ID | Case | Priority | Layer | Automated in |
| --- | --- | --- | --- | --- |
| MOB-01 | Dashboard is usable at handset width and the nav opens from the drawer | P1 | UI | `framework/tests/web/test_login.py` |
| MOB-02 | A project is visible on a real handset after being created over the API | P1 | Mobile | `framework/tests/integration/test_project_creation_flow.py` |
| MOB-03 | The same read works across the smoke device list | P2 | Mobile | `framework/tests/integration/test_project_creation_flow.py`, parametrized |
| MOB-04 | Touch targets and on screen keyboard do not obscure the form | P2 | Mobile | backlog, needs real device runs and a visual baseline |

## Tenant isolation and permissions, SEC

| ID | Case | Priority | Layer | Automated in |
| --- | --- | --- | --- | --- |
| SEC-01 | Another tenant cannot read a project by id | P1 | API | `framework/tests/security/test_tenant_isolation.py` |
| SEC-02 | Another tenant cannot delete a project by id | P1 | API | `framework/tests/security/test_tenant_isolation.py` |
| SEC-03 | A valid token with a swapped tenant header is refused | P1 | API | `framework/tests/security/test_tenant_isolation.py` |
| SEC-04 | A tenant's project list never contains another tenant's record | P1 | API | `framework/tests/security/test_tenant_isolation.py` |
| SEC-05 | The other tenant's UI search does not surface the project | P1 | UI | `framework/tests/integration/test_project_creation_flow.py` |
| SEC-06 | Opening another tenant's project URL directly shows access denied | P1 | UI | `framework/tests/integration/test_project_creation_flow.py` |
| SEC-07 | Employee cannot reach admin only screens by URL | P2 | UI | backlog |
| SEC-08 | An expired or tampered token is refused | P2 | API | backlog |

## Detailed cases for the critical path

### INT-01, project creation across API, web and mobile

**Preconditions.** Two tenants exist with role users. The tester holds admin credentials for company1 and company2.

| Step | Action | Expected |
| --- | --- | --- |
| 1 | POST `/api/v1/projects` as company1 admin with a unique name and two members | 201, body matches the contract, status is active |
| 2 | GET the project by id with the same token | 200, name and members match what was sent |
| 3 | Sign in to the web UI as the company1 manager and open Projects | The project card is listed and marked Active |
| 4 | Open the project | Title, description and member count match the payload |
| 5 | Repeat the read on a handset | The compact layout is served and the project is found |
| 6 | GET the project id with a company2 token | 403 or 404, never the record |
| 7 | GET it again with the company2 token and company1 in the tenant header | Refused |
| 8 | Search for the exact name in the company2 UI | Not listed |
| 9 | Open the project URL in the company2 browser | Access denied, no project title rendered |
| 10 | Teardown | The project is deleted, the tenant is left as it was found |

Automated in `framework/tests/integration/test_project_creation_flow.py`. Steps 6 to 9 also run as standalone API tests so they gate every commit rather than only the slow flow.

### AUTH-03, login with 2FA

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Submit valid credentials for a user with 2FA enabled | The verification code screen appears, no dashboard redirect |
| 2 | Submit a code generated from the shared TOTP secret | The user lands on the dashboard for their tenant |
| 3 | Submit a wrong code | An error is shown and the user stays on the challenge |

Steps 1 and 2 are automated. Step 3 is backlog. The login helper races the challenge, the error banner and the dashboard, so a user without 2FA takes the same path without a branch in the test.

## Traceability

| Requirement from the brief | Cases |
| --- | --- |
| Login works reliably in CI | AUTH-01 to AUTH-06 |
| Multi tenant data separation | SEC-01 to SEC-06, INT-01 steps 6 to 9 |
| Roles with different permissions | PROJ-10, AUTH-02 |
| Project creation via API, verified in UI | PROJ-01 to PROJ-11, UI-01, UI-02, INT-01 |
| Mobile accessibility of the same data | MOB-01 to MOB-03 |
| Cross browser support | Every UI case runs on the CI browser matrix |
