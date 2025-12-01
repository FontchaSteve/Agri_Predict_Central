"""
Central Network Controller for Distributed Storage
"""
import socket
import threading
import time
import pickle
import json
import hashlib
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import psutil

from config import Config


@dataclass
class NodeInfo:
    """Node information with resource tracking"""
    node_id: str
    host: str
    port: int
    cpu_cores: int
    memory_gb: int
    storage_gb: int
    bandwidth_mbps: int
    used_storage: int = 0
    available_storage: int = 0
    active_transfers: int = 0
    last_heartbeat: float = 0.0
    status: str = "active"  # active, inactive, failed
    
    def __post_init__(self):
        self.available_storage = self.storage_gb * 1024**3
        self.used_storage = 0
        
    def update_storage(self, used_bytes: int):
        """Update storage usage"""
        self.used_storage += used_bytes
        self.available_storage = (self.storage_gb * 1024**3) - self.used_storage
    
    def get_storage_percent(self) -> float:
        """Get storage usage percentage"""
        total = self.storage_gb * 1024**3
        return (self.used_storage / total) * 100 if total > 0 else 0


@dataclass
class FileMetadata:
    """File metadata with replication tracking"""
    file_id: str
    filename: str
    original_filename: str
    size_bytes: int
    chunks: int
    owner: str  # User who uploaded
    upload_time: float
    replica_nodes: List[str]  # Nodes that have this file
    checksum: str  # MD5 checksum
    is_complete: bool = True
    
    def to_dict(self):
        """Convert to dictionary for serialization"""
        return {
            'file_id': self.file_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'size': self.size_bytes,
            'size_human': self._human_size(),
            'chunks': self.chunks,
            'owner': self.owner,
            'upload_time': self.upload_time,
            'upload_date': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.upload_time)),
            'replica_count': len(self.replica_nodes),
            'replica_nodes': self.replica_nodes,
            'checksum': self.checksum,
            'is_complete': self.is_complete
        }
    
    def _human_size(self):
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size_bytes < 1024.0:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024.0
        return f"{self.size_bytes:.1f} TB"


