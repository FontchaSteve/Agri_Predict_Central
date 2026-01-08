"""
Authentication Helper Functions for AgriPredict Cloud Storage
"""
import sqlite3
import hashlib
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Database connection
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'user')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            storage_limit_gb FLOAT DEFAULT 2.5,
            storage_used_gb FLOAT DEFAULT 0.0,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            email_verified BOOLEAN DEFAULT 0
        )
    ''')
    
    # OTP codes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            otp_code VARCHAR(6) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_used BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Login attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ip_address VARCHAR(45),
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Create default admin if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        admin_hash = generate_password_hash('password1234')
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, storage_limit_gb, is_verified, email_verified)
            VALUES (?, ?, ?, ?, ?, 1, 1)
        ''', ('admin', 'admin@agripredict.com', admin_hash, 'admin', 10.0))
        print("✅ Created default admin: admin / password1234")
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

# User management functions
def create_user(username, email, password, role='user'):
    """Create a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
    if cursor.fetchone():
        conn.close()
        return None
    
    # Create user
    password_hash = generate_password_hash(password)
    cursor.execute('''
        INSERT INTO users (username, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    ''', (username, email, password_hash, role))
    
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

def verify_user_credentials(username, password):
    """Verify user credentials"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, email, role, password_hash, storage_limit_gb, storage_used_gb 
        FROM users 
        WHERE username = ? AND is_active = 1
    ''', (username,))
    
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        return dict(user)
    return None

def update_last_login(user_id):
    """Update user's last login time"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                  (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

# OTP functions
def generate_otp_code():
    """Generate a 6-digit OTP code"""
    return ''.join(random.choices(string.digits, k=6))

def create_otp(user_id):
    """Create OTP for user"""
    otp_code = generate_otp_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Invalidate old OTPs
    cursor.execute('UPDATE otp_codes SET is_used = 1 WHERE user_id = ? AND is_used = 0', 
                  (user_id,))
    
    # Create new OTP
    cursor.execute('''
        INSERT INTO otp_codes (user_id, otp_code, expires_at)
        VALUES (?, ?, ?)
    ''', (user_id, otp_code, expires_at))
    
    conn.commit()
    conn.close()
    return otp_code

def verify_otp(user_id, otp_code):
    """Verify OTP code"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM otp_codes 
        WHERE user_id = ? AND otp_code = ? AND is_used = 0 
        AND expires_at > ? 
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id, otp_code, datetime.now()))
    
    otp_record = cursor.fetchone()
    
    if otp_record:
        # Mark OTP as used
        cursor.execute('UPDATE otp_codes SET is_used = 1 WHERE id = ?', (otp_record['id'],))
        
        # Mark user as verified
        cursor.execute('UPDATE users SET is_verified = 1 WHERE id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def get_user_by_id(user_id):
    """Get user by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_username(username):
    """Get user by username"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_user_storage(user_id, file_size_gb):
    """Update user's storage usage"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET storage_used_gb = storage_used_gb + ?
        WHERE id = ?
    ''', (file_size_gb, user_id))
    conn.commit()
    conn.close()

def get_user_storage_info(user_id):
    """Get user's storage information"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT storage_limit_gb, storage_used_gb FROM users WHERE id = ?', (user_id,))
    storage = cursor.fetchone()
    conn.close()
    
    if storage:
        return {
            'total_gb': storage['storage_limit_gb'],
            'used_gb': storage['storage_used_gb'],
            'available_gb': round(storage['storage_limit_gb'] - storage['storage_used_gb'], 2),
            'percent_used': round((storage['storage_used_gb'] / storage['storage_limit_gb']) * 100, 1) 
                          if storage['storage_limit_gb'] > 0 else 0
        }
    return None

def log_activity(user_id, action, ip_address=None):
    """Log user activity"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO login_attempts (user_id, ip_address, attempt_time, success)
            VALUES (?, ?, ?, 1)
        ''', (user_id, ip_address, datetime.now()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging activity: {e}")