# config.py
MONGO_URI = "mongodb://localhost:27017/library_db"
SECRET_KEY = "af81f229725fe302f5e2d6293eb3f45e24d031f553f065cabf07c4a93f602cf8"

# Consul config
CONSUL_HOST = "localhost"
CONSUL_PORT = 8500

# Service info
SERVICE_NAME = "auth-service"
SERVICE_ID = "auth-service-1"
SERVICE_ADDRESS = "localhost"
SERVICE_PORT = 5000
HEALTH_CHECK_URL = f"http://{SERVICE_ADDRESS}:{SERVICE_PORT}/health"
