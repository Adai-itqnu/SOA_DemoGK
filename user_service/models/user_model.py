from pymongo import MongoClient
from datetime import datetime
from config import MONGO_URI
import bcrypt

# Kết nối MongoDB
client = MongoClient(MONGO_URI)
db = client["userdb"]
collection = db["users"]

# ---------------------- HỖ TRỢ HASH MẬT KHẨU ----------------------

# Mã hóa mật khẩu thành chuỗi hash để lưu vào database
def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng bcrypt"""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")  # chuyển bytes → str để lưu Mongo

# ---------------------- CRUD NGƯỜI DÙNG ----------------------

# Lấy danh sách tất cả người dùng
def get_all_users():
    """Lấy toàn bộ người dùng"""
    users = list(collection.find({}, {"_id": 0}))
    return users

# Lấy thông tin người dùng theo username
def get_user_by_username(username):
    """Lấy thông tin người dùng theo username"""
    user = collection.find_one({"username": username}, {"_id": 0})
    return user

# Tạo người dùng mới (tự động hash mật khẩu)
def create_user(data):
    """Thêm người dùng mới (hash mật khẩu)"""
    now = datetime.utcnow()
    hashed_pw = hash_password(data["password"])

    user = {
        "id": data.get("id", collection.count_documents({}) + 1),
        "name": data.get("name", ""),
        "username": data["username"],
        "password": hashed_pw,  # 🔐 bcrypt
        "age": int(data.get("age", 0)),
        "address": data.get("address", ""),
        "role": data.get("role", "user"),
        "created_at": now,
        "updated_at": now
    }

    collection.insert_one(user)
    return user

# Cập nhật thông tin người dùng (hash lại mật khẩu nếu đổi)
def update_user(username, data):
    """Cập nhật người dùng"""
    data["updated_at"] = datetime.utcnow()
    if "password" in data and data["password"]:
        data["password"] = hash_password(data["password"])  # ✅ hash lại mật khẩu khi đổi

    result = collection.update_one({"username": username}, {"$set": data})
    return result.modified_count > 0

# Xóa người dùng khỏi database
def delete_user(username):
    """Xóa người dùng"""
    result = collection.delete_one({"username": username})
    return result.deleted_count > 0