from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_jwt_extended import JWTManager, create_access_token, decode_token
from datetime import timedelta
from models.user_model import create_user, find_user, update_token, check_password
from service_registry import register_service
from config import *
import consul
import jwt as pyjwt

app = Flask(__name__)
app.secret_key = "auth_secret"

# JWT setup
app.config["JWT_SECRET_KEY"] = JWT_SECRET
jwt_manager = JWTManager(app)


# ---------------- HEALTH CHECK ----------------
@app.route("/health")
def health():
    return jsonify({"status": "UP"}), 200


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "GET":
        return render_template("register.html")

    data = request.get_json() if request.is_json else request.form

    username = data.get("username")
    password = data.get("password")
    name = data.get("name")
    age = data.get("age")
    address = data.get("address", "")

    if not username or not password or not name or not age:
        return render_template("register.html", msg="Thiếu thông tin!")

    if find_user(username):
        return render_template("register.html", msg="Tên đăng nhập đã tồn tại!")

    # ✅ Lưu người dùng mới (mặc định role = user)
    create_user({
        "username": username,
        "password": password,
        "name": name,
        "age": age,
        "address": address
    })

    return redirect(url_for("login_page"))


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json() if request.is_json else request.form
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return render_template("login.html", msg="Thiếu thông tin đăng nhập!")

    user = find_user(username)
    if not user or not check_password(password, user["password"]):
        return render_template("login.html", msg="Sai tên đăng nhập hoặc mật khẩu!")

    identity = {"username": username, "role": user["role"]}
    token = create_access_token(identity=identity, expires_delta=timedelta(hours=1))
    update_token(username, token)

    session["username"] = username
    session["token"] = token
    session["role"] = user["role"]

    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    else:
        # ✅ Chuyển sang borrow_service cho người dùng mượn sách
        return redirect(f"http://127.0.0.1:5003/?token={token}&username={username}")



# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin_dashboard():
    """Trang dashboard trung tâm của admin"""
    if "username" not in session or session.get("role") != "admin":
        return redirect(url_for("login_page"))

    username = session["username"]
    token = session["token"]

    return render_template("admin_dashboard.html", admin=username, token=token)


# ---------------- VERIFY TOKEN API ----------------
@app.route("/auth/verify", methods=["POST"])
def verify_token():
    auth_header = request.headers.get("Authorization")
    
    print("Auth Debug Info:")
    print(f"Received Authorization header: {auth_header}")
    
    if not auth_header:
        return jsonify({"valid": False, "error": "Thiếu token"}), 401

    try:
        # Extract token from Bearer header
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()
        else:
            token = auth_header.strip()
            
        print(f"Extracted token: {token}")

        # Use PyJWT (pyjwt) for low-level decode/validation
        decoded = pyjwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            options={"verify_sub": False}  # Don't verify subject claim
        )
        
        print(f"Decoded token: {decoded}")
        
        # Extract identity from sub claim
        if not isinstance(decoded.get('sub'), dict):
            return jsonify({"valid": False, "error": "Invalid token format"}), 401
            
        identity = decoded['sub']
        if not all(k in identity for k in ['username', 'role']):
            return jsonify({"valid": False, "error": "Missing required claims"}), 401

        return jsonify({
            "valid": True,
            "username": identity["username"],
            "role": identity["role"]
        }), 200
        
    except pyjwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "Token has expired"}), 401

    except pyjwt.InvalidTokenError as e:
        print(f"Token validation error: {str(e)}")
        return jsonify({"valid": False, "error": str(e)}), 401
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({"valid": False, "error": "Invalid token"}), 401


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect(url_for("login_page"))


if __name__ == "__main__":
    register_service()
    app.run(port=SERVICE_PORT, debug=True)