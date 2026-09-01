import json
import os
from itertools import count
from pathlib import Path

import pyotp
import yaml
from flask import Flask, abort, jsonify, redirect, render_template_string, request, session

ROOT = Path(__file__).resolve().parents[1]
TENANT_CONFIG = ROOT / "framework" / "config" / "tenants.yaml"
SEED_FILE = ROOT / "framework" / "data" / "fixtures" / "seed.json"
NAME_LIMIT = 200
CREATORS = {"admin", "manager"}

app = Flask(__name__)
app.secret_key = "workflowpro-demo"

projects = {}
ids = count(101)


def load_tenants():
    with open(TENANT_CONFIG) as handle:
        raw = yaml.safe_load(handle)
    tenants = {}
    for key, spec in raw.items():
        users = {}
        for role, user in spec["users"].items():
            users[user["email"]] = {
                "role": role,
                "password": os.environ.get(user.get("password_env", ""), ""),
                "totp_secret": os.environ.get(user.get("totp_secret_env", ""), ""),
                "display_name": user["display_name"],
            }
        tenants[key] = {"id": spec["id"], "label": spec["label"], "users": users}
    return tenants


TENANTS = load_tenants()
BY_ID = {spec["id"]: key for key, spec in TENANTS.items()}


def seed():
    projects.clear()
    with open(SEED_FILE) as handle:
        for tenant_key, records in json.load(handle).items():
            for record in records:
                new_id = next(ids)
                projects[new_id] = {"id": new_id, "tenant": tenant_key, **record}


def tenant_or_404(key):
    if key not in TENANTS:
        abort(404)
    return TENANTS[key]


def caller():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        parts = header.split(" ", 1)[1].split(".")
        if len(parts) == 3 and parts[0] == "demo" and parts[1] in BY_ID:
            return BY_ID[parts[1]], parts[2]
        return None
    # the browser calls the same endpoints with the session cookie
    if "tenant" in session:
        return session["tenant"], session["role"]
    return None


def api_identity():
    identity = caller()
    if not identity:
        return None, (jsonify(error="unauthorized"), 401)
    tenant_key, role = identity
    if request.headers.get("Authorization"):
        header_tenant = request.headers.get("X-Tenant-ID")
        if not header_tenant:
            return None, (jsonify(error="X-Tenant-ID is required"), 400)
        # the token decides the tenant, the header is never trusted on its own
        if BY_ID.get(header_tenant) != tenant_key:
            return None, (jsonify(error="tenant mismatch"), 403)
    return (tenant_key, role), None


@app.post("/api/v1/auth/token")
def issue_token():
    body = request.get_json(silent=True) or {}
    tenant_key = BY_ID.get(request.headers.get("X-Tenant-ID", ""))
    if not tenant_key:
        return jsonify(error="unknown tenant"), 400

    user = TENANTS[tenant_key]["users"].get(body.get("email", ""))
    if not user or not user["password"] or body.get("password") != user["password"]:
        return jsonify(error="invalid credentials"), 401
    if user["totp_secret"] and not pyotp.TOTP(user["totp_secret"]).verify(str(body.get("otp", "")), valid_window=1):
        return jsonify(error="invalid otp"), 401

    return jsonify(access_token=f"demo.{TENANTS[tenant_key]['id']}.{user['role']}", expires_in=3600)


@app.get("/api/v1/projects")
def list_projects():
    identity, failure = api_identity()
    if failure:
        return failure
    tenant_key, _ = identity
    term = request.args.get("q", "").lower()
    items = [p for p in projects.values() if p["tenant"] == tenant_key and term in p["name"].lower()]
    return jsonify(items=[public(p) for p in items], total=len(items))


@app.post("/api/v1/projects")
def create_project():
    identity, failure = api_identity()
    if failure:
        return failure
    tenant_key, role = identity
    if role not in CREATORS:
        return jsonify(error="role cannot create projects"), 403

    body = request.get_json(silent=True) or {}
    problem = validate(body, tenant_key)
    if problem:
        return jsonify(error=problem), 422

    new_id = next(ids)
    projects[new_id] = {
        "id": new_id,
        "tenant": tenant_key,
        "name": body["name"],
        "description": body.get("description", ""),
        "status": "active",
        "team_members": body.get("team_members", []),
    }
    return jsonify(public(projects[new_id])), 201


