"""
AgriPredict Cloud Storage - Fixed Version
"""
from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename
import traceback

# Get the absolute path to the templates folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__, template_folder=TEMPLATES_DIR)
app.secret_key = 'agripredict-cloud-2024'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file

# Storage settings
TOTAL_STORAGE_MB = 2500  # 2.5GB total (5 nodes × 500MB)
NODES = 5  # Hidden from user
STORAGE_PER_NODE_MB = 500
BLOCK_SIZE = 1024 * 1024  # 1MB blocks

print(f"📁 Base directory: {BASE_DIR}")
print(f"📁 Templates directory: {TEMPLATES_DIR}")

# Check if templates folder exists
if not os.path.exists(TEMPLATES_DIR):
    print(f"❌ ERROR: Templates folder not found at {TEMPLATES_DIR}")
    print("Creating templates folder...")
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Create directories
os.makedirs('temp', exist_ok=True)
os.makedirs('file_info', exist_ok=True)

class CloudStorage:
    def __init__(self):
        self.storage_path = os.path.join(os.path.expanduser("~"), "AgriPredict_Cloud")
        self.node_paths = []
        
        # Create storage
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
            print(f"🌐 Cloud Storage created at: {self.storage_path}")
        
        # Create 5 hidden nodes
        for i in range(1, NODES + 1):
            node_path = os.path.join(self.storage_path, f"node{i}")
            os.makedirs(node_path, exist_ok=True)
            self.node_paths.append(node_path)
        
        print(f"✅ {NODES} storage nodes ready (500MB each)")
    
    def save_file(self, file_path, filename):
        """Split file and save across nodes"""
        file_id = hashlib.md5(f"{filename}{datetime.now()}".encode()).hexdigest()[:12]
        file_size = os.path.getsize(file_path)
        
        # Check storage space
        storage_info = self.get_storage_info()
        if storage_info['available_mb'] < (file_size / (1024*1024)):
            return {'error': 'Not enough storage space'}
        
        # Split file into blocks
        blocks = []
        block_num = 0
        
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(BLOCK_SIZE)
                if not data:
                    break
                
                # Save block to a node (round-robin)
                node_idx = block_num % NODES
                block_name = f"{file_id}_block{block_num}"
                block_path = os.path.join(self.node_paths[node_idx], block_name)
                
                with open(block_path, 'wb') as block_file:
                    block_file.write(data)
                
                blocks.append({
                    'path': block_path,
                    'node': node_idx,
                    'size': len(data)
                })
                block_num += 1
        
        # Save file information
        file_data = {
            'id': file_id,
            'name': filename,
            'original_name': filename,
            'size_mb': round(file_size / (1024*1024), 2),
            'blocks': len(blocks),
            'upload_date': datetime.now().isoformat(),
            'block_info': blocks
        }
        
        with open(os.path.join('file_info', f"{file_id}.json"), 'w') as f:
            json.dump(file_data, f, indent=2)
        
        return {
            'success': True,
            'id': file_id,
            'name': filename,
            'size_mb': file_data['size_mb']
        }
    
    def get_file(self, file_id):
        """Reassemble file from blocks"""
        info_path = os.path.join('file_info', f"{file_id}.json")
        
        if not os.path.exists(info_path):
            return {'error': 'File not found'}
        
        with open(info_path, 'r') as f:
            file_data = json.load(f)
        
        # Reassemble file
        temp_path = os.path.join('temp', f"download_{file_id}")
        
        with open(temp_path, 'wb') as out_file:
            for block in file_data['block_info']:
                if os.path.exists(block['path']):
                    with open(block['path'], 'rb') as block_file:
                        out_file.write(block_file.read())
        
        return {
            'success': True,
            'path': temp_path,
            'name': file_data['name'],
            'original_name': file_data['original_name']
        }
    
    def delete_file(self, file_id):
        """Delete file and all its blocks"""
        info_path = os.path.join('file_info', f"{file_id}.json")
        
        if not os.path.exists(info_path):
            return {'error': 'File not found'}
        
        with open(info_path, 'r') as f:
            file_data = json.load(f)
        
        # Delete all blocks
        deleted = 0
        for block in file_data['block_info']:
            if os.path.exists(block['path']):
                os.remove(block['path'])
                deleted += 1
        
        # Delete file info
        os.remove(info_path)
        
        return {
            'success': True,
            'deleted_blocks': deleted,
            'name': file_data['name'],
            'size_mb': file_data['size_mb']
        }
    
    def get_storage_info(self):
        """Get total storage information"""
        total_used = 0
        
        for node_path in self.node_paths:
            if os.path.exists(node_path):
                for item in os.listdir(node_path):
                    item_path = os.path.join(node_path, item)
                    if os.path.isfile(item_path):
                        total_used += os.path.getsize(item_path)
        
        used_mb = total_used / (1024*1024)
        
        return {
            'total_mb': TOTAL_STORAGE_MB,
            'used_mb': round(used_mb, 2),
            'available_mb': round(TOTAL_STORAGE_MB - used_mb, 2),
            'percent_used': round((used_mb / TOTAL_STORAGE_MB) * 100, 1),
            'files': len(os.listdir('file_info')) if os.path.exists('file_info') else 0
        }
    
    def get_all_files(self):
        """Get list of all user files"""
        files = []
        
        if os.path.exists('file_info'):
            for filename in os.listdir('file_info'):
                if filename.endswith('.json'):
                    file_id = filename.replace('.json', '')
                    with open(os.path.join('file_info', filename), 'r') as f:
                        file_data = json.load(f)
                    
                    files.append({
                        'id': file_data['id'],
                        'name': file_data['name'],
                        'original_name': file_data['original_name'],
                        'size_mb': file_data['size_mb'],
                        'upload_date': file_data['upload_date']
                    })
        
        return files

