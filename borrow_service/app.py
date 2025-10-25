from flask import Flask, render_template, request, jsonify, session, redirect
from pymongo import MongoClient
from service_registry import register_service
from config import *
from datetime import datetime, timedelta
import requests, consul, time, os

app = Flask(__name__)
app.secret_key = "borrow_secret"

# ---------------- MONGO ----------------
client = MongoClient(MONGO_URI)
db = client["borrow_db"]
borrows = db["borrows"]

# ---------------- CONSUL DISCOVERY ----------------
def get_auth_service_url(retries=5, delay=2):
    """Lấy URL Auth Service từ Consul (retry nếu chưa thấy)."""
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


def verify_token_with_auth(token):
    """Gọi Auth Service để xác thực JWT token."""
    auth_url = get_auth_service_url()
    if not auth_url:
        return {"valid": False, "error": "Không tìm thấy Auth Service"}

    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.post(f"{auth_url}/auth/verify", headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
        else:
            return {"valid": False, "error": res.text}
    except requests.exceptions.RequestException as e:
        return {"valid": False, "error": str(e)}


# ---------------- HEALTH CHECK ----------------
@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200


# ---------------- USER: TRANG MƯỢN SÁCH ----------------
@app.route("/")
def home():
    """Hiển thị danh sách sách cho người dùng mượn"""
    token = request.args.get("token")
    username = request.args.get("username")

    if not token or not username:
        return redirect(f"{get_auth_service_url()}/login")

    verify = verify_token_with_auth(token)
    if not verify.get("valid"):
        return "<h3>⚠️ Token không hợp lệ hoặc đã hết hạn!</h3>", 401

    # Lưu session
    session["username"] = username
    session["token"] = token
    session["role"] = verify["role"]

    # Lấy danh sách sách từ Book Service
    try:
        books = requests.get("http://127.0.0.1:5002/books").json()
    except Exception as e:
        return f"<h3>⚠️ Không thể kết nối Book Service: {str(e)}</h3>", 500

    return render_template("borrow_user.html", username=username, books=books)


# ---------------- XỬ LÝ MƯỢN SÁCH ----------------
@app.route("/borrow", methods=["POST"])
def borrow_book():
    """Xử lý người dùng mượn sách"""
    if "username" not in session:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    data = request.get_json()
    username = session["username"]
    book_id = int(data.get("book_id"))
    quantity = int(data.get("quantity", 1))
    days = int(data.get("days", 1))

    # ✅ Lấy thông tin sách từ Book Service
    try:
        book_info = requests.get("http://127.0.0.1:5002/books").json()
        book = next((b for b in book_info if b["id"] == book_id), None)
        if not book:
            return jsonify({"error": "Không tìm thấy sách này!"}), 404
    except Exception as e:
        return jsonify({"error": f"Lỗi khi lấy dữ liệu sách: {str(e)}"}), 500

    # ✅ Giảm số lượng tồn kho
    try:
        res = requests.post(
            f"http://127.0.0.1:5002/books/{book_id}/decrease",
            json={"quantity": quantity},
            timeout=5
        )
        if res.status_code != 200:
            return jsonify(res.json()), res.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Không thể kết nối Book Service: {str(e)}"}), 500

    # ✅ Lưu phiếu mượn đầy đủ dữ liệu
    new_borrow = {
        "borrow_id": borrows.count_documents({}) + 1,
        "username": username,
        "book_id": book_id,
        "book_title": book["title"],
        "quantity": quantity,
        "days": days,
        "borrow_date": datetime.utcnow(),
        "return_date": datetime.utcnow() + timedelta(days=days)
    }

    borrows.insert_one(new_borrow)
    return jsonify({"message": "Mượn sách thành công!"}), 201


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin_page():
    """Admin xem danh sách phiếu mượn"""
    token = request.args.get("token")
    username = request.args.get("username")

    if not token or not username:
        return redirect(f"{get_auth_service_url()}/login")

    verify = verify_token_with_auth(token)
    if not verify.get("valid") or verify["role"] != "admin":
        return "<h3>🚫 Không có quyền truy cập!</h3>", 403

    data = list(borrows.find({}, {"_id": 0}))
    return render_template("borrow_admin.html", admin=username, borrows=data)


# ---------------- XÓA PHIẾU MƯỢN ----------------
@app.route("/borrows/<int:borrow_id>", methods=["DELETE"])
def delete_borrow(borrow_id):
    """Xóa phiếu mượn (chỉ admin dùng)"""
    borrow = borrows.find_one({"borrow_id": borrow_id})
    if not borrow:
        return jsonify({"error": "Không tìm thấy phiếu mượn"}), 404

    # ✅ Trả lại số lượng sách về Book Service
    try:
        requests.post(
            f"http://127.0.0.1:5002/books/{borrow['book_id']}/decrease",
            json={"quantity": -borrow["quantity"]}
        )
    except:
        pass

    borrows.delete_one({"borrow_id": borrow_id})
    return jsonify({"message": "Đã xóa phiếu mượn"}), 200


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    """Đăng xuất và quay lại trang đăng nhập"""
    session.clear()
    return redirect(f"{get_auth_service_url()}/login")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)
