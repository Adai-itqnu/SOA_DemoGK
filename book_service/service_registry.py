import consul
from config import SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT

def register_service():
    c = consul.Consul(host = CONSUL_HOST, port = CONSUL_PORT)
    c.agent.service.register(
        SERVICE_NAME,
        address="localhost",
        port=SERVICE_PORT,
        check=consul.Check.http(f"http://localhost:{SERVICE_PORT}/health", interval="10s")
    )
    print(f"[CONSUL] REGISTERED {SERVICE_NAME} ON PORT: {SERVICE_PORT}")
