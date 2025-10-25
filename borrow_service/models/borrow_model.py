from pymongo import MongoClient
from datetime import datetime, timedelta
from config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["borrow_db"]

borrows = db["borrows"]
books = db["books"]  # liên kết với dữ liệu sách


def get_all_borrows():
    """Lấy toàn bộ phiếu mượn"""
    return list(borrows.find({}, {"_id": 0}))


def get_borrow_by_id(borrow_id):
    """Tìm phiếu mượn theo ID"""
    return borrows.find_one({"borrow_id": int(borrow_id)}, {"_id": 0})


def create_borrow(data):
    """Thêm phiếu mượn mới và trừ số lượng trong kho"""
    now = datetime.utcnow()
    book = books.find_one({"id": int(data["book_id"])})
    if not book:
        return {"error": "Không tìm thấy sách!"}

    if book["quantity"] < int(data["quantity"]):
        return {"error": "Không đủ số lượng trong kho!"}

    # ✅ Trừ số lượng sách trong kho
    books.update_one({"id": int(data["book_id"])}, {"$inc": {"quantity": -int(data["quantity"])}})

    # ✅ Lưu phiếu mượn
    borrow = {
        "borrow_id": borrows.count_documents({}) + 1,
        "username": data["username"],
        "book_id": int(data["book_id"]),
        "book_title": book["title"],
        "quantity": int(data["quantity"]),
        "days": int(data["days"]),
        "borrow_date": now,
        "return_date": now + timedelta(days=int(data["days"]))
    }
    borrows.insert_one(borrow)
    return {"message": "Mượn thành công!"}


def update_borrow(borrow_id, data):
    """Cập nhật thông tin phiếu mượn"""
    result = borrows.update_one({"borrow_id": int(borrow_id)}, {"$set": data})
    return result.modified_count > 0


def delete_borrow(borrow_id):
    """Xóa phiếu mượn và trả lại số lượng sách"""
    borrow = borrows.find_one({"borrow_id": int(borrow_id)})
    if not borrow:
        return False

    # ✅ Trả lại số lượng sách đã mượn
    books.update_one({"id": borrow["book_id"]}, {"$inc": {"quantity": borrow["quantity"]}})
    borrows.delete_one({"borrow_id": int(borrow_id)})
    return True
