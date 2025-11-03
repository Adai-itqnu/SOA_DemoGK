from pymongo import MongoClient
from datetime import datetime
from config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["bookdb"]
collection = db["books"]

# Tạo sách mới trong database
def create_book(data):
    now = datetime.utcnow()
    book = {
        "id": data["id"],
        "title": data["title"],
        "author": data["author"],
        "category": data.get("category", ""),
        "quantity": int(data["quantity"]),
        "created_at": now,
        "updated_at": now
    }
    collection.insert_one(book)
    return book

# Lấy danh sách tất cả sách
def get_all_books():
    books = list(collection.find({}, {"_id": 0}))
    return books

# Tìm sách theo ID
def find_book_by_id(book_id):
    book = collection.find_one({"id": book_id}, {"_id": 0})
    return book

# Lấy thông tin sách theo ID
def get_book_by_id(bid):
    return collection.find_one({"id":bid}, {"_id": 0})

# Cập nhật thông tin sách
def update_book(bid, data):
    data["updated_at"] = datetime.utcnow()
    update_data = {k: v for k, v in data.items() if k in ["title", "author", "category", "quantity"]}
    result = collection.update_one({"id": bid}, {"$set": update_data})
    return result.modified_count > 0

# Xóa sách khỏi database
def delete_book(bid):
    result = collection.delete_one({"id": bid})
    return result.deleted_count > 0