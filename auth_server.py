"""
gRPC Auth Server for AgriPredict Cloud Storage
Runs separately on localhost:50051. Handles register/login/OTP via DB and email.
EMBEDDED: Uses exact functions from main.py (SHA256, users.db, etc.).
"""
import grpc
from concurrent import futures
import auth_pb2
import auth_pb2_grpc
import hashlib
import sqlite3
import random
from datetime import datetime, timedelta
import os

# Embedded from your main.py: DB and auth functions (exact match)
DATABASE = 'users.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            storage_total_gb REAL DEFAULT 2.5,
            storage_used_gb REAL DEFAULT 0,
            last_login TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create OTP table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create activity logs table (for log_activity)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create default admin user if not exists
    admin_password_hash = hashlib.sha256('password1234'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, password_hash, role, storage_total_gb) 
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin', 'admin@agripredict.com', admin_password_hash, 'admin', 100))
    
    conn.commit()
    conn.close()
    print("✅ gRPC Server: Database initialized. Admin user created: admin / password1234")

def verify_user_credentials(username, password):
    """Verify user credentials"""
    conn = get_db()
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    cursor.execute('''
        SELECT id, username, email, role, storage_total_gb, storage_used_gb 
        FROM users 
        WHERE username = ? AND password_hash = ?
    ''', (username, password_hash))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'role': user[3],
            'storage_total_gb': user[4],
            'storage_used_gb': user[5]
        }
    return None

def create_user(username, email, password, role='user'):
    """Create new user"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, storage_total_gb, storage_used_gb)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, role, 2.5, 0))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_user_by_username(username):
    """Get user by username"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, email, role 
        FROM users 
        WHERE username = ?
    ''', (username,))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'role': user[3]
        }
    return None

def update_last_login(user_id):
    """Update user's last login time"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET last_login = datetime('now') 
        WHERE id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def create_otp(user_id):
    """Create OTP for user"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Clear old OTPs
    cursor.execute('DELETE FROM otp_codes WHERE user_id = ? OR expires_at < datetime("now")', (user_id,))
    
    # Generate 6-digit OTP
    otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    
    # Store OTP
    cursor.execute('''
        INSERT INTO otp_codes (user_id, otp_code, expires_at)
        VALUES (?, ?, ?)
    ''', (user_id, otp_code, expires_at))
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"📧 OTP for user {user_id}: {otp_code}")
    print(f"⏰ Valid for 10 minutes")
    print(f"{'='*60}\n")
    return otp_code

def verify_otp(user_id, otp_code):
    """Verify OTP for user"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM otp_codes 
        WHERE user_id = ? AND otp_code = ? AND used = 0 AND expires_at > datetime('now')
    ''', (user_id, otp_code))
    
    otp = cursor.fetchone()
    
    if otp:
        # Mark OTP as used
        cursor.execute('UPDATE otp_codes SET used = 1 WHERE id = ?', (otp[0],))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def log_activity(user_id, action, ip_address=None):
    """Log user activity"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO activity_logs (user_id, action, ip_address)
        VALUES (?, ?, ?)
    ''', (user_id, action, ip_address or 'grpc'))
    
    conn.commit()
    conn.close()

# Email fallback (import if available)
try:
    from email_service import email_service
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    print("⚠️  Email service not available - OTP will fallback to console")

# Initialize DB on server start
init_database()

class AuthServiceServicer(auth_pb2_grpc.AuthServiceServicer):
    def RegisterUser(self, request, context):
        username = request.username
        email = request.email
        password = request.password
        
        user_id = create_user(username, email, password, role='user')
        
        if user_id:
            user = get_user_by_username(username)
            response = auth_pb2.RegisterResponse(
                success=True,
                message="User registered successfully",
                user_id=user_id,
                role=user['role'] if user else 'user'
            )
        else:
            response = auth_pb2.RegisterResponse(
                success=False,
                message="Username or email already exists"
            )
        return response

    def Login(self, request, context):
        username = request.username
        password = request.password
        
        user_info = verify_user_credentials(username, password)
        
        if user_info:
            user_id = user_info['id']
            is_admin = user_info['role'] == 'admin'
            
            # Log activity
            log_activity(user_id, 'login', ip_address='grpc')
            
            # Update last login
            update_last_login(user_id)
            
            needs_otp = not is_admin
            otp_code = ""
            sent_via_email = False
            
            if needs_otp:
                otp_code = create_otp(user_id)
                if EMAIL_AVAILABLE:
                    sent_via_email = email_service.send_otp_email(
                        user_info['email'], otp_code, user_info['username']
                    )
                    if sent_via_email:
                        otp_code = ""  # Hide code if emailed
            
            response = auth_pb2.LoginResponse(
                success=True,
                message="Login successful",
                user_id=user_id,
                username=user_info['username'],
                email=user_info['email'],
                role=user_info['role'],
                needs_otp=needs_otp,
                is_admin=is_admin,
                otp_code=otp_code  # Return only if not emailed (console fallback)
            )
        else:
            response = auth_pb2.LoginResponse(
                success=False,
                message="Invalid credentials"
            )
        return response

    def VerifyOTP(self, request, context):
        user_id = request.user_id
        otp_code = request.otp_code
        
        success = verify_otp(user_id, otp_code)
        
        if success:
            response = auth_pb2.VerifyOTPResponse(
                success=True,
                message="OTP verified"
            )
        else:
            response = auth_pb2.VerifyOTPResponse(
                success=False,
                message="Invalid or expired OTP"
            )
        return response

    def GenerateOTP(self, request, context):
        user_id = request.user_id
        # Get user for email/username
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT email, username FROM users WHERE id = ?', (user_id,))
        user_row = cursor.fetchone()
        conn.close()
        
        if not user_row:
            return auth_pb2.GenerateOTPResponse(otp_code="", sent=False)
        
        user_email = user_row['email']
        user_username = user_row['username']
        
        otp_code = create_otp(user_id)
        sent = False
        
        if EMAIL_AVAILABLE:
            sent = email_service.send_otp_email(user_email, otp_code, user_username)
        
        response = auth_pb2.GenerateOTPResponse(
            otp_code=otp_code if not sent else "",
            sent=sent
        )
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("✅ gRPC Auth Server started on localhost:50051")
    print("🚀 Ready for Flask connections (OTP via console/email)")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()