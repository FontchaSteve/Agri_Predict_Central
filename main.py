"""
AgriPredict Cloud Storage - Admin + User Dashboard with Authentication
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import os
import json
import hashlib
import shutil
import random
import sqlite3
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__, template_folder='templates')
app.secret_key = 'agripredict-2024-secure-auth-key'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Storage settings
TOTAL_STORAGE_GB = 2.5  # 2.5GB total
NODES = 5
STORAGE_PER_NODE_MB = 500
REPLICATION_FACTOR = 2  # Each file stored on 2 nodes

# Create directories
os.makedirs('temp', exist_ok=True)
os.makedirs('metadata', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Database setup
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
    
    # Create activity logs table
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
    print("✅ Database initialized. Admin user created: admin / password1234")

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

def get_user_by_id(user_id):
    """Get user by ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, email, role, storage_total_gb, storage_used_gb 
        FROM users 
        WHERE id = ?
    ''', (user_id,))
    
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

def get_user_storage_info(user_id):
    """Get user storage information"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT storage_total_gb, storage_used_gb 
        FROM users 
        WHERE id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        total_gb = result[0]
        used_gb = result[1]
        available_gb = total_gb - used_gb
        percent_used = (used_gb / total_gb) * 100 if total_gb > 0 else 0
        
        return {
            'total_gb': total_gb,
            'used_gb': used_gb,
            'available_gb': available_gb,
            'percent_used': percent_used
        }
    return None

def update_user_storage(user_id, size_gb):
    """Update user storage usage"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET storage_used_gb = storage_used_gb + ? 
        WHERE id = ?
    ''', (size_gb, user_id))
    
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
    
    print(f"📧 OTP for user {user_id}: {otp_code} (valid for 10 minutes)")
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