# Create storage system
storage = CloudStorage()

@app.route('/')
def home():
    """Main page - User sees ONE storage space"""
    try:
        storage_info = storage.get_storage_info()
        files = storage.get_all_files()
        
        return render_template('dashboard.html', 
                             storage=storage_info,
                             files=files,
                             total_files=len(files))
    except Exception as e:
        print(f"❌ Error loading template: {e}")
        traceback.print_exc()
        return f"""
        <h1>AgriPredict Cloud Storage</h1>
        <p>Template error: {e}</p>
        <p>Templates folder: {TEMPLATES_DIR}</p>
        <p>Exists: {os.path.exists(TEMPLATES_DIR)}</p>
        """

@app.route('/upload', methods=['POST'])
def upload():
    """Upload a file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save temporary file
    filename = secure_filename(file.filename)
    temp_path = os.path.join('temp', f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}")
    file.save(temp_path)
    
    # Save to distributed storage
    result = storage.save_file(temp_path, filename)
    
    # Clean temp file
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result), 200

@app.route('/download/<file_id>')
def download(file_id):
    """Download a file"""
    result = storage.get_file(file_id)
    
    if 'error' in result:
        return jsonify(result), 404
    
    try:
        # Send the file
        response = send_file(
            result['path'],
            as_attachment=True,
            download_name=result['original_name']
        )
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete/<file_id>', methods=['POST'])
def delete_file(file_id):
    """Delete a file"""
    result = storage.delete_file(file_id)
    
    if 'error' in result:
        return jsonify(result), 404
    
    return jsonify(result), 200

@app.route('/api/storage')
def api_storage():
    """Get storage info API"""
    return jsonify(storage.get_storage_info())

@app.route('/api/files')
def api_files():
    """Get files list API"""
    return jsonify({'files': storage.get_all_files()})

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 AgriPredict Cloud Storage System")
    print("=" * 60)
    print(f"📊 Total User Storage: {TOTAL_STORAGE_MB / 1024:.1f}GB")
    print(f"📁 Storage Location: {storage.storage_path}")
    print(f"🌐 Web Interface: http://localhost:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)