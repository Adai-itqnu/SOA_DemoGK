# user_service/app.py
from flask import Flask, jsonify, request, render_template
from pymongo import MongoClient
from service_registry import register_service
from config import *
import requests, consul, time, os
from models.user_model import get_all_users, get_user_by_username, create_user, update_user, delete_user

app = Flask(__name__)
app.secret_key = "user_secret"

client = MongoClient(MONGO_URI)
users_col = client["userdb"]["users"]

@app.route("/health")
def health():
    return {"status": "UP"}, 200

def get_auth_service_url(retries=5, delay=2):
    c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
    for attempt in range(retries):
        services = c.agent.services()
        for s in services.values():
            if s["Service"] == AUTH_SERVICE_NAME:
                return f"http://{s['Address']}:{s['Port']}"
        time.sleep(delay)
    return os.environ.get("AUTH_FALLBACK_URL", "http://127.0.0.1:5000")

def verify_token_with_auth(token):
    auth_url = get_auth_service_url()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.post(f"{auth_url}/auth/verify", headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json()  # {"valid": True, "sub": {...}}
    except requests.exceptions.RequestException:
        pass
    return {"valid": False}

def get_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return auth_header.strip()

# HTML shell for admin user management (accept both /user and /user/)
@app.route("/")
@app.route("/user")
@app.route("/user/")
def user_shell():
    # Get token from localStorage in frontend
    return render_template("users.html")

# APIs (JWT-protected via Nginx)
@app.route("/user-api/users", methods=["GET"])
def api_get_users():
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "forbidden"}), 403
    return jsonify(get_all_users()), 200

@app.route("/user-api/users/<username>", methods=["GET"])
def api_get_user(username):
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "forbidden"}), 403

    user = get_user_by_username(username)
    if user:
        return jsonify(user), 200
    return jsonify({"error": "Không tìm thấy người dùng"}), 404

@app.route("/user-api/users", methods=["POST"])
def api_add_user():
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json() or {}
    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Thiếu dữ liệu"}), 400
    if get_user_by_username(data["username"]):
        return jsonify({"error": "Username đã tồn tại"}), 400

    create_user(data)
    return jsonify({"message": "Thêm người dùng thành công"}), 201

@app.route("/user-api/users/<username>", methods=["PUT"])
def api_update_user(username):
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json() or {}
    updated = update_user(username, data)
    if updated:
        return jsonify({"message": "Cập nhật thành công"}), 200
    return jsonify({"error": "Không tìm thấy người dùng"}), 404

@app.route("/user-api/users/<username>", methods=["DELETE"])
def api_delete_user(username):
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "forbidden"}), 403

    deleted = delete_user(username)
    if deleted:
        return jsonify({"message": "Đã xóa người dùng"}), 200
    return jsonify({"error": "Không tìm thấy người dùng"}), 404

if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)