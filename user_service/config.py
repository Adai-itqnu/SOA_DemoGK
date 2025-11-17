import os

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/user_db")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "user-service")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", 5001))
JWT_SECRET = os.environ.get("JWT_SECRET", "mysecretkey")
CONSUL_HOST = os.environ.get("CONSUL_HOST", "localhost")
CONSUL_PORT = int(os.environ.get("CONSUL_PORT", 8500))

# ✅ Thêm dòng này để user_service biết gọi Auth Service nào
AUTH_SERVICE_NAME = os.environ.get("AUTH_SERVICE_NAME", "auth-service")