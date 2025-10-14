# common/consul_helper.py
import socket
import random
from consul import Consul

def register_service(service_name, service_port):
    consul = Consul(host="127.0.0.1", port=8500)
    address = socket.gethostbyname(socket.gethostname())

    consul.agent.service.register(
        name=service_name,
        service_id=f"{service_name}-{service_port}",
        address=address,
        port=service_port,
        tags=["flask", "python"],
        check={
            "http": f"http://{address}:{service_port}/health",
            "interval": "10s",
            "timeout": "5s"
        }
    )

    print(f"✅ Registered {service_name} on Consul at port {service_port}")

def get_free_port():
    return random.randint(5000, 8000)
