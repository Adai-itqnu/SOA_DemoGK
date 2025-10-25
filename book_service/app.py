from flask import Flask, jsonify, request, render_template, session, redirect
from pymongo import MongoClient
from service_registry import register_service
from config import *
from models.book_model import *
import requests, consul, os, time

app = Flask(__name__)
app.secret_key = "book_secret"

# ---------------- HEALTH CHECK ----------------
@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200


# ==================== CONSUL DISCOVERY ====================
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

    fallback = os.environ.get("AUTH_FALLBACK_URL", "http://127.0.0.1:5000")
    print(f"[Consul] Không tìm thấy {AUTH_SERVICE_NAME}, dùng fallback {fallback}")
    return fallback


# ==================== XÁC THỰC TOKEN VỚI AUTH SERVICE ====================
def verify_token_with_auth(token):
    """Gọi Auth Service để xác thực JWT token."""
    auth_url = get_auth_service_url()
    if not auth_url:
        return {"valid": False, "error": "Không tìm thấy Auth Service"}

    header_variants = [
        {"Authorization": f"Bearer {token}"},
        {"Authorization": token}
    ]
    for headers in header_variants:
        try:
            response = requests.post(f"{auth_url}/auth/verify", headers=headers, timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            continue
    return {"valid": False, "error": "Không thể xác thực token"}


# ==================== API CHO CÁC SERVICE KHÁC ====================
@app.route("/books", methods=["GET"])
def get_books_api():
    """API lấy danh sách tất cả sách."""
    return jsonify(get_all_books()), 200


@app.route("/books/<int:bid>/decrease", methods=["POST"])
def decrease_book_quantity(bid):
    """Giảm số lượng sách khi có người mượn (gọi từ borrow_service)."""
    try:
        data = request.get_json(force=True)
        qty = int(data.get("quantity", 1))
        book = find_book_by_id(bid)
        if not book:
            return jsonify({"error": "Không tìm thấy sách"}), 404
        if book["quantity"] < qty:
            return jsonify({"error": "Số lượng sách không đủ"}), 400

        update_book(bid, {"quantity": book["quantity"] - qty})
        return jsonify({"message": "Cập nhật số lượng thành công"}), 200

    except Exception as e:
        print(f"❌ Lỗi giảm số lượng sách: {e}")
        return jsonify({"error": f"Lỗi server: {str(e)}"}), 500



# ==================== ADMIN VIEW (CRUD) ====================
@app.route("/admin")
def admin_page():
    """Trang quản lý sách chỉ dành cho admin."""
    token = request.args.get("token")
    username = request.args.get("username")

    # Fallback từ session nếu thiếu query param
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


# ==================== API CRUD SÁCH ====================
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


# ==================== ĐĂNG XUẤT ====================
@app.route("/logout")
def logout():
    """Đăng xuất và quay lại trang đăng nhập Auth Service."""
    session.clear()
    return redirect(f"{get_auth_service_url()}/login")


# ==================== MAIN ====================
if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)
