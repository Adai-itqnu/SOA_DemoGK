from flask import Flask, jsonify, request, render_template, session, redirect
from pymongo import MongoClient
from service_registry import register_service
from config import *
from models.book_model import *
import requests, consul, os
import time

app = Flask(__name__)
app.secret_key = "book_secret"


# ---------------- HEALTH CHECK ----------------
@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200


# ---------------- CONSUL SERVICE DISCOVERY ----------------
# def get_auth_service_url():
#     """Tìm URL của auth-service trong Consul"""
#     c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
#     services = c.agent.services()
#     for s in services.values():
#         if s["Service"] == AUTH_SERVICE_NAME:
#             return f"http://{s['Address']}:{s['Port']}"
#     return "http://127.0.0.1:5000"  # fallback nếu chưa đăng ký
def get_auth_service_url(retries=5, delay=2):
    """Lấy URL Auth Service từ Consul, retry nếu chưa có. Nếu không tìm thấy -> fallback."""
    c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
    for attempt in range(retries):
        services = c.agent.services()
        for s in services.values():
            if s["Service"] == AUTH_SERVICE_NAME:
                return f"http://{s['Address']}:{s['Port']}"
        print(f"[Consul] Chưa thấy {AUTH_SERVICE_NAME}, thử lại ({attempt+1}/{retries})...")
        time.sleep(delay)

    # fallback từ env hoặc mặc định về localhost
    fallback = os.environ.get("AUTH_FALLBACK_URL", "http://127.0.0.1:5000")
    print(f"[Consul] Không tìm thấy {AUTH_SERVICE_NAME}, dùng fallback {fallback}")
    return fallback

# ==================== HÀM XÁC THỰC TOKEN VỚI AUTH SERVICE ====================

def verify_token_with_auth(token):
    """Gọi Auth Service để xác thực JWT token. Trả về dict với key 'valid' và optional 'error'."""
    auth_url = get_auth_service_url()
    if not auth_url:
        return {"valid": False, "error": "Không tìm thấy Auth Service"}

    # thử cả 2 format header (Bearer <token>) và (token)
    header_variants = [
        {"Authorization": f"Bearer {token}"},
        {"Authorization": token}
    ]
    last_err = None
    for headers in header_variants:
        try:
            response = requests.post(
                f"{auth_url}/auth/verify",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    return {"valid": False, "error": f"Auth trả JSON không hợp lệ: {response.text}"}
            else:
                last_err = f"Auth trả lỗi {response.status_code}: {response.text}"
                # tiếp tục thử biến thể header khác
        except requests.exceptions.RequestException as e:
            last_err = f"Request error: {str(e)}"
    return {"valid": False, "error": last_err or "Không thể xác thực token"}


# ---------------- USER VIEW ----------------
@app.route("/")
def home():
    """Trang người dùng xem và mượn sách"""
    token = request.args.get("token")
    username = request.args.get("username")

    # Nếu không có thì fallback về session
    if not token or not username:
        token = session.get("token")
        username = session.get("username")
        if not token or not username:
            return redirect(f"{get_auth_service_url()}/login")

    # Xác thực token qua Auth Service
    verify = verify_token_with_auth(token)
    if not verify.get("valid"):
        return "<h3>⚠️ Token không hợp lệ hoặc đã hết hạn!</h3>", 401

    # ✅ Ghi session để không cần truyền query mỗi lần
    # session["username"] = verify.get("username", username)
    # session["role"] = verify.get("role", "user")
    session["username"] = verify["username"]
    session["role"] = verify["role"]
    session["token"] = token

    books = get_all_books()
    return render_template("books_user.html", books=books, username=session["username"])


# ---------------- ADMIN VIEW ----------------
@app.route("/admin")
def admin_page():
    """Trang CRUD chỉ cho admin"""
    token = request.args.get("token")
    username = request.args.get("username")

    # Fallback lấy từ session nếu thiếu query param
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

    session["username"] = verify["username"]
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
    """Đăng xuất và quay lại trang đăng nhập Auth Service"""
    session.clear()
    return redirect(f"{get_auth_service_url()}/login")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)