from flask import Flask, jsonify, request, render_template, session, redirect
from pymongo import MongoClient
from service_registry import register_service
from config import *
from models.book_model import *
import requests, consul

app = Flask(__name__)
app.secret_key = "book_secret"

# ---------------- HEALTH CHECK ----------------
@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200


# ---------------- CONSUL SERVICE DISCOVERY ----------------
def get_auth_service_url():
    c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
    services = c.agent.services()
    for s in services.values():
        if s["Service"] == AUTH_SERVICE_NAME:
            return f"http://{s['Address']}:{s['Port']}"
    return "http://127.0.0.1:5000"  # fallback nếu chưa đăng ký


# ---------------- VERIFY TOKEN ----------------
def verify_token_with_auth(token):
    """Gửi token sang auth_service để xác thực"""
    auth_url = get_auth_service_url()
    try:
        # ⚠️ luôn gửi header đúng chuẩn
        res = requests.post(f"{auth_url}/auth/verify", headers={"Authorization": token})
        return res.json()
    except Exception as e:
        print("❌ Lỗi khi xác thực token:", e)
        return {"valid": False, "error": str(e)}


# ---------------- USER VIEW ----------------
@app.route("/")
def home():
    """Trang người dùng xem & mượn sách"""
    token = request.args.get("token")
    username = request.args.get("username")

    # nếu không có query string thì kiểm tra session
    if not token or not username:
        token = session.get("token")
        username = session.get("username")
        if not token or not username:
            return redirect(f"{get_auth_service_url()}/login")

    # xác thực token qua auth_service
    verify = verify_token_with_auth(token)
    if not verify.get("valid"):
        return "<h3>⚠️ Token không hợp lệ hoặc đã hết hạn!</h3>", 401

    # lưu session để không cần truyền lại mỗi lần
    session["username"] = username
    session["role"] = verify.get("role")
    session["token"] = token

    books = get_all_books()
    return render_template("books_user.html", books=books, username=username)


# ---------------- ADMIN VIEW ----------------
@app.route("/admin")
def admin_page():
    """Trang CRUD chỉ cho admin"""
    token = request.args.get("token")
    username = request.args.get("username")

    if not token or not username:
        token = session.get("token")
        username = session.get("username")
        if not token or not username:
            return redirect(f"{get_auth_service_url()}/login")

    verify = verify_token_with_auth(token)
    if not verify.get("valid"):
        return "<h3>⚠️ Token không hợp lệ hoặc đã hết hạn!</h3>", 401

    if verify.get("role") != "admin":
        return "<h3>🚫 Bạn không có quyền truy cập trang này</h3>", 403

    session["username"] = username
    session["role"] = "admin"
    session["token"] = token

    books = get_all_books()
    return render_template("books_admin.html", books=books, admin=username, token=token)


# ---------------- REST API ----------------
@app.route("/books", methods=["GET"])
def get_books_api():
    return jsonify(get_all_books()), 200


@app.route("/books", methods=["POST"])
def add_book_api():
    data = request.get_json()
    create_book(data)
    return jsonify({"message": "Thêm sách thành công"}), 201


@app.route("/books/<int:bid>", methods=["PUT"])
def update_book_api(bid):
    data = request.get_json()
    if update_book(bid, data):
        return jsonify({"message": "Cập nhật sách thành công"}), 200
    return jsonify({"error": "Không tìm thấy sách"}), 404


@app.route("/books/<int:bid>", methods=["DELETE"])
def delete_book_api(bid):
    if delete_book(bid):
        return jsonify({"message": "Đã xóa sách thành công"}), 200
    return jsonify({"error": "Không tìm thấy sách"}), 404


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    """Xóa session và quay về trang đăng nhập Auth Service"""
    session.clear()
    auth_url = get_auth_service_url()
    return redirect(f"{auth_url}/login")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)
