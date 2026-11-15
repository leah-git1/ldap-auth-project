import datetime
import jwt
from flask import Flask, request, jsonify
from ldap3 import Server, Connection, ALL

app = Flask(__name__)

LDAP_HOST = "localhost"
BASE_DN = "dc=example,dc=com"
USERS_OU = "ou=Developers,dc=example,dc=com"
GROUPS_OU = "ou=Groups,dc=example,dc=com"
JWT_SECRET = "change-me-in-real-life"


def authenticate(username, password):
    """בודק משתמש וסיסמה מול LDAP (Bind). מחזיר True/False."""
    user_dn = f"uid={username},{USERS_OU}"
    server = Server(LDAP_HOST, get_info=ALL)
    try:
        conn = Connection(server, user=user_dn, password=password)
        ok = conn.bind()
        conn.unbind()
        return ok
    except Exception:
        return False


def get_groups(username):
    """מחזיר את רשימת הקבוצות שהמשתמש חבר בהן."""
    user_dn = f"uid={username},{USERS_OU}"
    server = Server(LDAP_HOST, get_info=ALL)
    conn = Connection(server, user=f"cn=admin,{BASE_DN}", password="admin123", auto_bind=True)
    conn.search(GROUPS_OU, f"(member={user_dn})", attributes=["cn"])
    groups = [str(entry.cn) for entry in conn.entries]
    conn.unbind()
    return groups


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "missing credentials"}), 400

    if not authenticate(username, password):
        return jsonify({"error": "invalid username or password"}), 401

    groups = get_groups(username)
    token = jwt.encode(
        {
            "sub": username,
            "groups": groups,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return jsonify({"token": token})


def verify_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


@app.route("/profile")
def profile():
    payload = verify_token()
    if not payload:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"user": payload["sub"], "groups": payload["groups"]})


@app.route("/admin")
def admin():
    payload = verify_token()
    if not payload:
        return jsonify({"error": "unauthorized"}), 401
    if "admins" not in payload["groups"]:
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"message": f"Welcome admin {payload['sub']}"})


if __name__ == "__main__":
    app.run(port=5000, debug=True)