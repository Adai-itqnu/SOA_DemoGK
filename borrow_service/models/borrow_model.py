from pymongo import MongoClient
from datetime import datetime, timedelta
from config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["borrow_db"]

borrows = db["borrows"]
books = db["books"]  # liên kết với dữ liệu sách

# Lấy toàn bộ phiếu mượn
def get_all_borrows():
    """Lấy toàn bộ phiếu mượn"""
    return list(borrows.find({}, {"_id": 0}))

# Lấy phiếu mượn đang hoạt động (chưa trả)
def get_active_borrows():
    """Lấy phiếu mượn đang hoạt động (chưa trả)"""
    return list(borrows.find({"status": {"$ne": "returned"}}, {"_id": 0}))

# Lấy toàn bộ lịch sử mượn trả
def get_borrow_history():
    """Lấy toàn bộ lịch sử mượn trả"""
    return list(borrows.find({}, {"_id": 0}).sort("borrow_date", -1))

# Lấy phiếu mượn của user (chưa trả)
def get_user_borrows(username):
    """Lấy phiếu mượn của user (chưa trả)"""
    return list(borrows.find({
        "username": username,
        "status": {"$ne": "returned"}
    }, {"_id": 0}).sort("borrow_date", -1))

# Tìm phiếu mượn theo ID
def get_borrow_by_id(borrow_id):
    """Tìm phiếu mượn theo ID"""
    return borrows.find_one({"borrow_id": int(borrow_id)}, {"_id": 0})

# Tạo phiếu mượn mới và trừ số lượng sách trong kho
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
        "return_date": now + timedelta(days=int(data["days"])),
        "status": "borrowing"  # borrowing, returned
    }
    borrows.insert_one(borrow)
    return {"message": "Mượn thành công!", "borrow": borrow}

# Trả sách và cộng lại số lượng vào kho
def return_borrow(borrow_id):
    """Trả sách và cập nhật trạng thái"""
    borrow = borrows.find_one({"borrow_id": int(borrow_id)})
    if not borrow:
        return {"error": "Không tìm thấy phiếu mượn!"}
    
    if borrow.get("status") == "returned":
        return {"error": "Sách đã được trả rồi!"}
    
    # Trả lại số lượng sách
    books.update_one({"id": borrow["book_id"]}, {"$inc": {"quantity": borrow["quantity"]}})
    
    # Cập nhật trạng thái
    borrows.update_one(
        {"borrow_id": int(borrow_id)},
        {"$set": {
            "status": "returned",
            "actual_return_date": datetime.utcnow()
        }}
    )
    
    return {"message": "Trả sách thành công!"}

# Cập nhật thông tin phiếu mượn
def update_borrow(borrow_id, data):
    """Cập nhật thông tin phiếu mượn"""
    result = borrows.update_one({"borrow_id": int(borrow_id)}, {"$set": data})
    return result.modified_count > 0

# Xóa phiếu mượn và hoàn lại số lượng sách (nếu chưa trả)
def delete_borrow(borrow_id):
    """Xóa phiếu mượn và trả lại số lượng sách (nếu chưa trả)"""
    borrow = borrows.find_one({"borrow_id": int(borrow_id)})
    if not borrow:
        return False

    # ✅ Nếu chưa trả, hoàn lại số lượng sách
    if borrow.get("status") != "returned":
        books.update_one({"id": borrow["book_id"]}, {"$inc": {"quantity": borrow["quantity"]}})
    
    borrows.delete_one({"borrow_id": int(borrow_id)})
    return True