def log_activity(user_id, action, ip_address):
    """Log user activity"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO activity_logs (user_id, action, ip_address)
        VALUES (?, ?, ?)
    ''', (user_id, action, ip_address))
    
    conn.commit()
    conn.close()

# Simple email service for development
class EmailService:
    def send_otp_email(self, email, otp_code, username):
        """Send OTP email (console output for development)"""
        print("\n" + "="*60)
        print(f"📧 OTP Email to: {email}")
        print(f"👤 User: {username}")
        print(f"🔑 OTP Code: {otp_code}")
        print(f"⏰ Valid for: 10 minutes")
        print("="*60 + "\n")
        return True

email_service = EmailService()

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect('/login')
        
        user = get_user_by_id(session['user_id'])
        if not user or user['role'] != 'admin':
            flash('Admin access required', 'error')
            return redirect('/')
        
        return f(*args, **kwargs)
    return decorated_function

def otp_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        
        # Admin doesn't need OTP
        user = get_user_by_id(session['user_id'])
        if user and user['role'] == 'admin':
            return f(*args, **kwargs)
        
        # Normal users need OTP verification
        if session.get('otp_verified') != True:
            flash('OTP verification required', 'error')
            return redirect('/verify-otp')
        
        return f(*args, **kwargs)
    return decorated_function

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect('/admin')
        elif session.get('otp_verified'):
            return redirect('/')
        else:
            return redirect('/verify-otp')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = verify_user_credentials(username, password)
        
        if user:
            # Store user info in session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['email'] = user['email']
            
            # Update last login
            update_last_login(user['id'])
            
            # Log activity
            log_activity(user['id'], 'login', request.remote_addr)
            
            # Role-based handling
            if user['role'] == 'admin':
                # Admin doesn't need OTP
                session['otp_verified'] = True
                flash('Welcome back, Admin!', 'success')
                return redirect('/admin')
            else:
                # Generate OTP for normal users
                otp_code = create_otp(user['id'])
                
                # Send OTP via email
                email_sent = email_service.send_otp_email(
                    user['email'], 
                    otp_code, 
                    user['username']
                )
                
                if email_sent:
                    flash(f'OTP sent to {user["email"]}. Check your email.', 'success')
                else:
                    flash(f'OTP: {otp_code} (Email not configured, check console)', 'info')
                
                return redirect('/verify-otp')
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if 'user_id' in session:
        return redirect('/')
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        errors = []
        
        if len(username) < 3:
            errors.append('Username must be at least 3 characters')
        
        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        # Check if user exists
        existing_user = get_user_by_username(username)
        if existing_user:
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        # Create user
        user_id = create_user(username, email, password, role='user')
        
        if user_id:
            flash('Registration successful! Please login.', 'success')
            return redirect('/login')
        else:
            flash('Registration failed. Username or email may already exist.', 'error')
    
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
@login_required
def verify_otp():
    """Verify OTP for normal users"""
    # If already verified or admin, redirect
    if session.get('role') == 'admin' or session.get('otp_verified'):
        if session.get('role') == 'admin':
            return redirect('/admin')
        return redirect('/')
    
    if request.method == 'POST':
        otp_code = request.form.get('otp')
        
        if not otp_code or len(otp_code) != 6:
            flash('Please enter a valid 6-digit OTP', 'error')
            return render_template('verify_otp.html', email=session.get('email'))
        
        # Use the local verify_otp function
        if verify_otp(session['user_id'], otp_code):
            session['otp_verified'] = True
            flash('OTP verified successfully!', 'success')
            return redirect('/')
        else:
            flash('Invalid or expired OTP code', 'error')
    
    return render_template('verify_otp.html', email=session.get('email'))

@app.route('/resend-otp', methods=['POST'])
@login_required
def resend_otp():
    """Resend OTP code"""
    if session.get('role') == 'admin' or session.get('otp_verified'):
        return redirect('/')
    
    # Generate new OTP
    otp_code = create_otp(session['user_id'])
    
    # Send OTP via email
    email_sent = email_service.send_otp_email(
        session.get('email'), 
        otp_code, 
        session.get('username')
    )
    
    if email_sent:
        flash('New OTP sent to your email.', 'success')
    else:
        flash(f'New OTP: {otp_code} (Email not configured, check console)', 'info')
    
    return redirect('/verify-otp')

@app.route('/logout')
def logout():
    """User logout"""
    user_id = session.get('user_id')
    if user_id:
        log_activity(user_id, 'logout', request.remote_addr)
    
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect('/login')

# NodeManager and DistributedStorage classes (same as before)
class NodeManager:
    def __init__(self):
        self.nodes_file = 'nodes.json'
        self.nodes = self.load_nodes()
    
    def load_nodes(self):
        if os.path.exists(self.nodes_file):
            with open(self.nodes_file, 'r') as f:
                return json.load(f)
        
        nodes = []
        for i in range(1, NODES + 1):
            nodes.append({
                'id': f'N{i}',
                'name': f'Node {i}',
                'status': 'active',
                'storage_used_mb': 0,
                'storage_total_mb': STORAGE_PER_NODE_MB,
                'cpu_cores': random.randint(2, 8),
                'memory_gb': random.randint(4, 16),
                'bandwidth_mbps': random.choice([800, 1000, 1200, 1400]),
                'transfers': 0,
                'files': 0,
                'created': datetime.now().isoformat()
            })
        
        self.save_nodes(nodes)
        return nodes
    
    def save_nodes(self, nodes):
        with open(self.nodes_file, 'w') as f:
            json.dump(nodes, f, indent=2)
    
    def get_active_nodes(self):
        return [node for node in self.nodes if node['status'] == 'active']
    
    def get_node_stats(self):
        active = len([n for n in self.nodes if n['status'] == 'active'])
        total = len(self.nodes)
        total_storage_mb = sum(n['storage_total_mb'] for n in self.nodes)
        used_storage_mb = sum(n['storage_used_mb'] for n in self.nodes)
        
        return {
            'active_nodes': active,
            'total_nodes': total,
            'storage_used_gb': round(used_storage_mb / 1024, 2),
            'storage_total_gb': round(total_storage_mb / 1024, 2),
            'storage_percent': round((used_storage_mb / total_storage_mb) * 100, 1) if total_storage_mb > 0 else 0,
            'total_files': sum(n['files'] for n in self.nodes),
            'total_transfers': sum(n['transfers'] for n in self.nodes)
        }

class DistributedStorage:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        self.base_path = os.path.join(os.path.expanduser("~"), "AgriPredict_Cloud")
        os.makedirs(self.base_path, exist_ok=True)
        
        for node in node_manager.nodes:
            node_path = os.path.join(self.base_path, node['id'])
            os.makedirs(node_path, exist_ok=True)
    
    def upload_file(self, file_stream, filename, user_id=None):
        try:
            # Check user storage limit
            if user_id:
                storage_info = get_user_storage_info(user_id)
                if storage_info:
                    file_stream.seek(0, 2)
                    file_size_bytes = file_stream.tell()
                    file_size_gb = round(file_size_bytes / (1024 * 1024 * 1024), 3)
                    file_stream.seek(0)
                    
                    if storage_info['used_gb'] + file_size_gb > storage_info['total_gb']:
                        return {'error': 'Exceeds your storage limit'}
            
            active_nodes = self.node_manager.get_active_nodes()
            if len(active_nodes) < REPLICATION_FACTOR:
                return {'error': f'Need at least {REPLICATION_FACTOR} active nodes for replication'}
            
            temp_path = os.path.join('temp', f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(filename)}")
            file_stream.save(temp_path)
            
            file_id = hashlib.md5(f"{filename}{datetime.now()}".encode()).hexdigest()[:12]
            file_size = os.path.getsize(temp_path)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            file_size_gb = round(file_size_mb / 1024, 3)
            
            selected_nodes = random.sample(active_nodes, min(REPLICATION_FACTOR, len(active_nodes)))
            
            metadata = {
                'file_id': file_id,
                'filename': secure_filename(filename),
                'original_name': filename,
                'size_mb': file_size_mb,
                'size_gb': file_size_gb,
                'upload_date': datetime.now().isoformat(),
                'replicated_nodes': [node['id'] for node in selected_nodes],
                'user_id': user_id
            }
            
            for node in selected_nodes:
                node_path = os.path.join(self.base_path, node['id'])
                dest_path = os.path.join(node_path, f"{file_id}_{secure_filename(filename)}")
                shutil.copy2(temp_path, dest_path)
                
                node['storage_used_mb'] += file_size_mb
                node['files'] += 1
            
            metadata_path = os.path.join('metadata', f"{file_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.node_manager.save_nodes(self.node_manager.nodes)
            
            if user_id:
                update_user_storage(user_id, file_size_gb)
                log_activity(user_id, f'upload:{filename}', request.remote_addr)
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return {
                'success': True,
                'file_id': file_id,
                'filename': filename,
                'size_mb': file_size_mb,
                'size_gb': file_size_gb,
                'replicated_on': len(selected_nodes)
            }
        except Exception as e:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return {'error': f'Upload failed: {str(e)}'}
    
    def get_user_files(self, user_id):
        try:
            files = []
            if os.path.exists('metadata'):
                for filename in os.listdir('metadata'):
                    if filename.endswith('.json'):
                        file_id = filename.replace('.json', '')
                        with open(os.path.join('metadata', filename), 'r') as f:
                            metadata = json.load(f)
                        
                        if metadata.get('user_id') == user_id:
                            files.append({
                                'id': file_id,
                                'name': metadata['filename'],
                                'original_name': metadata['original_name'],
                                'size_mb': metadata['size_mb'],
                                'size_gb': metadata.get('size_gb', round(metadata['size_mb'] / 1024, 3)),
                                'upload_date': metadata['upload_date'],
                                'replicated_on': len(metadata['replicated_nodes'])
                            })
            return files
        except Exception as e:
            print(f"Error loading user files: {e}")
            return []

# Initialize managers
node_manager = NodeManager()
storage = DistributedStorage(node_manager)

# Helper function to format storage display
def format_storage_display(storage_info):
    if not storage_info:
        return {
            'total_gb': 2.5,
            'used_gb': 0,
            'available_gb': 2.5,
            'percent_used': 0,
            'used_gb_display': '0.000',
            'available_gb_display': '2.500',
            'percent_used_display': 0
        }
    
    used_gb = round(storage_info.get('used_gb', 0), 3)
    total_gb = storage_info.get('total_gb', 2.5)
    available_gb = round(total_gb - used_gb, 3)
    percent_used = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0
    
    return {
        'total_gb': total_gb,
        'used_gb': used_gb,
        'available_gb': available_gb,
        'percent_used': percent_used,
        'used_gb_display': f'{used_gb:.3f}',
        'available_gb_display': f'{available_gb:.3f}',
        'percent_used_display': percent_used
    }

# Protected routes
@app.route('/')
@login_required
@otp_required
def home():
    """User Dashboard"""
    try:
        storage_info = get_user_storage_info(session['user_id'])
        formatted_storage = format_storage_display(storage_info)
        files = storage.get_user_files(session['user_id'])
        
        return render_template('user_dashboard.html',
                              storage=formatted_storage,
                              files=files,
                              total_files=len(files),
                              username=session.get('username'))
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        default_storage = format_storage_display(None)
        return render_template('user_dashboard.html', 
                             storage=default_storage, 
                             files=[], 
                             username=session.get('username'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin Dashboard"""
    try:
        nodes = node_manager.nodes
        stats = node_manager.get_node_stats()
        
        return render_template('admin_dashboard.html',
                             nodes=nodes,
                             stats=stats,
                             username=session.get('username'))
    except Exception as e:
        flash(f'Error loading admin dashboard: {str(e)}', 'error')
        return render_template('admin_dashboard.html', nodes=[], stats={}, username=session.get('username'))

@app.route('/upload', methods=['POST'])
@login_required
@otp_required
def upload():
    """Upload file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        result = storage.upload_file(file, file.filename, session['user_id'])
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': f'Upload route error: {str(e)}'}), 500

@app.route('/api/storage')
@login_required
@otp_required
def api_storage():
    """Get storage info for current user"""
    storage_info = get_user_storage_info(session['user_id'])
    formatted_storage = format_storage_display(storage_info)
    return jsonify(formatted_storage)

@app.route('/api/files')
@login_required
@otp_required
def api_files():
    """Get files list for current user"""
    files = storage.get_user_files(session['user_id'])
    return jsonify({'files': files})

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    print("=" * 60)
    print("🚀 AgriPredict Distributed Cloud Storage")
    print("🔐 Complete Authentication System with OTP via Email")
    print("=" * 60)
    print(f"📊 Admin Login: username='admin', password='password1234'")
    print(f"🔐 Login: http://localhost:5000/login")
    print(f"📝 Register: http://localhost:5000/register")
    print(f"🌐 User Dashboard: http://localhost:5000")
    print(f"⚙️  Admin Dashboard: http://localhost:5000/admin")
    print("=" * 60)
    print("📧 OTP Codes are printed to console (for development)")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)