class NetworkController:
    """Central controller managing the distributed storage network"""
    
    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}
        self.files: Dict[str, FileMetadata] = {}
        self.file_locations: Dict[str, List[str]] = defaultdict(list)  # file_id -> [node_ids]
        self.running = False
        self.lock = threading.RLock()
        
        # Network socket
        self.socket = None
        self.host = Config.CONTROLLER_HOST
        self.port = Config.CONTROLLER_PORT
        
        # Statistics
        self.total_storage_capacity = 0
        self.total_used_storage = 0
        self.total_files = 0
        self.total_users = 0
        
        # Heartbeat thread
        self.heartbeat_thread = None
        
    def start(self):
        """Start the controller server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(20)
            self.socket.settimeout(1.0)
            
            self.running = True
            print(f"🌐 Network Controller started on {self.host}:{self.port}")
            
            # Start heartbeat monitor
            self.heartbeat_thread = threading.Thread(target=self._monitor_nodes, daemon=True)
            self.heartbeat_thread.start()
            
            # Start accepting connections
            self._accept_connections()
            
        except Exception as e:
            print(f"❌ Controller start failed: {e}")
            self.stop()
    
    def _accept_connections(self):
        """Accept incoming node connections"""
        while self.running:
            try:
                conn, addr = self.socket.accept()
                threading.Thread(target=self._handle_node_connection, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️ Connection error: {e}")
    
    def _handle_node_connection(self, conn, addr):
        """Handle communication with a storage node"""
        try:
            conn.settimeout(10)
            data = conn.recv(4096)
            if not data:
                return
            
            message = pickle.loads(data)
            response = self._process_node_message(message)
            conn.sendall(pickle.dumps(response))
            
        except Exception as e:
            print(f"⚠️ Node connection error: {e}")
        finally:
            conn.close()
    
    def _process_node_message(self, message: dict) -> dict:
        """Process messages from nodes"""
        action = message.get('action')
        
        with self.lock:
            if action == 'REGISTER':
                return self._register_node(message)
            elif action == 'HEARTBEAT':
                return self._handle_heartbeat(message)
            elif action == 'STORE_FILE':
                return self._store_file(message)
            elif action == 'RETRIEVE_FILE':
                return self._retrieve_file(message)
            elif action == 'DELETE_FILE':
                return self._delete_file(message)
            elif action == 'GET_STATS':
                return self._get_stats(message)
            elif action == 'LIST_FILES':
                return self._list_files(message)
            else:
                return {'status': 'error', 'message': f'Unknown action: {action}'}
    
    def _register_node(self, message: dict) -> dict:
        """Register a new storage node"""
        try:
            node_id = message['node_id']
            
            if node_id in self.nodes:
                return {'status': 'error', 'message': 'Node already registered'}
            
            # Create node info
            node = NodeInfo(
                node_id=node_id,
                host=message['host'],
                port=message['port'],
                cpu_cores=message['resources']['cpu_cores'],
                memory_gb=message['resources']['memory_gb'],
                storage_gb=message['resources']['storage_gb'],
                bandwidth_mbps=message['resources']['bandwidth_mbps'],
                last_heartbeat=time.time()
            )
            
            self.nodes[node_id] = node
            
            # Update total capacity
            self.total_storage_capacity += node.storage_gb * 1024**3
            
            print(f"✅ Node {node_id} registered successfully")
            self._print_network_status()
            
            return {
                'status': 'success',
                'message': 'Registration successful',
                'node_id': node_id,
                'total_nodes': len(self.nodes)
            }
            
        except Exception as e:
            return {'status': 'error', 'message': f'Registration failed: {e}'}
    
    def _handle_heartbeat(self, message: dict) -> dict:
        """Handle node heartbeat"""
        node_id = message['node_id']
        
        if node_id in self.nodes:
            self.nodes[node_id].last_heartbeat = time.time()
            self.nodes[node_id].status = 'active'
            
            # Update storage usage
            if 'used_storage' in message:
                self.nodes[node_id].used_storage = message['used_storage']
                self.nodes[node_id].available_storage = (
                    self.nodes[node_id].storage_gb * 1024**3 - message['used_storage']
                )
            
            return {'status': 'ack', 'timestamp': time.time()}
        else:
            return {'status': 'error', 'message': 'Node not registered'}
    
    def _store_file(self, message: dict) -> dict:
        """Coordinate file storage across nodes"""
        try:
            file_id = message['file_id']
            filename = message['filename']
            size_bytes = message['size']
            checksum = message['checksum']
            
            # Select nodes for storage (based on replication factor)
            selected_nodes = self._select_storage_nodes(size_bytes)
            
            if not selected_nodes:
                return {'status': 'error', 'message': 'Insufficient storage space'}
            
            # Create file metadata
            file_meta = FileMetadata(
                file_id=file_id,
                filename=filename,
                original_filename=message.get('original_name', filename),
                size_bytes=size_bytes,
                chunks=message.get('chunks', 1),
                owner=message.get('owner', 'anonymous'),
                upload_time=time.time(),
                replica_nodes=selected_nodes,
                checksum=checksum
            )
            
            # Store metadata
            self.files[file_id] = file_meta
            self.file_locations[file_id] = selected_nodes
            self.total_files += 1
            
            # Update node storage
            for node_id in selected_nodes:
                if node_id in self.nodes:
                    self.nodes[node_id].update_storage(size_bytes)
            
            # Update total used storage
            self.total_used_storage += size_bytes
            
            print(f"📁 File {filename} stored on nodes: {selected_nodes}")
            
            return {
                'status': 'success',
                'message': 'File storage coordinated',
                'nodes': selected_nodes,
                'file_id': file_id
            }
            
        except Exception as e:
            return {'status': 'error', 'message': f'Storage failed: {e}'}
    
    def _retrieve_file(self, message: dict) -> dict:
        """Coordinate file retrieval"""
        try:
            file_id = message['file_id']
            
            if file_id not in self.files:
                return {'status': 'error', 'message': 'File not found'}
            
            file_meta = self.files[file_id]
            available_nodes = [
                node_id for node_id in file_meta.replica_nodes 
                if node_id in self.nodes and self.nodes[node_id].status == 'active'
            ]
            
            if not available_nodes:
                return {'status': 'error', 'message': 'No available replicas'}
            
            # Select the least loaded node
            source_node = min(available_nodes, 
                            key=lambda n: self.nodes[n].active_transfers)
            
            # Increment transfer count
            self.nodes[source_node].active_transfers += 1
            
            return {
                'status': 'success',
                'source_node': source_node,
                'file_info': file_meta.to_dict(),
                'node_host': self.nodes[source_node].host,
                'node_port': self.nodes[source_node].port
            }
            
        except Exception as e:
            return {'status': 'error', 'message': f'Retrieval failed: {e}'}
        finally:
            # Decrement transfer count after a delay
            if 'source_node' in locals():
                threading.Timer(5, self._decrement_transfer, args=[source_node]).start()
    
    def _decrement_transfer(self, node_id: str):
        """Decrement active transfer count"""
        with self.lock:
            if node_id in self.nodes:
                self.nodes[node_id].active_transfers = max(
                    0, self.nodes[node_id].active_transfers - 1
                )
    
    def _delete_file(self, message: dict) -> dict:
        """Coordinate file deletion"""
        try:
            file_id = message['file_id']
            
            if file_id not in self.files:
                return {'status': 'error', 'message': 'File not found'}
            
            file_meta = self.files[file_id]
            
            # Remove from storage tracking
            for node_id in file_meta.replica_nodes:
                if node_id in self.nodes:
                    self.nodes[node_id].update_storage(-file_meta.size_bytes)
            
            # Remove metadata
            del self.files[file_id]
            del self.file_locations[file_id]
            self.total_files -= 1
            self.total_used_storage -= file_meta.size_bytes
            
            return {'status': 'success', 'message': 'File deleted'}
            
        except Exception as e:
            return {'status': 'error', 'message': f'Deletion failed: {e}'}
    
    def _get_stats(self, message: dict) -> dict:
        """Get system statistics"""
        with self.lock:
            active_nodes = [n for n in self.nodes.values() if n.status == 'active']
            
            stats = {
                'status': 'success',
                'total_nodes': len(self.nodes),
                'active_nodes': len(active_nodes),
                'total_files': self.total_files,
                'total_capacity': self.total_storage_capacity,
                'total_used': self.total_used_storage,
                'total_available': self.total_storage_capacity - self.total_used_storage,
                'replication_factor': Config.REPLICATION_FACTOR,
                'nodes': {
                    node_id: {
                        'status': node.status,
                        'storage_used': node.used_storage,
                        'storage_available': node.available_storage,
                        'storage_total': node.storage_gb * 1024**3,
                        'storage_percent': node.get_storage_percent(),
                        'active_transfers': node.active_transfers,
                        'last_seen': node.last_heartbeat
                    }
                    for node_id, node in self.nodes.items()
                },
                'files': {
                    file_id: meta.to_dict()
                    for file_id, meta in self.files.items()
                }
            }
            
            return stats
    
    def _list_files(self, message: dict) -> dict:
        """List all files in the system"""
        with self.lock:
            return {
                'status': 'success',
                'files': [
                    meta.to_dict()
                    for meta in self.files.values()
                ],
                'count': len(self.files)
            }
    
    def _select_storage_nodes(self, file_size: int) -> List[str]:
        """Select nodes for file storage based on available space and load"""
        with self.lock:
            # Filter active nodes with enough space
            candidate_nodes = [
                (node_id, node) 
                for node_id, node in self.nodes.items()
                if node.status == 'active' and node.available_storage >= file_size
            ]
            
            if not candidate_nodes:
                return []
            
            # Sort by available space (descending) and load (ascending)
            candidate_nodes.sort(
                key=lambda x: (
                    x[1].available_storage,  # More space first
                    -x[1].active_transfers    # Fewer transfers first
                ),
                reverse=True
            )
            
            # Select up to replication factor nodes
            selected = [node_id for node_id, _ in candidate_nodes[:Config.REPLICATION_FACTOR]]
            
            return selected
    
    def _monitor_nodes(self):
        """Monitor node health and handle failures"""
        while self.running:
            try:
                current_time = time.time()
                failed_nodes = []
                
                with self.lock:
                    for node_id, node in self.nodes.items():
                        if current_time - node.last_heartbeat > 30:  # 30 second timeout
                            if node.status == 'active':
                                node.status = 'failed'
                                failed_nodes.append(node_id)
                                print(f"⚠️ Node {node_id} failed")
                    
                    # Handle node failures - re-replicate files
                    for node_id in failed_nodes:
                        self._handle_node_failure(node_id)
                
                if failed_nodes:
                    self._print_network_status()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"⚠️ Node monitor error: {e}")
    
    def _handle_node_failure(self, node_id: str):
        """Handle node failure by re-replicating files"""
        print(f"🔄 Replicating files from failed node {node_id}")
        
        # Find files that need re-replication
        files_to_replicate = []
        for file_id, file_meta in self.files.items():
            if node_id in file_meta.replica_nodes:
                # Check if we still have enough replicas
                active_replicas = [
                    n for n in file_meta.replica_nodes
                    if n in self.nodes and self.nodes[n].status == 'active'
                ]
                
                if len(active_replicas) < Config.REPLICATION_FACTOR:
                    files_to_replicate.append((file_id, file_meta, active_replicas))
        
        # Re-replicate files
        for file_id, file_meta, current_replicas in files_to_replicate:
            needed = Config.REPLICATION_FACTOR - len(current_replicas)
            if needed > 0:
                # Select new nodes for replication
                new_nodes = self._select_storage_nodes(file_meta.size_bytes)
                new_nodes = [n for n in new_nodes if n not in current_replicas][:needed]
                
                if new_nodes:
                    file_meta.replica_nodes.extend(new_nodes)
                    self.file_locations[file_id].extend(new_nodes)
                    
                    # Update node storage
                    for new_node in new_nodes:
                        if new_node in self.nodes:
                            self.nodes[new_node].update_storage(file_meta.size_bytes)
                    
                    print(f"  ↪️ Re-replicated {file_meta.filename} to {new_nodes}")
    
    def _print_network_status(self):
        """Print current network status"""
        with self.lock:
            active_nodes = sum(1 for n in self.nodes.values() if n.status == 'active')
            total_capacity_gb = self.total_storage_capacity / 1024**3
            used_gb = self.total_used_storage / 1024**3
            available_gb = total_capacity_gb - used_gb
            
            print(f"\n{'='*60}")
            print(f"🌐 NETWORK STATUS")
            print(f"{'='*60}")
            print(f"Nodes: {active_nodes}/{len(self.nodes)} active")
            print(f"Files: {self.total_files}")
            print(f"Storage: {used_gb:.1f}/{total_capacity_gb:.1f} GB used ({used_gb/total_capacity_gb*100:.1f}%)")
            print(f"Available: {available_gb:.1f} GB")
            print(f"{'='*60}")
    
    def stop(self):
        """Stop the controller"""
        self.running = False
        if self.socket:
            self.socket.close()
        print("🛑 Controller stopped")


if __name__ == "__main__":
    controller = NetworkController()
    try:
        controller.start()
    except KeyboardInterrupt:
        controller.stop()