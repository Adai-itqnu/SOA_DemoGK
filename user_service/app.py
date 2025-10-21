from flask import Flask, jsonify, request, render_template, session, redirect
from pymongo import MongoClient
from service_registry import register_service
from config import *
import requests, consul
from datetime import datetime
from models.user_model import get_all_users, get_user_by_username, create_user, update_user, delete_user

app = Flask(__name__)
app.secret_key = "user_secret"

# Kết nối Mongo
client = MongoClient(MONGO_URI)
users = client["userdb"]["users"]

# ---------------- HEALTH CHECK ----------------
@app.route("/health")
def health():
    return {"status": "UP"}, 200


# ---------------- Consul Service Discovery ----------------
def get_auth_service_url():
    c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
    services = c.agent.services()
    for s in services.values():
        if s["Service"] == AUTH_SERVICE_NAME:
            return f"http://{s['Address']}:{s['Port']}"
    return None


# ---------------- Trang giao diện chính ----------------
@app.route("/")
def home():
    token = request.args.get("token")
    username = request.args.get("username")

    if not token or not username:
        return "Thiếu token hoặc username", 401

    # Gọi Auth Service để xác thực token
    auth_url = get_auth_service_url()
    if not auth_url:
        return "Không tìm thấy Auth Service!", 500

    r = requests.post(f"{auth_url}/auth/verify", headers={"Authorization": token})
    result = r.json()

    if not result.get("valid"):
        return "Token không hợp lệ!", 401

    # Kiểm tra role
    role = result["role"]
    if role != "admin":
        return "<h3>Bạn không có quyền truy cập trang quản trị!</h3>", 403

    session["username"] = username
    session["token"] = token

    all_users = get_all_users()
    return render_template("users.html", users=all_users, admin=username)


# ---------------- REST API CRUD ----------------

@app.route("/users", methods=["GET"])
def api_get_users():
    """Lấy toàn bộ người dùng"""
    return jsonify(get_all_users()), 200


@app.route("/users/<username>", methods=["GET"])
def api_get_user(username):
    user = get_user_by_username(username)
    if user:
        return jsonify(user), 200
    return jsonify({"error": "Không tìm thấy người dùng"}), 404


@app.route("/users", methods=["POST"])
def api_add_user():
    """Thêm người dùng mới"""
    data = request.get_json()
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Thiếu dữ liệu"}), 400
    if get_user_by_username(data["username"]):
        return jsonify({"error": "Username đã tồn tại"}), 400

    create_user(data)
    return jsonify({"message": "Thêm người dùng thành công"}), 201


@app.route("/users/<username>", methods=["PUT"])
def api_update_user(username):
    """Cập nhật thông tin người dùng"""
    data = request.get_json()
    updated = update_user(username, data)
    if updated:
        return jsonify({"message": "Cập nhật thành công"}), 200
    return jsonify({"error": "Không tìm thấy người dùng"}), 404


@app.route("/users/<username>", methods=["DELETE"])
def api_delete_user(username):
    """Xóa người dùng"""
    deleted = delete_user(username)
    if deleted:
        return jsonify({"message": "Đã xóa người dùng"}), 200
    return jsonify({"error": "Không tìm thấy người dùng"}), 404


@app.route("/logout")
def logout():
    """Xóa session của user_service và quay lại trang đăng nhập auth_service"""
    session.clear()

    # Nếu bạn có dùng Consul để lấy địa chỉ auth_service:
    try:
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        services = c.agent.services()
        for s in services.values():
            if s["Service"] == AUTH_SERVICE_NAME:
                auth_url = f"http://{s['Address']}:{s['Port']}"
                return redirect(f"{auth_url}/login")
    except Exception:
        pass

    # Fallback nếu không tìm thấy service qua Consul
    return redirect("http://127.0.0.1:5000/login")


if __name__ == "__main__":
    register_service()
    app.run(port=5002, debug=True)