MONGO_URI = "mongodb://localhost:27017/user_db"
SERVICE_NAME = "user-service"
SERVICE_PORT = 5002
JWT_SECRET = "mysecretkey"
CONSUL_HOST = "localhost"
CONSUL_PORT = 8500

# ✅ Thêm dòng này để user_service biết gọi Auth Service nào
AUTH_SERVICE_NAME = "auth-service"