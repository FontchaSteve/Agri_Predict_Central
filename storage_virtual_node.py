import time
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from enum import Enum, auto
import hashlib

class TransferStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class FileChunk:
    chunk_id: int
    size: int  # in bytes
    checksum: str
    status: TransferStatus = TransferStatus.PENDING
    stored_node: Optional[str] = None

@dataclass
class FileTransfer:
    file_id: str
    file_name: str
    total_size: int  # in bytes
    chunks: List[FileChunk]
    status: TransferStatus = TransferStatus.PENDING
    created_at: float = time.time()
    completed_at: Optional[float] = None

class StorageVirtualNode:
    def __init__(
        self,
        node_id: str,
        cpu_capacity: int,  # in vCPUs
        memory_capacity: int,  # in GB
        storage_capacity: int,  # in GB
        bandwidth: int  # in Mbps
    ):
        self.node_id = node_id
        self.cpu_capacity = cpu_capacity
        self.memory_capacity = memory_capacity
        self.total_storage = storage_capacity * 1024 * 1024 * 1024  # Convert GB to bytes
        self.bandwidth = bandwidth * 1000000  # Convert Mbps to bits per second
        
        # Current utilization
        self.used_storage = 0
        self.active_transfers: Dict[str, FileTransfer] = {}
        self.stored_files: Dict[str, FileTransfer] = {}
        self.network_utilization = 0  # Current bandwidth usage
        
        # Performance metrics
        self.total_requests_processed = 0
        self.total_data_transferred = 0  # in bytes
        self.failed_transfers = 0
        
        # Network connections (node_id: bandwidth_available)
        self.connections: Dict[str, int] = {}

    def add_connection(self, node_id: str, bandwidth: int):
        """Add a network connection to another node"""
        self.connections[node_id] = bandwidth * 1000000  # Store in bits per second

    def _calculate_chunk_size(self, file_size: int) -> int:
        """Determine optimal chunk size based on file size"""
        # Simple heuristic: larger files get larger chunks
        if file_size < 10 * 1024 * 1024:  # < 10MB
            return 512 * 1024  # 512KB chunks
        elif file_size < 100 * 1024 * 1024:  # < 100MB
            return 2 * 1024 * 1024  # 2MB chunks
        else:
            return 10 * 1024 * 1024  # 10MB chunks

    def _generate_chunks(self, file_id: str, file_size: int) -> List[FileChunk]:
        """Break file into chunks for transfer"""
        chunk_size = self._calculate_chunk_size(file_size)
        num_chunks = math.ceil(file_size / chunk_size)
        
        chunks = []
        for i in range(num_chunks):
            # In a real system, we'd compute actual checksums
            fake_checksum = hashlib.md5(f"{file_id}-{i}".encode()).hexdigest()
            actual_chunk_size = min(chunk_size, file_size - i * chunk_size)
            chunks.append(FileChunk(
                chunk_id=i,
                size=actual_chunk_size,
                checksum=fake_checksum
            ))
        
        return chunks

    def initiate_file_transfer(
        self,
        file_id: str,
        file_name: str,
        file_size: int,
        source_node: Optional[str] = None
    ) -> Optional[FileTransfer]:
        """Initiate a file storage request to this node"""
        # Check if we have enough storage space
        if self.used_storage + file_size > self.total_storage:
            return None
        
        # Create file transfer record
        chunks = self._generate_chunks(file_id, file_size)
        transfer = FileTransfer(
            file_id=file_id,
            file_name=file_name,
            total_size=file_size,
            chunks=chunks
        )
        
        self.active_transfers[file_id] = transfer
        return transfer

    def process_chunk_transfer(
        self,
        file_id: str,
        chunk_id: int,
        source_node: str
    ) -> bool:
        """Process an incoming file chunk"""
        if file_id not in self.active_transfers:
            return False
        
        transfer = self.active_transfers[file_id]
        
        try:
            chunk = next(c for c in transfer.chunks if c.chunk_id == chunk_id)
        except StopIteration:
            return False
        
        # Simulate network transfer time
        chunk_size_bits = chunk.size * 8  # Convert bytes to bits
        available_bandwidth = min(
            self.bandwidth - self.network_utilization,
            self.connections.get(source_node, 0)
        )
        
        if available_bandwidth <= 0:
            return False
        
        # Calculate transfer time (in seconds)
        transfer_time = chunk_size_bits / available_bandwidth
        time.sleep(transfer_time)  # Simulate transfer delay
        
        # Update chunk status
        chunk.status = TransferStatus.COMPLETED
        chunk.stored_node = self.node_id
        
        # Update metrics
        self.network_utilization += available_bandwidth * 0.8  # Simulate some fluctuation
        self.total_data_transferred += chunk.size
        
        # Check if all chunks are completed
        if all(c.status == TransferStatus.COMPLETED for c in transfer.chunks):
            transfer.status = TransferStatus.COMPLETED
            transfer.completed_at = time.time()
            self.used_storage += transfer.total_size
            self.stored_files[file_id] = transfer
            del self.active_transfers[file_id]
            self.total_requests_processed += 1
        
        return True

    def retrieve_file(
        self,
        file_id: str,
        destination_node: str
    ) -> Optional[FileTransfer]:
        """Initiate file retrieval to another node"""
        if file_id not in self.stored_files:
            return None
        
        file_transfer = self.stored_files[file_id]
        
        # Create a new transfer record for the retrieval
        new_transfer = FileTransfer(
            file_id=f"retr-{file_id}-{time.time()}",
            file_name=file_transfer.file_name,
            total_size=file_transfer.total_size,
            chunks=[
                FileChunk(
                    chunk_id=c.chunk_id,
                    size=c.size,
                    checksum=c.checksum,
                    stored_node=destination_node
                )
                for c in file_transfer.chunks
            ]
        )
        
        return new_transfer

    def get_storage_utilization(self) -> Dict[str, Union[int, float, List[str]]]:
        """Get current storage utilization metrics"""
        return {
            "used_bytes": self.used_storage,  # int
            "total_bytes": self.total_storage,  # int
            "utilization_percent": (self.used_storage / self.total_storage) * 100,  # float
            "files_stored": len(self.stored_files),  # int
            "active_transfers": len(self.active_transfers)  # int
            # Note: Removed list[str] since the current implementation doesn't return any lists
        }

    def get_network_utilization(self) -> Dict[str, Union[int, float, List[str]]]:
        """Get current network utilization metrics"""
        total_bandwidth_bps = self.bandwidth
        return {
            "current_utilization_bps": self.network_utilization,  # float
            "max_bandwidth_bps": total_bandwidth_bps,  # int
            "utilization_percent": (self.network_utilization / total_bandwidth_bps) * 100,  # float
            "connections": list(self.connections.keys())  # List[str]
        }

    def get_performance_metrics(self) -> Dict[str, int]:
        """Get node performance metrics"""
        return {
            "total_requests_processed": self.total_requests_processed,
            "total_data_transferred_bytes": self.total_data_transferred,
            "failed_transfers": self.failed_transfers,
            "current_active_transfers": len(self.active_transfers)
        }