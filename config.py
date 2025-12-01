"""
Configuration for the distributed storage system
"""
import os
from dataclasses import dataclass

@dataclass
class Config:
    """System configuration"""
    # Network settings
    CONTROLLER_HOST = "localhost"
    CONTROLLER_PORT = 5001
    NODE_PORT_RANGE = (6001, 6010)
    
    # Storage settings
    DEFAULT_NODE_COUNT = 5
    MIN_NODE_COUNT = 3
    REPLICATION_FACTOR = 3  # Number of copies for each file
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    
    # Node resources (for auto-created nodes)
    NODE_CPU_CORES = 4
    NODE_MEMORY_GB = 8
    NODE_STORAGE_GB = 500
    NODE_BANDWIDTH_MBPS = 1000
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    NODE_STORAGE_DIR = os.path.join(BASE_DIR, "data", "node_storage")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    
    # Web interface
    SECRET_KEY = "distributed-cloud-storage-secret-key-2024"
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB max upload
    
    @classmethod
    def init_directories(cls):
        """Initialize required directories"""
        os.makedirs(cls.NODE_STORAGE_DIR, exist_ok=True)
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        
        # Create node directories
        for i in range(1, cls.DEFAULT_NODE_COUNT + 1):
            node_dir = os.path.join(cls.NODE_STORAGE_DIR, f"node{i}")
            os.makedirs(node_dir, exist_ok=True)