@app.get("/api/v1/projects/<int:project_id>")
def read_project(project_id):
    identity, failure = api_identity()
    if failure:
        return failure
    tenant_key, _ = identity
    record = projects.get(project_id)
    if not record or record["tenant"] != tenant_key:
        return jsonify(error="not found"), 404
    return jsonify(public(record))


@app.delete("/api/v1/projects/<int:project_id>")
def delete_project(project_id):
    identity, failure = api_identity()
    if failure:
        return failure
    tenant_key, _ = identity
    record = projects.get(project_id)
    if not record or record["tenant"] != tenant_key:
        return jsonify(error="not found"), 404
    projects.pop(project_id)
    return "", 204


def validate(body, tenant_key):
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        return "name is required"
    if len(name) > NAME_LIMIT:
        return f"name is longer than {NAME_LIMIT} characters"
    members = body.get("team_members", [])
    if not isinstance(members, list):
        return "team_members must be a list"
    known = TENANTS[tenant_key]["users"]
    unknown = [email for email in members if email not in known]
    if unknown:
        return f"unknown team members: {', '.join(unknown)}"
    return None


def public(record):
    return {
        "id": record["id"],
        "name": record["name"],
        "description": record["description"],
        "status": record["status"],
        "team_members": record["team_members"],
        "tenant_id": TENANTS[record["tenant"]]["id"],
    }


@app.route("/t/<tenant_key>/login", methods=["GET", "POST"])
def login(tenant_key):
    tenant = tenant_or_404(tenant_key)
    if request.method == "GET":
        return render_template_string(LOGIN, tenant_key=tenant_key, error=None, stage="password")

    email = request.form.get("email", "")
    user = tenant["users"].get(email)
    if not user or not user["password"] or request.form.get("password") != user["password"]:
        return render_template_string(LOGIN, tenant_key=tenant_key, error="Email or password is incorrect", stage="password")

    if user["totp_secret"]:
        session["pending"] = email
        session["tenant"] = tenant_key
        return render_template_string(LOGIN, tenant_key=tenant_key, error=None, stage="otp")

    session.update(tenant=tenant_key, role=user["role"], email=email)
    return redirect(f"/t/{tenant_key}/dashboard")


@app.post("/t/<tenant_key>/verify")
def verify(tenant_key):
    tenant = tenant_or_404(tenant_key)
    user = tenant["users"].get(session.get("pending", ""))
    if not user or not pyotp.TOTP(user["totp_secret"]).verify(request.form.get("code", ""), valid_window=1):
        return render_template_string(LOGIN, tenant_key=tenant_key, error="That code did not work", stage="otp")

    session.update(tenant=tenant_key, role=user["role"], email=session.pop("pending"))
    return redirect(f"/t/{tenant_key}/dashboard")


def signed_in(tenant_key):
    return session.get("tenant") == tenant_key and session.get("role")


@app.get("/t/<tenant_key>/dashboard")
def dashboard(tenant_key):
    tenant = tenant_or_404(tenant_key)
    if not signed_in(tenant_key):
        return redirect(f"/t/{tenant_key}/login")
    user = tenant["users"][session["email"]]
    return render_template_string(DASHBOARD, tenant_key=tenant_key, label=tenant["label"], name=user["display_name"])


@app.get("/t/<tenant_key>/projects")
def projects_page(tenant_key):
    tenant_or_404(tenant_key)
    if not signed_in(tenant_key):
        return redirect(f"/t/{tenant_key}/login")
    return render_template_string(PROJECTS, tenant_key=tenant_key, label=TENANTS[tenant_key]["label"])


@app.get("/t/<tenant_key>/projects/<int:project_id>")
def project_page(tenant_key, project_id):
    tenant_or_404(tenant_key)
    if not signed_in(tenant_key):
        return redirect(f"/t/{tenant_key}/login")
    record = projects.get(project_id)
    if not record or record["tenant"] != tenant_key:
        return render_template_string(DENIED, tenant_key=tenant_key), 404
    return render_template_string(DETAIL, tenant_key=tenant_key, project=record)


LAYOUT = """
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font:15px/1.5 system-ui,sans-serif;margin:0;color:#16202b}
 header{display:flex;align-items:center;gap:16px;padding:14px 22px;border-bottom:1px solid #dfe4ea}
 nav a{margin-right:16px;color:#0b6b66;text-decoration:none}
 main{padding:24px 22px;max-width:900px}
 .card{border:1px solid #dfe4ea;border-radius:8px;padding:14px 16px;margin-bottom:10px}
 .badge{background:#e6f2f1;color:#0b6b66;border-radius:4px;padding:2px 8px;font-size:12px}
 [data-testid=nav-toggle]{display:none}
 input{padding:8px 10px;border:1px solid #cfd6de;border-radius:6px;font-size:15px}
 button{padding:8px 14px;border:0;border-radius:6px;background:#0b6b66;color:#fff;font-size:15px}
 @media (max-width:767px){
   [data-testid=nav-toggle]{display:inline-block}
   nav{display:none}
   nav.open{display:block;width:100%}
 }
</style>
<script>
 function toggleNav(){document.querySelector('nav').classList.toggle('open')}
</script>
"""

