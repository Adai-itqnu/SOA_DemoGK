from pymongo import MongoClient
from datetime import datetime
from config import MONGO_URI
import bcrypt

# Kết nối MongoDB
client = MongoClient(MONGO_URI)
db = client["userdb"]
users = db["users"]

# ---------------------- HÀM BCRYPT ----------------------

# Mã hóa mật khẩu thành chuỗi hash để lưu vào database
def hash_password(password: str) -> str:
    """Mã hoá mật khẩu bằng bcrypt"""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")  # chuyển bytes -> str

# Kiểm tra mật khẩu nhập vào có khớp với hash trong DB không
def check_password(password: str, hashed: str) -> bool:
    """Kiểm tra mật khẩu"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

# ---------------------- CRUD NGƯỜI DÙNG ----------------------

# Tạo user mới (user đầu tiên tự động là admin)
def create_user(data):
    now = datetime.utcnow()

    # Nếu là user đầu tiên → admin
    if users.count_documents({}) == 0:
        role = "admin"
    else:
        role = data.get("role", "user")

    hashed_pw = hash_password(data["password"])

    user = {
        "id": data.get("id", users.count_documents({}) + 1),
        "name": data["name"],
        "username": data["username"],
        "password": hashed_pw,
        "age": int(data["age"]),
        "address": data.get("address", ""),
        "role": role,
        "created_at": now,
        "updated_at": now
    }

    users.insert_one(user)
    return user

# Tìm user theo username
def find_user(username):
    """Tìm user theo username"""
    return users.find_one({"username": username})

# Lưu token vào DB sau khi đăng nhập
def update_token(username, token):
    """Cập nhật token khi đăng nhập"""
    users.update_one({"username": username}, {"$set": {"token": token}})