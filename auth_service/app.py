from flask import Flask, request, jsonify, render_template, redirect, url_for
from pymongo import MongoClient
import bcrypt
import jwt
import datetime
from consul import Consul
import config

app = Flask(__name__)

# ---------- MongoDB ----------
client = MongoClient(config.MONGO_URI)
db = client.get_database()  # database: library_db
users_col = db.users        # collection users

# Đăng ký dịch vụ với Consul
try:
    consul = Consul(host=config.CONSUL_HOST, port=config.CONSUL_PORT)
    consul.agent.service.register(
        name=config.SERVICE_NAME,
        service_id=config.SERVICE_ID,
        address=config.SERVICE_ADDRESS,
        port=config.SERVICE_PORT,
        check={
            "http": config.HEALTH_CHECK_URL,
            "interval": "10s"
        }
    )
    print(f"✅ Đăng ký {config.SERVICE_NAME} thành công tại {config.SERVICE_ADDRESS}:{config.SERVICE_PORT}")
except Exception as e:
    print("⚠️ Không kết nối được Consul (app vẫn chạy):", e)

@app.route('/health')
def health():
    return "OK", 200

# ---------- Helpers: JWT + decorators ----------
def create_token(user_doc, expires_hours=1):
    payload = {
        'username': user_doc['username'],
        'role': user_doc.get('role', 'user'),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=expires_hours)
    }
    token = jwt.encode(payload, config.SECRET_KEY, algorithm='HS256')
    # PyJWT trả str (v2.x) hoặc bytes (v1.x) => đảm bảo str
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def decode_token(token):
    return jwt.decode(token, config.SECRET_KEY, algorithms=['HS256'])

from functools import wraps

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)
        if not auth_header:
            return jsonify({'error': 'Missing Authorization header'}), 401
        parts = auth_header.split()
        if parts[0].lower() != 'bearer' or len(parts) != 2:
            return jsonify({'error': 'Invalid Authorization header format. Use: Bearer <token>'}), 401
        token = parts[1]
        try:
            data = decode_token(token)
            # anh/chị có thể attach user info vào request (gọn)
            request.user = data
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin privilege required'}), 403
        return f(*args, **kwargs)
    return decorated

# ---------- Routes: Register / Login (HTML forms + API) ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Hỗ trợ cả form html và json
        data = request.form if request.form else request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'user')  # mặc định user; bạn có thể cấp admin trực tiếp trong DB

        if not username or not password:
            return jsonify({'error': 'username và password bắt buộc'}), 400

        if users_col.find_one({'username': username}):
            return jsonify({'error': 'Username đã tồn tại'}), 400

        # Hash mật khẩu
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        # Lưu hash dưới dạng chuỗi (utf-8) để dễ đọc trong Mongo
        users_col.insert_one({
            'username': username,
            'password': hashed.decode('utf-8'),
            'role': role
        })
        # Nếu request từ form, redirect về login; nếu JSON, trả token hoặc message
        if request.form:
            return redirect(url_for('login'))
        return jsonify({'message': 'Đăng ký thành công'}), 201

    # GET -> trả form HTML
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form if request.form else request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({'error': 'username và password bắt buộc'}), 400

        user = users_col.find_one({'username': username})
        if not user:
            return jsonify({'error': 'Username hoặc password sai'}), 401

        stored_hash = user['password']
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')

        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            token = create_token(user)
            # Nếu form HTML -> show token (bạn có thể redirect frontend)
            if request.form:
                return jsonify({'message': 'Đăng nhập thành công', 'token': token})
            return jsonify({'token': token})
        else:
            return jsonify({'error': 'Username hoặc password sai'}), 401

    return render_template('login.html')

# ---------- Ví dụ route user (protected) ----------
@app.route('/profile')
@token_required
def profile():
    user = getattr(request, 'user', {})
    return jsonify({'message': 'Thông tin user', 'user': user})

# ---------- Ví dụ route admin ----------
@app.route('/admin')
@admin_required
def admin_panel():
    # Ví dụ: liệt kê users (thực tế admin service có thể gọi service khác để lấy sách / mượn)
    users = list(users_col.find({}, {'password': 0}))  # ẩn password
    # Convert ObjectId -> str nếu cần (đơn giản ở đây ta bỏ _id)
    for u in users:
        u['_id'] = str(u.get('_id'))
    return jsonify({'admin': True, 'users': users})

# ---------- Run ----------
if __name__ == '__main__':
    app.run(port=config.SERVICE_PORT, debug=True)
