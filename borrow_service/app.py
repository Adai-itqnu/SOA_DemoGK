# borrow_service/app.py
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from service_registry import register_service
from config import *
from datetime import datetime, timedelta
import requests, consul, time, os

app = Flask(__name__)
app.secret_key = "borrow_secret"

client = MongoClient(MONGO_URI)
db = client["borrow_db"]
borrows = db["borrows"]

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
        res = requests.post(f"{auth_url}/auth/verify", headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
        else:
            return {"valid": False, "error": res.text}
    except requests.exceptions.RequestException as e:
        return {"valid": False, "error": str(e)}

def get_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return auth_header.strip()

@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200

@app.route("/")
@app.route("/borrow")
@app.route("/borrow/")
def borrow_page():
    return render_template("borrow_user.html")

@app.route("/borrow-admin")
def borrow_admin_page():
    return render_template("borrow_admin.html")

@app.route("/borrow-api/list", methods=["GET"])
def list_borrows():
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    if not verify.get("valid"):
        return jsonify({"error": "Token không hợp lệ"}), 401

    sub = verify.get("sub", {})
    username = sub.get("username")
    role = sub.get("role")

    if role == "admin":
        data = list(borrows.find({}, {"_id": 0}))
    else:
        data = list(borrows.find({"username": username}, {"_id": 0}))
    return jsonify(data), 200

@app.route("/borrow-api/borrow", methods=["POST"])
def borrow_book():
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    if not verify.get("valid"):
        return jsonify({"error": "Token không hợp lệ"}), 401
    username = verify["sub"]["username"]

    data = request.get_json()
    book_id = int(data.get("book_id"))
    quantity = int(data.get("quantity", 1))
    days = int(data.get("days", 1))

    try:
        book_info = requests.get("http://127.0.0.1:5002/books").json()
        book = next((b for b in book_info if b["id"] == book_id), None)
        if not book:
            return jsonify({"error": "Không tìm thấy sách này!"}), 404
        if quantity <= 0 or book["quantity"] < quantity:
            return jsonify({"error": "Số lượng không hợp lệ"}), 400
    except Exception as e:
        return jsonify({"error": f"Lỗi khi lấy dữ liệu sách: {str(e)}"}), 500

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

@app.route("/borrow-api/<int:borrow_id>", methods=["DELETE"])
def delete_borrow(borrow_id):
    token = get_token_from_request()
    verify = verify_token_with_auth(token)
    if not verify.get("valid") or verify["sub"]["role"] != "admin":
        return jsonify({"error": "Không có quyền"}), 403

    borrow = borrows.find_one({"borrow_id": borrow_id})
    if not borrow:
        return jsonify({"error": "Không tìm thấy phiếu mượn"}), 404

    try:
        requests.post(
            f"http://127.0.0.1:5002/books/{borrow['book_id']}/decrease",
            json={"quantity": -borrow["quantity"]}
        )
    except:
        pass

    borrows.delete_one({"borrow_id": borrow_id})
    return jsonify({"message": "Đã xóa phiếu mượn"}), 200

if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)