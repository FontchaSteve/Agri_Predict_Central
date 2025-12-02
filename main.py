"""
AgriPredict Cloud Storage - Admin + User Dashboard
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
import json
import hashlib
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
import random

app = Flask(__name__, template_folder='templates')
app.secret_key = 'agripredict-2024-secret'
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
        # NOTE: This does not clean up the physical storage folder on disk.
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
            'storage_total_mb': node_data.get('storage_total_mb', STORAGE_PER_NODE_MB), # Use provided storage if available
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
        
        # Calculate storage usage
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
        
        # Ensure the base path exists
        os.makedirs(self.base_path, exist_ok=True)
        
        # 🌟 FIX: Ensure all node-specific directories exist 🌟
        # This will run every time the app starts and is robust 
        # against running the app multiple times or adding new nodes.
        for node in node_manager.nodes:
            node_path = os.path.join(self.base_path, node['id'])
            os.makedirs(node_path, exist_ok=True)
    
    def upload_file(self, file_stream, filename):
        """Upload file with replication across nodes"""
        try:
            active_nodes = self.node_manager.get_active_nodes()
            if len(active_nodes) < REPLICATION_FACTOR:
                return {'error': f'Need at least {REPLICATION_FACTOR} active nodes for replication'}
            
            # Save file temporarily
            # IMPORTANT: The file_stream passed to upload_file is a FileStorage object.
            # Calling .save() on it saves the uploaded file to the specified path.
            temp_path = os.path.join('temp', f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(filename)}")
            file_stream.save(temp_path)
            
            file_id = hashlib.md5(f"{filename}{datetime.now()}".encode()).hexdigest()[:12]
            file_size = os.path.getsize(temp_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Check if enough storage space available
            node_stats = self.node_manager.get_node_stats()
            # We need enough available space for REPLICATION_FACTOR copies
            required_space_gb = (file_size_mb / 1024) * REPLICATION_FACTOR
            available_gb = node_stats['storage_total_gb'] - node_stats['storage_used_gb']
            
            if available_gb < required_space_gb:
                os.remove(temp_path)
                return {'error': f'Not enough total storage space (Required: {round(required_space_gb, 2)}GB)'}
            
            # Select nodes for replication (choose random active nodes)
            selected_nodes = random.sample(active_nodes, min(REPLICATION_FACTOR, len(active_nodes)))
            
            # Final check per node availability (storage_total_mb - storage_used_mb)
            can_store = True
            for node in selected_nodes:
                if node['storage_total_mb'] - node['storage_used_mb'] < file_size_mb:
                    can_store = False
                    break

            if not can_store:
                os.remove(temp_path)
                return {'error': 'Not enough space on selected replication nodes.'}
            
            # Create metadata
            metadata = {
                'file_id': file_id,
                'filename': secure_filename(filename),
                'original_name': filename,
                'size_mb': round(file_size_mb, 2),
                'upload_date': datetime.now().isoformat(),
                'replicated_nodes': [node['id'] for node in selected_nodes],
                'size_bytes': file_size
            }
            
            # Save file to selected nodes
            for node in selected_nodes:
                node_path = os.path.join(self.base_path, node['id'])
                dest_path = os.path.join(node_path, f"{file_id}_{secure_filename(filename)}")
                
                # Copy file to node
                shutil.copy2(temp_path, dest_path)
                
                # Update node usage
                node['storage_used_mb'] += file_size_mb
                node['files'] += 1
            
            # Save metadata
            metadata_path = os.path.join('metadata', f"{file_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Save updated nodes
            self.node_manager.save_nodes(self.node_manager.nodes)
            
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return {
                'success': True,
                'file_id': file_id,
                'filename': filename,
                'size_mb': round(file_size_mb, 2),
                'replicated_on': len(selected_nodes),
                'nodes': [node['id'] for node in selected_nodes]
            }
        except Exception as e:
            # Clean up temp file if it exists and the upload failed midway
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
            
            # Try to get file from any replicated node
            for node_id in metadata['replicated_nodes']:
                node_path = os.path.join(self.base_path, node_id)
                file_path = os.path.join(node_path, f"{file_id}_{metadata['filename']}")
                
                if os.path.exists(file_path):
                    return {
                        'success': True,
                        'path': file_path,
                        'filename': metadata['original_name'],
                        'from_node': node_id
                    }
            
            return {'error': 'File not found on any node'}
        except Exception as e:
            return {'error': f'Download failed: {str(e)}'}
    
    def delete_file(self, file_id):
        """Delete file from all nodes"""
        try:
            metadata_path = os.path.join('metadata', f"{file_id}.json")
            
            if not os.path.exists(metadata_path):
                return {'error': 'File not found'}
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Delete from all nodes
            deleted_count = 0
            for node_id in metadata['replicated_nodes']:
                node_path = os.path.join(self.base_path, node_id)
                file_path = os.path.join(node_path, f"{file_id}_{metadata['filename']}")
                
                if os.path.exists(file_path):
                    # Update node storage usage
                    for node in self.node_manager.nodes:
                        if node['id'] == node_id:
                            node['storage_used_mb'] = max(0, node['storage_used_mb'] - metadata['size_mb'])
                            node['files'] = max(0, node['files'] - 1)
                            break
                    
                    os.remove(file_path)
                    deleted_count += 1
            
            # Delete metadata
            os.remove(metadata_path)
            
            # Save updated nodes
            self.node_manager.save_nodes(self.node_manager.nodes)
            
            return {
                'success': True,
                'deleted_from': deleted_count,
                'filename': metadata['original_name']
            }
        except Exception as e:
            return {'error': f'Delete failed: {str(e)}'}
    
    def get_storage_info(self):
        """Get storage information for user view"""
        try:
            node_stats = self.node_manager.get_node_stats()
            
            return {
                'total_gb': node_stats['storage_total_gb'],
                'used_gb': node_stats['storage_used_gb'],
                'available_gb': round(node_stats['storage_total_gb'] - node_stats['storage_used_gb'], 2),
                'percent_used': node_stats['storage_percent'],
                'files': node_stats['total_files']
            }
        except Exception as e:
            return {'error': f'Storage info failed: {str(e)}'}
    
    def get_all_files(self):
        """Get all files"""
        try:
            files = []
            
            if os.path.exists('metadata'):
                for filename in os.listdir('metadata'):
                    if filename.endswith('.json'):
                        file_id = filename.replace('.json', '')
                        with open(os.path.join('metadata', filename), 'r') as f:
                            metadata = json.load(f)
                        
                        files.append({
                            'id': file_id,
                            'name': metadata['filename'],
                            'original_name': metadata['original_name'],
                            'size_mb': metadata['size_mb'],
                            'upload_date': metadata['upload_date'],
                            'replicated_on': len(metadata['replicated_nodes']),
                            'nodes': metadata['replicated_nodes']
                        })
            
            return files
        except Exception as e:
            print(f"Error loading files: {e}")
            return []

# Initialize managers
node_manager = NodeManager()
storage = DistributedStorage(node_manager)

# Routes
@app.route('/')
def home():
    """User Dashboard"""
    try:
        storage_info = storage.get_storage_info()
        files = storage.get_all_files()
        
        return render_template('user_dashboard.html',
                              storage=storage_info,
                              files=files,
                              total_files=len(files))
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/admin')
def admin_dashboard():
    """Admin Dashboard"""
    try:
        nodes = node_manager.nodes
        stats = node_manager.get_node_stats()
        
        return render_template('admin_dashboard.html',
                              nodes=nodes,
                              stats=stats)
    except Exception as e:
        return f"Error loading admin dashboard: {str(e)}", 500

@app.route('/admin/api/start-node/<node_id>', methods=['POST'])
def admin_start_node(node_id):
    """Start a node"""
    if node_manager.start_node(node_id):
        return jsonify({'success': True, 'message': f'Node {node_id} started'})
    return jsonify({'error': 'Node not found'}), 404

@app.route('/admin/api/stop-node/<node_id>', methods=['POST'])
def admin_stop_node(node_id):
    """Stop a node"""
    if node_manager.stop_node(node_id):
        return jsonify({'success': True, 'message': f'Node {node_id} stopped'})
    return jsonify({'error': 'Node not found'}), 404

@app.route('/admin/api/delete-node/<node_id>', methods=['POST'])
def admin_delete_node(node_id):
    """Delete a node"""
    if node_manager.delete_node(node_id):
        return jsonify({'success': True, 'message': f'Node {node_id} deleted'})
    return jsonify({'error': 'Node not found'}), 404

@app.route('/admin/api/add-node', methods=['POST'])
def admin_add_node():
    """Add a new node"""
    try:
        data = request.json
        node = node_manager.add_node(data)
        # Ensure the physical directory for the new node is created immediately
        node_path = os.path.join(storage.base_path, node['id'])
        os.makedirs(node_path, exist_ok=True)
        return jsonify({'success': True, 'node': node})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/upload', methods=['POST'])
def upload():
    """Upload file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file size (500MB max)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()  # Get file size
        file.seek(0)  # Reset file pointer
        
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({'error': f'File must be less than {app.config["MAX_CONTENT_LENGTH"] / (1024*1024)}MB'}), 400
        
        # Upload to distributed storage
        result = storage.upload_file(file, file.filename)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': f'Upload route error: {str(e)}'}), 500

@app.route('/download/<file_id>')
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
def delete_file(file_id):
    """Delete file"""
    try:
        result = storage.delete_file(file_id)
        
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': f'Delete error: {str(e)}'}), 500

@app.route('/api/storage')
def api_storage():
    """Get storage info"""
    return jsonify(storage.get_storage_info())

@app.route('/api/files')
def api_files():
    """Get files list"""
    return jsonify({'files': storage.get_all_files()})

@app.route('/api/nodes')
def api_nodes():
    """Get nodes info"""
    return jsonify({
        'nodes': node_manager.nodes,
        'stats': node_manager.get_node_stats()
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 AgriPredict Distributed Cloud Storage")
    print("=" * 60)
    print(f"📊 User Storage: {TOTAL_STORAGE_GB}GB")
    print(f"🔧 Replication Factor: {REPLICATION_FACTOR}")
    print(f"🌐 User Dashboard: http://localhost:5000")
    print(f"⚙️  Admin Dashboard: http://localhost:5000/admin")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)