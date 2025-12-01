import os
import json
import shutil
import threading
from datetime import datetime

class StorageManager:
    def __init__(self, base_path=None):
        # Use your computer's disk space
        if base_path is None:
            # Default to a directory in your user folder
            user_home = os.path.expanduser("~")
            base_path = os.path.join(user_home, "AgriPredict_Storage")
        
        self.base_path = base_path
        self.STORAGE_PER_NODE = 10  # 10GB per node - you can change this
        self.node_paths = {}
        self.lock = threading.Lock()
        self.ensure_base_path()
        print(f"📦 Storage Manager initialized at: {self.base_path}")
        
    def ensure_base_path(self):
        """Create the base directory if it doesn't exist"""
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
            print(f"✅ Created base storage directory: {self.base_path}")
            
            # Create a README file
            with open(os.path.join(self.base_path, "README.txt"), "w") as f:
                f.write(f"AgriPredict Node Storage\n")
                f.write(f"Created: {datetime.now()}\n")
                f.write(f"Storage per node: {self.STORAGE_PER_NODE} GB\n")
                f.write(f"Path: {self.base_path}\n")
    
    def allocate_storage_for_node(self, node_id):
        """Allocate storage space for a specific node"""
        with self.lock:
            node_path = os.path.join(self.base_path, f"node_{node_id}")
            
            if not os.path.exists(node_path):
                os.makedirs(node_path)
                
                # Create subdirectories
                subdirs = ['data', 'models', 'logs', 'cache', 'backup']
                for subdir in subdirs:
                    os.makedirs(os.path.join(node_path, subdir), exist_ok=True)
                
                print(f"✅ Created storage for {node_id}: {node_path}")
            
            # Create/Update storage info file
            storage_info = {
                'node_id': node_id,
                'path': node_path,
                'allocated_gb': self.STORAGE_PER_NODE,
                'used_gb': 0,
                'available_gb': self.STORAGE_PER_NODE,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'subdirectories': ['data', 'models', 'logs', 'cache', 'backup'],
                'max_size_gb': self.STORAGE_PER_NODE
            }
            
            info_file = os.path.join(node_path, 'storage_info.json')
            with open(info_file, 'w') as f:
                json.dump(storage_info, f, indent=2)
            
            self.node_paths[node_id] = node_path
            
            # Update current usage
            self.update_node_usage(node_id)
            
            return node_path
    
    def update_node_usage(self, node_id):
        """Update the storage usage for a node"""
        if node_id not in self.node_paths:
            return
            
        node_path = self.node_paths[node_id]
        total, used, free = self.get_disk_usage(node_path)
        
        info_file = os.path.join(node_path, 'storage_info.json')
        if os.path.exists(info_file):
            with open(info_file, 'r') as f:
                storage_info = json.load(f)
            
            storage_info['used_gb'] = used
            storage_info['available_gb'] = free
            storage_info['last_updated'] = datetime.now().isoformat()
            storage_info['usage_percentage'] = (used / self.STORAGE_PER_NODE) * 100
            
            with open(info_file, 'w') as f:
                json.dump(storage_info, f, indent=2)
    
    def get_disk_usage(self, path):
        """Get disk usage statistics for a path"""
        try:
            total, used, free = shutil.disk_usage(path)
            # Convert bytes to GB
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            return total_gb, used_gb, free_gb
        except Exception as e:
            print(f"⚠️ Error getting disk usage for {path}: {e}")
            return 0, 0, 0
    
    def get_all_nodes_storage(self):
        """Get storage info for all nodes"""
        storage_info = {}
        for node_id, path in self.node_paths.items():
            total, used, free = self.get_disk_usage(path)
            storage_info[node_id] = {
                'path': path,
                'total_gb': total,
                'used_gb': used,
                'free_gb': free,
                'allocated_gb': self.STORAGE_PER_NODE,
                'usage_percentage': (used / self.STORAGE_PER_NODE) * 100 if self.STORAGE_PER_NODE > 0 else 0,
                'status': 'active' if os.path.exists(path) else 'inactive'
            }
        return storage_info
    
    def get_total_system_storage(self):
        """Get total system disk space"""
        total, used, free = shutil.disk_usage("/")
        return {
            'total_gb': total / (1024**3),
            'used_gb': used / (1024**3),
            'free_gb': free / (1024**3),
            'usage_percentage': (used / total) * 100
        }
    
    def cleanup_old_files(self, node_id, days_old=30):
        """Clean up files older than specified days"""
        if node_id not in self.node_paths:
            return
            
        node_path = self.node_paths[node_id]
        cache_path = os.path.join(node_path, 'cache')
        log_path = os.path.join(node_path, 'logs')
        
        deleted_files = 0
        deleted_size = 0
        
        for dir_path in [cache_path, log_path]:
            if os.path.exists(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_age = datetime.now().timestamp() - os.path.getmtime(file_path)
                            if file_age > (days_old * 24 * 3600):
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                deleted_files += 1
                                deleted_size += file_size
                        except:
                            pass
        
        if deleted_files > 0:
            print(f"🧹 Cleaned up {deleted_files} old files ({deleted_size/1024/1024:.2f} MB) from {node_id}")
        
        return deleted_files, deleted_size

# Global storage manager instance
storage_manager = StorageManager()