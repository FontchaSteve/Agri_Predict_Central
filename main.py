"""
AgriPredict Cloud Storage - Admin + User Dashboard with Authentication
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import os
import json
import hashlib
import shutil
import random
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import wraps

# Import authentication helpers
from auth_helpers import (
    init_database, verify_user_credentials, create_user, 
    update_last_login, create_otp, verify_otp as verify_otp_auth,
    get_user_by_id, get_user_storage_info, update_user_storage,
    log_activity, get_user_by_username
)

# Import email service
from email_service import email_service

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
        
        # FIXED: Use the renamed imported function instead of calling itself recursively
        if verify_otp_auth(session['user_id'], otp_code):
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

# Keep existing NodeManager and DistributedStorage classes
class NodeManager:
    def __init__(self):
        self.nodes_file = 'nodes.json'
        self.nodes = self.load_nodes()
    
    def load_nodes(self):
        """Load nodes from file or create default"""
        if os.path.exists(self.nodes_file):
            with open(self.nodes_file, 'r') as f:
                return json.load(f)
        
        # Create default nodes
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
        """Save nodes to file"""
        with open(self.nodes_file, 'w') as f:
            json.dump(nodes, f, indent=2)
    
    def get_active_nodes(self):
        """Get active nodes for file storage"""
        return [node for node in self.nodes if node['status'] == 'active']
    
    def start_node(self, node_id):
        """Start a node"""
        for node in self.nodes:
            if node['id'] == node_id:
                node['status'] = 'active'
                self.save_nodes(self.nodes)
                return True
        return False
    
    def stop_node(self, node_id):
        """Stop a node"""
        for node in self.nodes:
            if node['id'] == node_id:
                node['status'] = 'stopped'
                self.save_nodes(self.nodes)
                return True
        return False
    
    def delete_node(self, node_id):
        """Delete a node (mark as deleted)"""
        self.nodes = [node for node in self.nodes if node['id'] != node_id]
        self.save_nodes(self.nodes)
        return True
    
    def add_node(self, node_data):
        """Add a new node"""
        new_node = {
            'id': f'N{len(self.nodes) + 1}',
            'name': node_data.get('name', f'Node {len(self.nodes) + 1}'),
            'status': 'active',
            'storage_used_mb': 0,
            'storage_total_mb': node_data.get('storage_total_mb', STORAGE_PER_NODE_MB),
            'cpu_cores': node_data.get('cpu_cores', 4),
            'memory_gb': node_data.get('memory_gb', 8),
            'bandwidth_mbps': node_data.get('bandwidth_mbps', 1000),
            'transfers': 0,
            'files': 0,
            'created': datetime.now().isoformat()
        }
        self.nodes.append(new_node)
        self.save_nodes(self.nodes)
        return new_node
    
    def get_node_stats(self):
        """Get overall node statistics"""
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
        """Upload file with replication across nodes"""
        try:
            # Check user storage limit
            if user_id:
                storage_info = get_user_storage_info(user_id)
                if storage_info:
                    file_stream.seek(0, 2)
                    file_size_bytes = file_stream.tell()
                    file_size_gb = file_size_bytes / (1024 * 1024 * 1024)
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
            file_size_mb = file_size / (1024 * 1024)
            file_size_gb = file_size_mb / 1024
            
            # Check storage space
            node_stats = self.node_manager.get_node_stats()
            required_space_gb = file_size_gb * REPLICATION_FACTOR
            available_gb = node_stats['storage_total_gb'] - node_stats['storage_used_gb']
            
            if available_gb < required_space_gb:
                os.remove(temp_path)
                return {'error': f'Not enough total storage space'}
            
            selected_nodes = random.sample(active_nodes, min(REPLICATION_FACTOR, len(active_nodes)))
            
            # Check per node availability
            for node in selected_nodes:
                if node['storage_total_mb'] - node['storage_used_mb'] < file_size_mb:
                    os.remove(temp_path)
                    return {'error': 'Not enough space on selected replication nodes.'}
            
            # Create metadata with user_id
            metadata = {
                'file_id': file_id,
                'filename': secure_filename(filename),
                'original_name': filename,
                'size_mb': round(file_size_mb, 2),
                'size_bytes': file_size,
                'size_gb': round(file_size_gb, 3),  # Store GB with 3 decimal places
                'upload_date': datetime.now().isoformat(),
                'replicated_nodes': [node['id'] for node in selected_nodes],
                'user_id': user_id
            }
            
            # Save file to nodes
            for node in selected_nodes:
                node_path = os.path.join(self.base_path, node['id'])
                dest_path = os.path.join(node_path, f"{file_id}_{secure_filename(filename)}")
                
                shutil.copy2(temp_path, dest_path)
                
                node['storage_used_mb'] += file_size_mb
                node['files'] += 1
            
            # Save metadata
            metadata_path = os.path.join('metadata', f"{file_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.node_manager.save_nodes(self.node_manager.nodes)
            
            # Update user storage usage
            if user_id:
                update_user_storage(user_id, round(file_size_gb, 3))  # Store with 3 decimal places
                log_activity(user_id, f'upload:{filename}', request.remote_addr)
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return {
                'success': True,
                'file_id': file_id,
                'filename': filename,
                'size_mb': round(file_size_mb, 2),
                'size_gb': round(file_size_gb, 3),
                'replicated_on': len(selected_nodes),
                'nodes': [node['id'] for node in selected_nodes]
            }
        except Exception as e:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                 os.remove(temp_path)
            return {'error': f'Upload failed: {str(e)}'}
    
    def download_file(self, file_id):
        """Download file from any available node"""
        try:
            metadata_path = os.path.join('metadata', f"{file_id}.json")
            
            if not os.path.exists(metadata_path):
                return {'error': 'File not found'}
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            for node_id in metadata['replicated_nodes']:
                node_path = os.path.join(self.base_path, node_id)
                file_path = os.path.join(node_path, f"{file_id}_{metadata['filename']}")
                
                if os.path.exists(file_path):
                    # Log download activity
                    if metadata.get('user_id'):
                        log_activity(metadata['user_id'], f'download:{metadata["filename"]}', request.remote_addr)
                    
                    return {
                        'success': True,
                        'path': file_path,
                        'filename': metadata['original_name'],
                        'from_node': node_id
                    }
            
            return {'error': 'File not found on any node'}
        except Exception as e:
            return {'error': f'Download failed: {str(e)}'}
    
    def delete_file(self, file_id, user_id=None):
        """Delete file from all nodes"""
        try:
            metadata_path = os.path.join('metadata', f"{file_id}.json")
            
            if not os.path.exists(metadata_path):
                return {'error': 'File not found'}
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Check if user owns this file (unless admin)
            if user_id and metadata.get('user_id') != user_id:
                user = get_user_by_id(user_id)
                if not user or user['role'] != 'admin':
                    return {'error': 'You do not have permission to delete this file'}
            
            deleted_count = 0
            for node_id in metadata['replicated_nodes']:
                node_path = os.path.join(self.base_path, node_id)
                file_path = os.path.join(node_path, f"{file_id}_{metadata['filename']}")
                
                if os.path.exists(file_path):
                    for node in self.node_manager.nodes:
                        if node['id'] == node_id:
                            node['storage_used_mb'] = max(0, node['storage_used_mb'] - metadata['size_mb'])
                            node['files'] = max(0, node['files'] - 1)
                            break
                    
                    os.remove(file_path)
                    deleted_count += 1
            
            os.remove(metadata_path)
            self.node_manager.save_nodes(self.node_manager.nodes)
            
            # Update user storage usage (subtract file size)
            if user_id and metadata.get('user_id') == user_id:
                # Subtract the file size from user storage
                file_size_gb = metadata.get('size_gb', metadata['size_mb'] / 1024)
                update_user_storage(user_id, -file_size_gb)  # Negative to subtract
                log_activity(user_id, f'delete:{metadata["original_name"]}', request.remote_addr)
            
            return {
                'success': True,
                'deleted_from': deleted_count,
                'filename': metadata['original_name']
            }
        except Exception as e:
            return {'error': f'Delete failed: {str(e)}'}
    
    def get_user_files(self, user_id):
        """Get files for a specific user"""
        try:
            files = []
            
            if os.path.exists('metadata'):
                for filename in os.listdir('metadata'):
                    if filename.endswith('.json'):
                        file_id = filename.replace('.json', '')
                        with open(os.path.join('metadata', filename), 'r') as f:
                            metadata = json.load(f)
                        
                        # Only return files belonging to this user
                        if metadata.get('user_id') == user_id:
                            files.append({
                                'id': file_id,
                                'name': metadata['filename'],
                                'original_name': metadata['original_name'],
                                'size_mb': metadata['size_mb'],
                                'size_gb': metadata.get('size_gb', round(metadata['size_mb'] / 1024, 3)),
                                'upload_date': metadata['upload_date'],
                                'replicated_on': len(metadata['replicated_nodes']),
                                'nodes': metadata['replicated_nodes']
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
    """Format storage info for display with proper rounding"""
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
    
    # Ensure values are properly rounded
    used_gb = round(storage_info.get('used_gb', 0), 3)
    total_gb = storage_info.get('total_gb', 2.5)
    available_gb = round(total_gb - used_gb, 3)
    
    # Calculate percentage
    if total_gb > 0:
        percent_used = (used_gb / total_gb) * 100
    else:
        percent_used = 0
    
    return {
        'total_gb': total_gb,
        'used_gb': used_gb,
        'available_gb': available_gb,
        'percent_used': percent_used,
        'used_gb_display': f'{used_gb:.3f}',
        'available_gb_display': f'{available_gb:.3f}',
        'percent_used_display': round(percent_used, 1)
    }

# Protected routes
@app.route('/')
@login_required
@otp_required
def home():
    """User Dashboard"""
    try:
        # Get user-specific storage info
        storage_info = get_user_storage_info(session['user_id'])
        
        # Format storage display
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

# File operations (protected with OTP)
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
        
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({'error': f'File must be less than 500MB'}), 400
        
        result = storage.upload_file(file, file.filename, session['user_id'])
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': f'Upload route error: {str(e)}'}), 500

@app.route('/download/<file_id>')
@login_required
@otp_required
def download(file_id):
    """Download file"""
    try:
        result = storage.download_file(file_id)
        
        if 'error' in result:
            return jsonify(result), 404
        
        return send_file(result['path'],
                         as_attachment=True,
                         download_name=result['filename'])
    except Exception as e:
        return jsonify({'error': f'Download error: {str(e)}'}), 500

@app.route('/delete/<file_id>', methods=['POST'])
@login_required
@otp_required
def delete_file(file_id):
    """Delete file"""
    try:
        result = storage.delete_file(file_id, session['user_id'])
        
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': f'Delete error: {str(e)}'}), 500

# API routes
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

@app.route('/api/nodes')
@admin_required
def api_nodes():
    """Get nodes info (admin only)"""
    return jsonify({
        'nodes': node_manager.nodes,
        'stats': node_manager.get_node_stats()
    })

# Admin API routes
@app.route('/admin/api/start-node/<node_id>', methods=['POST'])
@admin_required
def admin_start_node(node_id):
    """Start a node"""
    if node_manager.start_node(node_id):
        return jsonify({'success': True, 'message': f'Node {node_id} started'})
    return jsonify({'error': 'Node not found'}), 404

@app.route('/admin/api/stop-node/<node_id>', methods=['POST'])
@admin_required
def admin_stop_node(node_id):
    """Stop a node"""
    if node_manager.stop_node(node_id):
        return jsonify({'success': True, 'message': f'Node {node_id} stopped'})
    return jsonify({'error': 'Node not found'}), 404

@app.route('/admin/api/delete-node/<node_id>', methods=['POST'])
@admin_required
def admin_delete_node(node_id):
    """Delete a node"""
    if node_manager.delete_node(node_id):
        return jsonify({'success': True, 'message': f'Node {node_id} deleted'})
    return jsonify({'error': 'Node not found'}), 404

@app.route('/admin/api/add-node', methods=['POST'])
@admin_required
def admin_add_node():
    """Add a new node"""
    data = request.json
    node = node_manager.add_node(data)
    return jsonify({'success': True, 'node': node})

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    print("=" * 60)
    print("🚀 AgriPredict Distributed Cloud Storage")
    print("🔐 Complete Authentication System with OTP via Email")
    print("=" * 60)
    print(f"📊 Default Admin: admin / password1234")
    print(f"🔐 Login: http://localhost:5000/login")
    print(f"📝 Register: http://localhost:5000/register")
    print(f"🌐 User Dashboard: http://localhost:5000")
    print(f"⚙️  Admin Dashboard: http://localhost:5000/admin")
    print("=" * 60)
    print("📧 OTP Codes are sent via email (or printed to console if not configured)")
    print("=" * 60)
    print("To configure email, create a .env file with:")
    print("SMTP_SERVER=smtp.gmail.com")
    print("SMTP_PORT=587")
    print("SENDER_EMAIL=your_email@gmail.com")
    print("SENDER_PASSWORD=your_app_password")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)