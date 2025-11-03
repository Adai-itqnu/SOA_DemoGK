from flask import Flask, render_template, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt, verify_jwt_in_request
)
from datetime import timedelta
from models.user_model import create_user, find_user, update_token, check_password
from service_registry import register_service
from config import *

app = Flask(__name__)

# Cấu hình JWT để xác thực người dùng
app.config["JWT_SECRET_KEY"] = JWT_SECRET
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
jwt_manager = JWTManager(app)

# Kiểm tra service có hoạt động không
@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200

# Xử lý đăng ký tài khoản mới
@app.route("/auth/register", methods=["GET", "POST"])
def register_page():
    if request.method == "GET":
        return render_template("register.html")

    data = request.get_json() if request.is_json else request.form
    username = data.get("username")
    password = data.get("password")
    name = data.get("name")
    age = data.get("age")
    address = data.get("address", "")

    if not username or not password or not name or not age:
        return render_template("register.html", msg="Thiếu thông tin!")

    if find_user(username):
        return render_template("register.html", msg="Tên đăng nhập đã tồn tại!")

    create_user({
        "username": username,
        "password": password,
        "name": name,
        "age": age,
        "address": address,
        "role": "user"
    })
    return render_template("login.html", msg="Đăng ký thành công, hãy đăng nhập!")

# Xử lý đăng nhập và tạo JWT token
@app.route("/auth/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json() if request.is_json else request.form
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "missing credentials"}), 400

    user = find_user(username)
    if not user or not check_password(password, user["password"]):
        return jsonify({"error": "invalid credentials"}), 401

    identity = {"username": username, "role": user.get("role", "user")}
    token = create_access_token(identity=identity, expires_delta=timedelta(hours=1))
    update_token(username, token)

    return jsonify({
        "token": token,
        "username": username,
        "role": identity["role"]
    }), 200

# Hiển thị trang dashboard admin
@app.route("/admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")

# API dành riêng cho admin (yêu cầu role admin)
@app.route("/admin-api")
@jwt_required()
def admin_api():
    claims = get_jwt()
    identity = claims.get("sub") or {}
    if identity.get("role") != "admin":
        return jsonify({"error": "forbidden"}), 403

    return jsonify({
        "admin": identity.get("username"),
        "role": identity.get("role"),
        "message": "Welcome to Admin API"
    }), 200

# Xác thực token có hợp lệ không
@app.route("/auth/verify", methods=["GET", "POST"])
def verify_token():
    try:
        verify_jwt_in_request()
        claims = get_jwt()
        sub = claims.get("sub") or {}
        return jsonify({"valid": True, "sub": sub}), 200
    except Exception:
        return jsonify({"valid": False}), 401

# Xử lý đăng xuất
@app.route("/auth/logout")
def logout():
    return ("", 204)

# Trang chủ chuyển đến login
@app.route("/")
def home():
    return render_template("login.html")

# Khởi chạy ứng dụng
if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)