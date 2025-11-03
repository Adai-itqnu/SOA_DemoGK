from flask import Flask, jsonify, request, render_template
from service_registry import register_service
from config import *
from models.book_model import *
import requests, consul, os, time

app = Flask(__name__)
app.secret_key = "book_secret"

# Kiểm tra service có hoạt động không
@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200

# Tìm địa chỉ Auth Service từ Consul (thử nhiều lần nếu chưa sẵn sàng)
def get_auth_service_url(retries=5, delay=2):
    c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
    for attempt in range(retries):
        services = c.agent.services()
        for s in services.values():
            if s["Service"] == AUTH_SERVICE_NAME:
                return f"http://{s['Address']}:{s['Port']}"
        time.sleep(delay)
    return os.environ.get("AUTH_FALLBACK_URL", "http://127.0.0.1:5000")

# Gọi Auth Service để xác thực token
def verify_token_with_auth(token):
    auth_url = get_auth_service_url()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(f"{auth_url}/auth/verify", headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()  # {"valid": True, "sub": {...}}
    except requests.exceptions.RequestException:
        pass
    return {"valid": False, "error": "Không thể xác thực token"}

# Lấy token từ header Authorization
def get_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return auth_header.strip()

# Hiển thị trang quản lý sách cho admin
@app.route("/")
@app.route("/book")
@app.route("/book/")
def book_page():
    return render_template("books_admin.html")

# Hiển thị trang xem sách cho user
@app.route("/book-user")
def book_user_page():
    return render_template("books_user.html")

# API lấy danh sách sách (dùng nội bộ, không cần token)
@app.route("/books", methods=["GET"])
def get_books_api_internal():
    return jsonify(get_all_books()), 200

# Giảm số lượng sách (dùng khi mượn sách)
@app.route("/books/<int:bid>/decrease", methods=["POST"])
def decrease_book_quantity(bid):
    try:
        data = request.get_json(force=True)
        qty = int(data.get("quantity", 1))
        book = find_book_by_id(bid)
        if not book:
            return jsonify({"error": "Không tìm thấy sách"}), 404
        if qty >= 0 and book["quantity"] < qty:
            return jsonify({"error": "Số lượng sách không đủ"}), 400

        update_book(bid, {"quantity": book["quantity"] - qty})
        return jsonify({"message": "Cập nhật số lượng thành công"}), 200
    except Exception as e:
        return jsonify({"error": f"Lỗi server: {str(e)}"}), 500

# Lấy danh sách sách (yêu cầu token hợp lệ)
@app.route("/book-api/books", methods=["GET"])
def list_books():
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    if not verify.get("valid"):
        return jsonify({"error": "Token không hợp lệ"}), 401
    return jsonify(get_all_books()), 200

# Thêm sách mới (chỉ admin)
@app.route("/book-api/books", methods=["POST"])
def add_book_api():
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "Không có quyền"}), 403

    data = request.get_json() or {}
    create_book(data)
    return jsonify({"message": "Thêm sách thành công"}), 201

# Cập nhật thông tin sách (chỉ admin)
@app.route("/book-api/books/<int:bid>", methods=["PUT"])
def update_book_api(bid):
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "Không có quyền"}), 403

    data = request.get_json() or {}
    if update_book(bid, data):
        return jsonify({"message": "Cập nhật sách thành công"}), 200
    return jsonify({"error": "Không tìm thấy sách"}), 404

# Xóa sách (chỉ admin)
@app.route("/book-api/books/<int:bid>", methods=["DELETE"])
def delete_book_api(bid):
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    role = (verify.get("sub") or {}).get("role")
    if not verify.get("valid") or role != "admin":
        return jsonify({"error": "Không có quyền"}), 403

    if delete_book(bid):
        return jsonify({"message": "Đã xóa sách thành công"}), 200
    return jsonify({"error": "Không tìm thấy sách"}), 404

# Khởi chạy ứng dụng
if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)