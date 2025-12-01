"""
Storage Node Implementation
"""
import socket
import threading
import time
import pickle
import os
import hashlib
import json
import shutil
from typing import Dict, List, Optional
import psutil

from config import Config


class StorageNode:
    """Storage node that provides storage space and handles files"""
    
    def __init__(self, node_id: str, host: str = "localhost", port: int = None):
        self.node_id = node_id
        self.host = host
        self.port = port or self._find_available_port()
        
        # Resources
        self.cpu_cores = Config.NODE_CPU_CORES
        self.memory_gb = Config.NODE_MEMORY_GB
        self.storage_gb = Config.NODE_STORAGE_GB
        self.bandwidth_mbps = Config.NODE_BANDWIDTH_MBPS
        
        # Storage
        self.storage_dir = os.path.join(Config.NODE_STORAGE_DIR, f"node_{node_id}")
        os.makedirs(self.storage_dir, exist_ok=True)
        
        self.used_storage = 0
        self.files: Dict[str, dict] = {}  # file_id -> file_info
        self.active_transfers = 0
        
        # Controller connection
        self.controller_host = Config.CONTROLLER_HOST
        self.controller_port = Config.CONTROLLER_PORT
        
        # Status
        self.running = False
        self.heartbeat_thread = None
        self.server_thread = None
        self.server_socket = None
        
        # Initialize storage usage
        self._calculate_storage_usage()
    
    def _find_available_port(self) -> int:
        """Find an available port for the node"""
        for port in range(*Config.NODE_PORT_RANGE):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(('localhost', port))
                sock.close()
                return port
            except:
                continue
        raise Exception("No available ports found")
    
    def _calculate_storage_usage(self):
        """Calculate current storage usage"""
        total_size = 0
        for root, dirs, files in os.walk(self.storage_dir):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        
        self.used_storage = total_size
    
    def start(self):
        """Start the storage node"""
        try:
            # Start server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            
            self.running = True
            
            # Register with controller
            if not self._register_with_controller():
                print(f"❌ Node {self.node_id} failed to register")
                return False
            
            # Start heartbeat
            self.heartbeat_thread = threading.Thread(target=self._send_heartbeats, daemon=True)
            self.heartbeat_thread.start()
            
            # Start server
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            print(f"✅ Node {self.node_id} started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            print(f"❌ Node {self.node_id} start failed: {e}")
            return False
    
    def _register_with_controller(self) -> bool:
        """Register this node with the controller"""
        try:
            message = {
                'action': 'REGISTER',
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port,
                'resources': {
                    'cpu_cores': self.cpu_cores,
                    'memory_gb': self.memory_gb,
                    'storage_gb': self.storage_gb,
                    'bandwidth_mbps': self.bandwidth_mbps
                }
            }
            
            response = self._send_to_controller(message)
            return response and response.get('status') == 'success'
            
        except Exception as e:
            print(f"❌ Registration failed: {e}")
            return False
    
    def _send_to_controller(self, message: dict) -> Optional[dict]:
        """Send message to controller"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((self.controller_host, self.controller_port))
                sock.sendall(pickle.dumps(message))
                
                response_data = sock.recv(4096)
                return pickle.loads(response_data)
                
        except Exception as e:
            print(f"⚠️ Controller communication failed: {e}")
            return None
    
    def _send_heartbeats(self):
        """Send periodic heartbeats to controller"""
        while self.running:
            try:
                message = {
                    'action': 'HEARTBEAT',
                    'node_id': self.node_id,
                    'used_storage': self.used_storage
                }
                
                self._send_to_controller(message)
                
            except Exception as e:
                print(f"⚠️ Heartbeat failed: {e}")
            
            time.sleep(5)  # Send heartbeat every 5 seconds
    
    def _run_server(self):
        """Run the node server to handle file operations"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"⚠️ Server error: {e}")
    
    def _handle_client(self, conn, addr):
        """Handle client connection"""
        try:
            conn.settimeout(30)
            data = conn.recv(1024)  # Receive initial command
            
            if not data:
                return
            
            command = data.decode().strip().upper()
            
            if command == 'STORE':
                self._handle_store(conn)
            elif command == 'RETRIEVE':
                self._handle_retrieve(conn)
            elif command == 'DELETE':
                self._handle_delete(conn)
            elif command == 'STATUS':
                self._handle_status(conn)
            else:
                conn.sendall(b'ERROR: Unknown command')
                
        except Exception as e:
            print(f"⚠️ Client handler error: {e}")
        finally:
            conn.close()
    
    def _handle_store(self, conn):
        """Handle file storage request"""
        try:
            # Receive file metadata
            metadata_data = b''
            while True:
                chunk = conn.recv(1024)
                if b'<END_META>' in chunk:
                    metadata_data += chunk.split(b'<END_META>')[0]
                    break
                metadata_data += chunk
            
            metadata = json.loads(metadata_data.decode())
            file_id = metadata['file_id']
            filename = metadata['filename']
            size = metadata['size']
            
            # Check available space
            available = (self.storage_gb * 1024**3) - self.used_storage
            if available < size:
                conn.sendall(b'ERROR: Insufficient storage')
                return
            
            # Send ready signal
            conn.sendall(b'READY')
            
            # Receive file data
            file_path = os.path.join(self.storage_dir, file_id)
            received = 0
            
            with open(file_path, 'wb') as f:
                while received < size:
                    chunk = conn.recv(min(8192, size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            if received == size:
                # Calculate checksum
                checksum = self._calculate_checksum(file_path)
                
                # Store file info
                self.files[file_id] = {
                    'filename': filename,
                    'original_name': metadata.get('original_name', filename),
                    'size': size,
                    'checksum': checksum,
                    'stored_at': time.time(),
                    'path': file_path
                }
                
                # Update storage usage
                self.used_storage += size
                
                conn.sendall(f'SUCCESS:{checksum}'.encode())
                print(f"📁 Stored {filename} ({size} bytes)")
            else:
                conn.sendall(b'ERROR: Incomplete transfer')
                os.remove(file_path)
                
        except Exception as e:
            conn.sendall(f'ERROR: {str(e)}'.encode())
    
    def _handle_retrieve(self, conn):
        """Handle file retrieval request"""
        try:
            # Receive file ID
            file_id = conn.recv(1024).decode().strip()
            
            if file_id not in self.files:
                conn.sendall(b'ERROR: File not found')
                return
            
            file_info = self.files[file_id]
            file_path = file_info['path']
            
            # Send file metadata
            metadata = {
                'filename': file_info['filename'],
                'original_name': file_info['original_name'],
                'size': file_info['size'],
                'checksum': file_info['checksum']
            }
            
            conn.sendall(json.dumps(metadata).encode() + b'<END_META>')
            
            # Wait for ready signal
            ready = conn.recv(1024)
            if ready != b'READY':
                return
            
            # Send file data
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    conn.sendall(chunk)
            
            print(f"📤 Retrieved {file_info['filename']}")
            
        except Exception as e:
            conn.sendall(f'ERROR: {str(e)}'.encode())
    
    def _handle_delete(self, conn):
        """Handle file deletion request"""
        try:
            file_id = conn.recv(1024).decode().strip()
            
            if file_id not in self.files:
                conn.sendall(b'ERROR: File not found')
                return
            
            file_info = self.files[file_id]
            file_path = file_info['path']
            
            # Delete file
            os.remove(file_path)
            
            # Update storage
            self.used_storage -= file_info['size']
            del self.files[file_id]
            
            conn.sendall(b'SUCCESS')
            print(f"🗑️ Deleted {file_info['filename']}")
            
        except Exception as e:
            conn.sendall(f'ERROR: {str(e)}'.encode())
    
    def _handle_status(self, conn):
        """Handle status request"""
        try:
            status = {
                'node_id': self.node_id,
                'status': 'running',
                'storage_used': self.used_storage,
                'storage_total': self.storage_gb * 1024**3,
                'files_count': len(self.files),
                'active_transfers': self.active_transfers
            }
            
            conn.sendall(json.dumps(status).encode())
            
        except Exception as e:
            conn.sendall(f'ERROR: {str(e)}'.encode())
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of a file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def store_file(self, file_path: str, file_id: str, metadata: dict) -> bool:
        """Store a file (called by controller)"""
        try:
            if not os.path.exists(file_path):
                return False
            
            file_size = os.path.getsize(file_path)
            
            # Check space
            available = (self.storage_gb * 1024**3) - self.used_storage
            if available < file_size:
                return False
            
            # Copy file
            dest_path = os.path.join(self.storage_dir, file_id)
            shutil.copy2(file_path, dest_path)
            
            # Calculate checksum
            checksum = self._calculate_checksum(dest_path)
            
            # Store metadata
            self.files[file_id] = {
                'filename': metadata.get('filename', os.path.basename(file_path)),
                'original_name': metadata.get('original_name', os.path.basename(file_path)),
                'size': file_size,
                'checksum': checksum,
                'stored_at': time.time(),
                'path': dest_path
            }
            
            # Update storage
            self.used_storage += file_size
            
            return True
            
        except Exception as e:
            print(f"❌ Store file failed: {e}")
            return False
    
    def retrieve_file(self, file_id: str, dest_path: str) -> bool:
        """Retrieve a file to destination path"""
        try:
            if file_id not in self.files:
                return False
            
            file_info = self.files[file_id]
            shutil.copy2(file_info['path'], dest_path)
            return True
            
        except Exception as e:
            print(f"❌ Retrieve file failed: {e}")
            return False
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file from this node"""
        try:
            if file_id not in self.files:
                return False
            
            file_info = self.files[file_id]
            os.remove(file_info['path'])
            
            self.used_storage -= file_info['size']
            del self.files[file_id]
            
            return True
            
        except Exception as e:
            print(f"❌ Delete file failed: {e}")
            return False
    
    def stop(self):
        """Stop the node"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print(f"🛑 Node {self.node_id} stopped")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python storage_node.py <node_id> [port]")
        sys.exit(1)
    
    node_id = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    node = StorageNode(node_id, port=port)
    
    try:
        if node.start():
            print(f"Node {node_id} running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        node.stop()