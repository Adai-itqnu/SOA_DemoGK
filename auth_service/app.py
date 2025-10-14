from flask import Flask, jsonify
from common.consul_helper import register_service, get_free_port

app = Flask(__name__)
port = get_free_port()

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/auth/login')
def login():
    return jsonify({"message": "login OK"})

if __name__ == '__main__':
    register_service("auth-service", port)
    app.run(host="0.0.0.0", port=port)
