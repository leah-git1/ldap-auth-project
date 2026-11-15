import datetime
import os
import re

import jwt
from flask import Flask, jsonify, request, send_from_directory
from ldap3 import ALL, HASHED_SALTED_SHA, SUBTREE, Connection, Server
from ldap3.utils.hashed import hashed

app = Flask(__name__, static_folder="static")

LDAP_HOST = os.getenv("LDAP_HOST", "localhost")
LDAP_PORT = int(os.getenv("LDAP_PORT", "389"))
BASE_DN = "dc=example,dc=com"
USERS_OU = f"ou=Developers,{BASE_DN}"
GROUPS_OU = f"ou=Groups,{BASE_DN}"
ADMIN_DN = f"cn=admin,{BASE_DN}"
ADMIN_PW = os.getenv("LDAP_ADMIN_PASSWORD", "admin123")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-real-life")
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")


def server():
    return Server(LDAP_HOST, port=LDAP_PORT, get_info=ALL)


def admin_conn():
    return Connection(server(), user=ADMIN_DN, password=ADMIN_PW, auto_bind=True)


def step(op, msg, status="info"):
    return {"op": op, "msg": msg, "status": status}


def get_groups(user_dn):
    conn = admin_conn()
    conn.search(GROUPS_OU, f"(member={user_dn})", attributes=["cn"])
    groups = [str(e.cn) for e in conn.entries]
    conn.unbind()
    return groups


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.post("/register")
def register():
    d = request.get_json(silent=True) or {}
    username = d.get("username", "").strip().lower()
    full_name = " ".join(d.get("fullName", "").split())
    email = d.get("email", "").strip()
    password = d.get("password", "")
    dn = f"uid={username},{USERS_OU}"

    if not USERNAME_RE.match(username):
        return jsonify(error="Username: 3-20 chars, lowercase letters, digits or _, starting with a letter."), 400
    if not full_name or "@" not in email or len(password) < 8:
        return jsonify(error="Full name, a valid email and a password of 8+ characters are required."), 400

    parts = full_name.split()
    attrs = {
        "uid": username,
        "cn": full_name,
        "givenName": parts[0],
        "sn": parts[-1],
        "mail": email,
        "userPassword": hashed(HASHED_SALTED_SHA, password),
    }
    trace = [
        step("CONNECT", f"ldap://{LDAP_HOST}:{LDAP_PORT}"),
        step("BIND", f"as {ADMIN_DN} (service account)", "ok"),
        step("HASH", "password -> {SSHA} salted SHA-1, never stored in plain text", "ok"),
    ]
    try:
        conn = admin_conn()
        ok = conn.add(dn, "inetOrgPerson", attrs)
        reason = conn.result.get("description")
        conn.unbind()
    except Exception as exc:
        return jsonify(error=f"Directory unreachable: {exc}"), 503

    if not ok:
        trace.append(step("ADD", f"{dn} -> {reason}", "fail"))
        code = 409 if reason == "entryAlreadyExists" else 400
        msg = "That username is taken." if code == 409 else f"Directory refused the entry: {reason}"
        return jsonify(error=msg, trace=trace), code

    trace.append(step("ADD", dn, "ok"))
    return jsonify(message="Account created", trace=trace), 201


@app.post("/login")
def login():
    d = request.get_json(silent=True) or {}
    username = d.get("username", "").strip().lower()
    password = d.get("password", "")
    if not username or not password:
        return jsonify(error="Enter a username and password."), 400

    user_dn = f"uid={username},{USERS_OU}"
    trace = [step("CONNECT", f"ldap://{LDAP_HOST}:{LDAP_PORT}"), step("BIND", f"as {user_dn}")]
    try:
        conn = Connection(server(), user=user_dn, password=password)
        ok = conn.bind()
        conn.unbind()
    except Exception as exc:
        return jsonify(error=f"Directory unreachable: {exc}"), 503

    if not ok:
        trace[-1]["status"] = "fail"
        trace.append(step("RESULT", "invalidCredentials (49)", "fail"))
        return jsonify(error="Wrong username or password.", trace=trace), 401

    trace[-1]["status"] = "ok"
    trace.append(step("RESULT", "success (0)", "ok"))
    groups = get_groups(user_dn)
    trace.append(step("SEARCH", f"(member={user_dn}) in {GROUPS_OU}", "ok"))
    trace.append(step("GROUPS", ", ".join(groups) if groups else "no group memberships", "ok"))

    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
    token = jwt.encode({"sub": username, "groups": groups, "exp": exp}, JWT_SECRET, algorithm="HS256")
    trace.append(step("JWT", "signed HS256, valid for 30 minutes", "ok"))
    return jsonify(token=token, trace=trace)


def verify_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


@app.get("/profile")
def profile():
    p = verify_token()
    if not p:
        return jsonify(error="unauthorized: missing, expired or tampered token"), 401
    return jsonify(user=p["sub"], groups=p["groups"])


@app.get("/admin")
def admin():
    p = verify_token()
    if not p:
        return jsonify(error="unauthorized: missing, expired or tampered token"), 401
    if "admins" not in p["groups"]:
        return jsonify(error="forbidden: admins group required"), 403
    return jsonify(message=f"Welcome, admin {p['sub']}")


@app.get("/api/directory")
def directory():
    p = verify_token()
    if not p:
        return jsonify(error="unauthorized: missing, expired or tampered token"), 401
    if "admins" not in p["groups"]:
        return jsonify(error="forbidden: admins group required"), 403
    conn = admin_conn()
    conn.search(BASE_DN, "(objectClass=*)", search_scope=SUBTREE, attributes=["objectClass", "mail"])
    entries = []
    for e in conn.entries:
        a = e.entry_attributes_as_dict
        entries.append({"dn": e.entry_dn, "classes": a.get("objectClass", []), "mail": (a.get("mail") or [None])[0]})
    conn.unbind()
    return jsonify(base=BASE_DN, entries=entries)


if __name__ == "__main__":
    app.run(port=5000, debug=True)