LOGIN = LAYOUT + """
<main>
  <h1>WorkFlow Pro</h1>
  {% if stage == 'password' %}
  <form method="post" data-testid="login-form">
    <p><input data-testid="email" name="email" placeholder="Work email"></p>
    <p><input data-testid="password" name="password" type="password" placeholder="Password"></p>
    <button data-testid="login-btn">Sign in</button>
  </form>
  {% else %}
  <form method="post" action="/t/{{ tenant_key }}/verify" data-testid="login-form">
    <p>Enter the code from your authenticator app.</p>
    <p><input data-testid="verification-code" name="code" placeholder="6 digit code"></p>
    <button data-testid="verify-btn">Verify</button>
  </form>
  {% endif %}
  {% if error %}<p data-testid="login-error" style="color:#a3271e">{{ error }}</p>{% endif %}
</main>
"""

DASHBOARD = LAYOUT + """
<header>
  <strong>WorkFlow Pro</strong>
  <span class="badge" data-testid="tenant-badge">{{ label }}</span>
  <button data-testid="nav-toggle" onclick="toggleNav()">Menu</button>
  <nav>
    <a href="/t/{{ tenant_key }}/dashboard" data-testid="nav-dashboard">Dashboard</a>
    <a href="/t/{{ tenant_key }}/projects" data-testid="nav-projects">Projects</a>
  </nav>
</header>
<main><h1 data-testid="welcome-message">Welcome back, {{ name }}</h1></main>
"""

PROJECTS = LAYOUT + """
<header>
  <strong>WorkFlow Pro</strong>
  <button data-testid="nav-toggle" onclick="toggleNav()">Menu</button>
  <nav>
    <a href="/t/{{ tenant_key }}/dashboard" data-testid="nav-dashboard">Dashboard</a>
    <a href="/t/{{ tenant_key }}/projects" data-testid="nav-projects">Projects</a>
  </nav>
</header>
<main>
  <h1>Projects</h1>
  <p><input data-testid="project-search" placeholder="Search projects"></p>
  <div data-testid="projects-list"><div data-testid="projects-skeleton">Loading projects</div></div>
</main>
<script>
 const list = document.querySelector('[data-testid=projects-list]');
 let timer;
 async function load(term){
   const res = await fetch('/api/v1/projects?q=' + encodeURIComponent(term || ''));
   const body = await res.json();
   if(!body.items.length){ list.innerHTML = '<p data-testid="projects-empty">No projects yet</p>'; return; }
   list.innerHTML = body.items.map(p => `
     <div class="card" data-testid="project-card" onclick="location.href='/t/{{ tenant_key }}/projects/${p.id}'">
       <strong data-testid="project-name">${p.name}</strong>
       <span class="badge" data-testid="project-owner">{{ label }}</span>
       <span class="badge">${p.status === 'active' ? 'Active' : 'Archived'}</span>
     </div>`).join('');
 }
 document.querySelector('[data-testid=project-search]').addEventListener('input', e => {
   clearTimeout(timer);
   timer = setTimeout(() => load(e.target.value), 150);
 });
 setTimeout(() => load(''), 350);
</script>
"""

DETAIL = LAYOUT + """
<main data-testid="project-header">
  <h1 data-testid="project-title">{{ project.name }}</h1>
  <p data-testid="project-description">{{ project.description }}</p>
  <p><span class="badge" data-testid="project-status">{{ 'Active' if project.status == 'active' else 'Archived' }}</span></p>
  <ul>{% for member in project.team_members %}<li data-testid="project-member">{{ member }}</li>{% endfor %}</ul>
  <a href="/t/{{ tenant_key }}/projects">Back to projects</a>
</main>
"""

DENIED = LAYOUT + """
<main><h1 data-testid="access-denied">You do not have access to this project</h1></main>
"""


if __name__ == "__main__":
    seed()
    app.run(port=int(os.environ.get("MOCK_PORT", 8080)), threaded=True)
