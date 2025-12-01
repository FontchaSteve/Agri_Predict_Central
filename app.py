"""
AgriPredict Central Application
Fixed version with start_web_server function
"""

import os
import json
import threading
from datetime import datetime
from flask import Flask, jsonify

# Global storage manager (will be imported)
storage_manager = None

# Store active nodes
active_nodes = {}

def set_storage_manager(manager):
    """Set the storage manager instance"""
    global storage_manager
    storage_manager = manager

def start_web_server(port, node_id, storage_path=None):
    """
    Start a web server for a node
    This function fixes the import error
    """
    print(f"Starting web server for {node_id} on port {port}")
    
    # Create a Flask app for this node
    node_app = Flask(node_id)
    
    # Store node information
    node_info = {
        'node_id': node_id,
        'port': port,
        'storage_path': storage_path,
        'start_time': datetime.now().isoformat(),
        'status': 'active'
    }
    active_nodes[node_id] = node_info
    
    @node_app.route('/')
    def home():
        return jsonify({
            'node': node_id,
            'status': 'active',
            'port': port,
            'api': 'ready'
        })
    
    @node_app.route('/status')
    def status():
        return jsonify({
            'node_id': node_id,
            'status': 'active',
            'timestamp': datetime.now().isoformat()
        })
    
    @node_app.route('/storage')
    def storage():
        if storage_path and os.path.exists(storage_path):
            if storage_manager:
                total, used, free = storage_manager.get_disk_usage(storage_path)
                return jsonify({
                    'node_id': node_id,
                    'path': storage_path,
                    'total_gb': round(total, 2),
                    'used_gb': round(used, 2),
                    'free_gb': round(free, 2)
                })
        return jsonify({'node_id': node_id, 'storage': 'not_available'})
    
    # Run server in background thread
    def run_server():
        node_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    return node_app

def get_active_nodes():
    """Get all active nodes"""
    return active_nodes

# Main Flask app for central dashboard
main_app = Flask(__name__)

@main_app.route('/')
def index():
    return jsonify({
        'app': 'AgriPredict Central',
        'nodes_active': len(active_nodes),
        'timestamp': datetime.now().isoformat()
    })

@main_app.route('/nodes')
def nodes():
    return jsonify(active_nodes)

if __name__ == '__main__':
    main_app.run(port=5000, debug=True)