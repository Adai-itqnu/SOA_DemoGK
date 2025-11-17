import os

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/borrow_db") 
SERVICE_NAME = os.environ.get("SERVICE_NAME", "borrow-service")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", 5003))
JWT_SECRET = os.environ.get("JWT_SECRET", "mysecretkey")
CONSUL_HOST = os.environ.get("CONSUL_HOST", "localhost")
CONSUL_PORT = int(os.environ.get("CONSUL_PORT", 8500))

# ---------------- SERVICE DISCOVERY ----------------
AUTH_SERVICE_NAME = os.environ.get("AUTH_SERVICE_NAME", "auth-service")
BOOK_SERVICE_NAME = os.environ.get("BOOK_SERVICE_NAME", "book-service")
USER_SERVICE_NAME = os.environ.get("USER_SERVICE_NAME", "user-service")