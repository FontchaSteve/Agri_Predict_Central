#!/usr/bin/env python3
"""
Clean Storage Node
Single communication system - no conflicts, no gRPC, no packet managers
"""

import socket
import threading
import time
import pickle
import json
import os
import hashlib
import concurrent.futures
from typing import Dict, Any, Optional, List


class CleanNode:
    """Enhanced distributed storage node with resource management"""

    def __init__(
        self,
        node_id: str,
        cpu_cores: int = 4,
        memory_gb: int = 16,
        storage_gb: int = 1000,
        bandwidth_mbps: int = 1000,
        controller_host: str = 'localhost',
        controller_port: int = 5000,
        interactive: bool = False
    ):
        self.node_id = node_id
        self.cpu_cores = cpu_cores
        self.memory_gb = memory_gb
        self.storage_gb = storage_gb
        self.bandwidth_mbps = bandwidth_mbps
        self.controller_host = controller_host
        self.controller_port = controller_port
        self.interactive = interactive

        # Storage management
        self.storage_dir = f"node_storage_{node_id}"
        self.total_storage = storage_gb * 1024 ** 3  # Convert to bytes
        self.used_storage = 0
        self.files = {}

        # Transfer management
        self.active_transfers = 0
        self.max_concurrent_transfers = min(cpu_cores, 4)  # Limit based on CPU
        self.transfer_threads = {}

        # Threading
        self.running = False
        self.heartbeat_thread = None
        self.interactive_thread = None

        # Connection management
        self.connection_lock = threading.Lock()
        self.last_heartbeat_success = time.time()

        # Statistics
        self.total_uploads = 0
        self.total_downloads = 0
        self.bytes_transferred = 0

        # Create storage directory
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def start(self) -> bool:
        """Start the node"""
        try:
            # Register with controller
            if not self._register():
                print(f"❌ Failed to register {self.node_id}")
                return False
            
            self.running = True
            
            # Start heartbeat
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            
            # Start interactive mode if requested
            if self.interactive:
                self._start_interactive_mode()
            
            print(f"✅ Node {self.node_id} started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Node start failed: {e}")
            return False
    
    def _register(self) -> bool:
        """Register with controller with resource information"""
        try:
            message = {
                'action': 'REGISTER',
                'node_id': self.node_id,
                'host': 'localhost',
                'port': 0,  # Not using separate port
                'resources': {
                    'cpu_cores': self.cpu_cores,
                    'memory_gb': self.memory_gb,
                    'storage_gb': self.storage_gb,
                    'bandwidth_mbps': self.bandwidth_mbps
                }
            }
            
            response = self._send_message(message)
            
            if response and response.get('status') == 'OK':
                print(f"[Node {self.node_id}] Registered successfully")
                return True
            else:
                error = response.get('error', 'Unknown error') if response else 'No response'
                print(f"[Node {self.node_id}] Registration failed: {error}")
                return False
                
        except Exception as e:
            print(f"[Node {self.node_id}] Registration error: {e}")
            return False
    
    def _send_message(self, message: Dict[str, Any], timeout: int = 10) -> Optional[Dict[str, Any]]:
        """Send message to controller"""
        with self.connection_lock:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(timeout)
                    s.connect((self.controller_host, self.controller_port))
                    s.sendall(pickle.dumps(message))
                    
                    response_data = s.recv(8192)
                    return pickle.loads(response_data)
                    
            except Exception as e:
                print(f"⚠️  Message send failed: {e}")
                return None
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        consecutive_failures = 0
        
        while self.running:
            try:
                message = {
                    'action': 'HEARTBEAT',
                    'node_id': self.node_id
                }
                
                response = self._send_message(message, timeout=8)
                
                if response and response.get('status') == 'ACK':
                    consecutive_failures = 0
                    self.last_heartbeat_success = time.time()
                else:
                    consecutive_failures += 1
                    if consecutive_failures <= 3:
                        error = response.get('error', 'No response') if response else 'Connection failed'
                        print(f"⚠️  Heartbeat failed: {error}")
                
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures <= 3:
                    print(f"⚠️  Heartbeat error: {e}")
            
            # Adaptive sleep
            sleep_time = 5 if consecutive_failures == 0 else min(10, 5 + consecutive_failures)
            time.sleep(sleep_time)
    
    def create_file(self, file_name: str, size_mb: int) -> bool:
        """Create a file with storage validation and progress tracking"""
        try:
            size_bytes = size_mb * 1024 * 1024

            # Check available storage
            if self.used_storage + size_bytes > self.total_storage:
                available_mb = (self.total_storage - self.used_storage) / (1024 * 1024)
                print(f"❌ Insufficient storage. Available: {available_mb:.1f} MB, Required: {size_mb} MB")
                return False

            file_path = os.path.join(self.storage_dir, file_name)

            print(f"📝 Creating {file_name} ({size_mb} MB)...")
            print(f"💾 Storage: {self.used_storage/(1024**3):.1f}/{self.storage_gb} GB used")

            # Adaptive chunk size based on file size and CPU
            if size_mb < 10:
                chunk_size = 512 * 1024  # 512KB for small files
            elif size_mb < 100:
                chunk_size = 1024 * 1024  # 1MB for medium files
            else:
                chunk_size = min(5 * 1024 * 1024, size_bytes // (self.cpu_cores * 2))  # Larger chunks for big files

            # Create file with progress tracking
            start_time = time.time()
            last_progress_time = start_time

            with open(file_path, 'wb') as f:
                written = 0
                while written < size_bytes:
                    write_size = min(chunk_size, size_bytes - written)

                    # Simulate CPU-bound work (data generation)
                    chunk_start = time.time()
                    data = os.urandom(write_size)
                    f.write(data)
                    chunk_time = time.time() - chunk_start

                    written += write_size
                    current_time = time.time()

                    # Show progress for larger files
                    if size_mb >= 10 and (current_time - last_progress_time >= 0.5 or written == size_bytes):
                        progress = (written / size_bytes) * 100
                        elapsed = current_time - start_time
                        rate = (written / elapsed) / (1024 * 1024) if elapsed > 0 else 0

                        # More accurate ETA calculation
                        if written > 0 and elapsed > 0:
                            bytes_per_second = written / elapsed
                            remaining_bytes = size_bytes - written
                            eta = remaining_bytes / bytes_per_second
                        else:
                            eta = 0

                        print(f"   📈 Progress: {progress:.1f}% ({written/(1024*1024):.1f}/{size_mb:.1f} MB) - {rate:.1f} MB/s - ETA: {eta:.1f}s")
                        last_progress_time = current_time

            elapsed = time.time() - start_time
            rate = size_mb / elapsed if elapsed > 0 else 0
            print(f"✅ File created in {elapsed:.1f}s at {rate:.1f} MB/s")

            # Update storage usage
            self.used_storage += size_bytes

            # Notify controller and trigger automatic upload
            success = self._notify_file_created(file_name, size_bytes, file_path)

            if success:
                # Store file info locally
                file_id = hashlib.md5(f"{self.node_id}_{file_name}_{time.time()}".encode()).hexdigest()
                self.files[file_id] = {
                    'name': file_name,
                    'size': size_bytes,
                    'path': file_path,
                    'created_at': time.time(),
                    'chunk_size': chunk_size
                }
                self.total_uploads += 1

            return success

        except Exception as e:
            print(f"❌ File creation failed: {e}")
            return False
    
    def _notify_file_created(self, file_name: str, file_size: int, file_path: str) -> bool:
        """Notify controller about file creation"""
        try:
            file_id = hashlib.md5(f"{self.node_id}_{file_name}_{time.time()}".encode()).hexdigest()
            
            message = {
                'action': 'FILE_CREATED',
                'node_id': self.node_id,
                'file_info': {
                    'file_id': file_id,
                    'file_name': file_name,
                    'file_size': file_size,
                    'owner_node': self.node_id,
                    'file_path': file_path
                }
            }
            
            print(f"📡 Notifying controller about {file_name}...")
            
            response = self._send_message(message, timeout=15)
            
            if response and response.get('status') == 'ACK':
                print(f"✅ File {file_name} successfully registered with controller!")
                # File info already stored in create_file method, no need to duplicate
                return True
            else:
                error = response.get('error', 'No response') if response else 'Connection failed'
                print(f"❌ File notification failed: {error}")
                return False
                
        except Exception as e:
            print(f"❌ File notification error: {e}")
            return False
    
    def download_file(self, file_id: str) -> bool:
        """Download a file from the network"""
        try:
            # Request download from controller
            message = {
                'action': 'DOWNLOAD_REQUEST',
                'node_id': self.node_id,
                'file_id': file_id
            }

            print(f"📥 Requesting download for file {file_id}...")
            response = self._send_message(message, timeout=15)

            if not response or response.get('status') != 'OK':
                error = response.get('error', 'No response') if response else 'Connection failed'
                print(f"❌ Download request failed: {error}")
                return False

            # Extract transfer information
            source_node = response['source_node']
            file_info = response['file_info']
            transfer_params = response['transfer_params']

            file_name = file_info['file_name']
            file_size = file_info['file_size']
            chunk_size = file_info['chunk_size']
            total_chunks = file_info['total_chunks']
            bandwidth_mbps = transfer_params['bandwidth_mbps']

            print(f"📡 Downloading {file_name} ({file_size/(1024*1024):.1f} MB) from {source_node}")
            print(f"⚡ Bandwidth: {bandwidth_mbps} Mbps, Chunks: {total_chunks}")

            # Check storage space
            if self.used_storage + file_size > self.total_storage:
                print(f"❌ Insufficient storage for download")
                return False

            # Start chunked download in separate thread
            download_thread = threading.Thread(
                target=self._download_file_chunked,
                args=(file_info, transfer_params, source_node),
                daemon=True
            )
            download_thread.start()

            return True

        except Exception as e:
            print(f"❌ Download initiation failed: {e}")
            return False

    def _download_file_chunked(self, file_info: Dict, transfer_params: Dict, source_node: str):
        """Perform chunked file download with progress tracking"""
        try:
            file_name = file_info['file_name']
            file_size = file_info['file_size']
            chunk_size = file_info['chunk_size']
            total_chunks = file_info['total_chunks']
            bandwidth_mbps = transfer_params['bandwidth_mbps']

            # Calculate transfer timing
            bytes_per_second = (bandwidth_mbps * 1024 * 1024) / 8  # Convert Mbps to bytes/sec
            chunk_transfer_time = chunk_size / bytes_per_second

            file_path = os.path.join(self.storage_dir, file_name)
            start_time = time.time()

            # Use parallel downloads for large files with multiple CPU cores
            if total_chunks > 4 and self.cpu_cores > 2:
                print(f"🔄 Starting parallel chunked download: {total_chunks} chunks of {chunk_size/(1024*1024):.1f} MB each")
                print(f"⚡ Using {min(self.cpu_cores, 4)} parallel threads for optimal performance")
                self._parallel_chunked_download(file_path, file_size, chunk_size, total_chunks, chunk_transfer_time, start_time)
            else:
                print(f"🔄 Starting sequential chunked download: {total_chunks} chunks of {chunk_size/(1024*1024):.1f} MB each")
                self._sequential_chunked_download(file_path, file_size, chunk_size, total_chunks, chunk_transfer_time, start_time)

            # Download completed
            elapsed = time.time() - start_time
            rate = (file_size / elapsed) / (1024 * 1024) if elapsed > 0 else 0

            print(f"✅ Download completed in {elapsed:.1f}s at {rate:.1f} MB/s")

            # Update local storage
            self.used_storage += file_size
            self.total_downloads += 1
            self.bytes_transferred += file_size

            # Store file info
            self.files[file_info['file_id']] = {
                'name': file_name,
                'size': file_size,
                'path': file_path,
                'downloaded_at': time.time(),
                'source_node': source_node
            }

            # Notify controller of completion
            self._notify_transfer_complete(file_info['file_id'], 'download')

        except Exception as e:
            print(f"❌ Chunked download failed: {e}")

    def _sequential_chunked_download(self, file_path: str, file_size: int, chunk_size: int, total_chunks: int, chunk_transfer_time: float, start_time: float):
        """Sequential chunk download for smaller files or limited CPU"""
        with open(file_path, 'wb') as f:
            downloaded = 0

            for chunk_num in range(total_chunks):
                chunk_start_time = time.time()

                # Simulate chunk download (in real system, would request from source node)
                actual_chunk_size = min(chunk_size, file_size - downloaded)
                chunk_data = os.urandom(actual_chunk_size)
                f.write(chunk_data)
                downloaded += actual_chunk_size

                # Simulate network transfer time based on bandwidth
                elapsed_chunk_time = time.time() - chunk_start_time
                if elapsed_chunk_time < chunk_transfer_time:
                    time.sleep(chunk_transfer_time - elapsed_chunk_time)

                # Progress reporting with accurate calculations
                progress = (downloaded / file_size) * 100
                elapsed_total = time.time() - start_time
                current_rate = (downloaded / elapsed_total) / (1024 * 1024) if elapsed_total > 0 else 0

                # More accurate ETA calculation
                if downloaded > 0 and elapsed_total > 0:
                    bytes_per_second = downloaded / elapsed_total
                    remaining_bytes = file_size - downloaded
                    eta = remaining_bytes / bytes_per_second
                else:
                    eta = 0

                if chunk_num % max(1, total_chunks // 10) == 0 or chunk_num == total_chunks - 1:
                    print(f"   📈 Download: {progress:.1f}% ({downloaded/(1024*1024):.1f}/{file_size/(1024*1024):.1f} MB) - {current_rate:.1f} MB/s - ETA: {eta:.1f}s")

    def _parallel_chunked_download(self, file_path: str, file_size: int, chunk_size: int, total_chunks: int, chunk_transfer_time: float, start_time: float):
        """Parallel chunk download for large files with multiple threads"""
        # Create temporary file for each chunk
        chunk_files = []
        max_workers = min(self.cpu_cores, 4)  # Limit to 4 threads max

        def download_chunk(chunk_num: int) -> tuple:
            """Download a single chunk"""
            chunk_start_time = time.time()
            actual_chunk_size = min(chunk_size, file_size - (chunk_num * chunk_size))

            # Simulate chunk download
            chunk_data = os.urandom(actual_chunk_size)

            # Simulate network transfer time
            elapsed_chunk_time = time.time() - chunk_start_time
            if elapsed_chunk_time < chunk_transfer_time:
                time.sleep(chunk_transfer_time - elapsed_chunk_time)

            return chunk_num, chunk_data

        # Download chunks in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunk download tasks
            future_to_chunk = {executor.submit(download_chunk, i): i for i in range(total_chunks)}

            # Collect results as they complete
            chunk_results = {}
            downloaded = 0

            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_num, chunk_data = future.result()
                chunk_results[chunk_num] = chunk_data
                downloaded += len(chunk_data)

                # Progress reporting
                progress = (downloaded / file_size) * 100
                elapsed_total = time.time() - start_time
                current_rate = (downloaded / elapsed_total) / (1024 * 1024) if elapsed_total > 0 else 0

                # More accurate ETA calculation
                if downloaded > 0 and elapsed_total > 0:
                    bytes_per_second = downloaded / elapsed_total
                    remaining_bytes = file_size - downloaded
                    eta = remaining_bytes / bytes_per_second
                else:
                    eta = 0

                if len(chunk_results) % max(1, total_chunks // 10) == 0 or len(chunk_results) == total_chunks:
                    print(f"   📈 Parallel Download: {progress:.1f}% ({downloaded/(1024*1024):.1f}/{file_size/(1024*1024):.1f} MB) - {current_rate:.1f} MB/s - ETA: {eta:.1f}s - Threads: {max_workers}")

        # Write chunks to file in correct order
        with open(file_path, 'wb') as f:
            for chunk_num in range(total_chunks):
                f.write(chunk_results[chunk_num])

    def list_files(self):
        """List files on this node"""
        if not self.files:
            print("📂 No files on this node")
            return

        print(f"📂 Local Files on {self.node_id}:")
        print("-" * 50)
        for file_info in self.files.values():
            size_mb = file_info['size'] / (1024 * 1024)
            source = file_info.get('source_node', 'local')
            status = "📥 Downloaded" if 'downloaded_at' in file_info else "📝 Created"
            print(f"{status} {file_info['name']} ({size_mb:.2f} MB) from {source}")
        print("-" * 50)

    def list_available_files(self):
        """List all files available in the network"""
        try:
            message = {
                'action': 'LIST_FILES',
                'node_id': self.node_id
            }

            response = self._send_message(message, timeout=10)

            if not response or response.get('status') != 'OK':
                print("❌ Failed to get file list from controller")
                return

            files = response.get('files', [])
            total_files = response.get('total_files', 0)

            if not files:
                print("📂 No files available in the network")
                return

            print(f"\n📂 NETWORK FILES AVAILABLE ({total_files} total)")
            print("=" * 90)
            print(f"{'#':<3} {'File Name':<30} {'Size':<12} {'Owner':<12} {'Replicas':<10} {'ID':<8}")
            print("-" * 90)

            for i, file_info in enumerate(files, 1):
                size_mb = file_info['file_size'] / (1024 * 1024)
                file_id_short = file_info['file_id'][:8]
                replica_count = file_info['replica_count']

                print(f"{i:<3} {file_info['file_name']:<30} {size_mb:>8.2f} MB {file_info['owner_node']:<12} {replica_count:<10} {file_id_short:<8}")

            print("=" * 90)
            print("💡 Download options:")
            print("   • Use download_file_by_name('filename') to download by name")
            print("   • Use download_file_by_index(index) to download by number")
            print("   • Use download_multiple_files(['file1', 'file2']) for multiple files")

            # Store file list for easy access
            self._available_files = files

        except Exception as e:
            print(f"❌ Failed to list available files: {e}")

    def download_file_by_index(self, index: int) -> bool:
        """Download file by index from available files list"""
        try:
            if not hasattr(self, '_available_files') or not self._available_files:
                print("❌ No available files. Run list_available_files() first.")
                return False

            if index < 1 or index > len(self._available_files):
                print(f"❌ Invalid index. Choose between 1 and {len(self._available_files)}")
                return False

            file_info = self._available_files[index - 1]
            return self.download_file(file_info['file_id'])

        except Exception as e:
            print(f"❌ Download by index failed: {e}")
            return False

    def download_file_by_name(self, file_name: str) -> bool:
        """Download file by name from available files list"""
        try:
            if not hasattr(self, '_available_files') or not self._available_files:
                print("❌ No available files. Run list_available_files() first.")
                return False

            # Find file by name (case-insensitive)
            matching_files = []
            for file_info in self._available_files:
                if file_info['file_name'].lower() == file_name.lower():
                    matching_files.append(file_info)
                elif file_name.lower() in file_info['file_name'].lower():
                    matching_files.append(file_info)

            if not matching_files:
                print(f"❌ File '{file_name}' not found in network")
                print("💡 Use list_available_files() to see available files")
                return False

            if len(matching_files) > 1:
                print(f"🔍 Multiple files match '{file_name}':")
                for i, file_info in enumerate(matching_files, 1):
                    size_mb = file_info['file_size'] / (1024 * 1024)
                    print(f"   {i}. {file_info['file_name']} ({size_mb:.1f} MB) - {file_info['owner_node']}")

                choice = input("Enter number to select file (or 'all' for all matches): ").strip()

                if choice.lower() == 'all':
                    return self.download_multiple_files([f['file_name'] for f in matching_files])

                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(matching_files):
                        file_info = matching_files[choice_idx]
                        return self.download_file(file_info['file_id'])
                    else:
                        print("❌ Invalid selection")
                        return False
                except ValueError:
                    print("❌ Invalid input")
                    return False
            else:
                # Single match found
                file_info = matching_files[0]
                print(f"📥 Found: {file_info['file_name']} ({file_info['file_size']/(1024*1024):.1f} MB)")
                return self.download_file(file_info['file_id'])

        except Exception as e:
            print(f"❌ Download by name failed: {e}")
            return False

    def download_multiple_files(self, file_names: List[str]) -> bool:
        """Download multiple files by name"""
        try:
            if not hasattr(self, '_available_files') or not self._available_files:
                print("❌ No available files. Run list_available_files() first.")
                return False

            if not file_names:
                print("❌ No file names provided")
                return False

            # Find all matching files
            files_to_download = []
            not_found = []

            for file_name in file_names:
                found = False
                for file_info in self._available_files:
                    if file_info['file_name'].lower() == file_name.lower():
                        files_to_download.append(file_info)
                        found = True
                        break

                if not found:
                    not_found.append(file_name)

            if not_found:
                print(f"⚠️  Files not found: {', '.join(not_found)}")

            if not files_to_download:
                print("❌ No valid files to download")
                return False

            # Calculate total size and check storage
            total_size = sum(f['file_size'] for f in files_to_download)
            if self.used_storage + total_size > self.total_storage:
                available_mb = (self.total_storage - self.used_storage) / (1024 * 1024)
                required_mb = total_size / (1024 * 1024)
                print(f"❌ Insufficient storage. Available: {available_mb:.1f} MB, Required: {required_mb:.1f} MB")
                return False

            # Display download summary
            print(f"\n📥 MULTIPLE FILE DOWNLOAD")
            print("=" * 60)
            print(f"Files to download: {len(files_to_download)}")
            print(f"Total size: {total_size/(1024*1024):.1f} MB")
            print("-" * 60)

            for i, file_info in enumerate(files_to_download, 1):
                size_mb = file_info['file_size'] / (1024 * 1024)
                print(f"{i:2}. {file_info['file_name']:<25} {size_mb:>8.1f} MB")

            print("=" * 60)

            # Confirm download
            confirm = input("Proceed with download? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Download cancelled")
                return False

            # Download files sequentially with progress
            successful_downloads = 0
            failed_downloads = 0

            print(f"\n🚀 Starting batch download of {len(files_to_download)} files...")

            for i, file_info in enumerate(files_to_download, 1):
                print(f"\n📥 [{i}/{len(files_to_download)}] Downloading {file_info['file_name']}...")

                if self.download_file(file_info['file_id']):
                    successful_downloads += 1
                    print(f"✅ [{i}/{len(files_to_download)}] {file_info['file_name']} completed")
                else:
                    failed_downloads += 1
                    print(f"❌ [{i}/{len(files_to_download)}] {file_info['file_name']} failed")

                # Brief pause between downloads to prevent overwhelming the system
                if i < len(files_to_download):
                    time.sleep(1)

            # Summary
            print(f"\n📊 BATCH DOWNLOAD SUMMARY")
            print("=" * 50)
            print(f"✅ Successful: {successful_downloads}")
            print(f"❌ Failed: {failed_downloads}")
            print(f"📈 Success Rate: {successful_downloads/len(files_to_download)*100:.1f}%")
            print("=" * 50)

            return successful_downloads > 0

        except Exception as e:
            print(f"❌ Multiple file download failed: {e}")
            return False

    def _notify_transfer_complete(self, file_id: str, transfer_type: str):
        """Notify controller of transfer completion"""
        try:
            message = {
                'action': 'TRANSFER_COMPLETE',
                'node_id': self.node_id,
                'file_id': file_id,
                'transfer_type': transfer_type
            }

            response = self._send_message(message, timeout=10)
            if response and response.get('status') == 'OK':
                print(f"📡 Transfer completion notified to controller")

        except Exception as e:
            print(f"⚠️  Transfer completion notification failed: {e}")
    
    def _start_interactive_mode(self):
        """Start interactive terminal"""
        print(f"\n🌟 INTERACTIVE TERMINAL FOR NODE: {self.node_id}")
        print("=" * 60)
        print("This node now has its own interactive terminal!")
        print("You can perform all file operations directly from here.")
        print("=" * 60)
        
        self.interactive_thread = threading.Thread(target=self._interactive_loop, daemon=True)
        self.interactive_thread.start()
    
    def _interactive_loop(self):
        """Enhanced interactive menu loop"""
        while self.running:
            try:
                print(f"\n🖥️  NODE {self.node_id} - ENHANCED INTERACTIVE TERMINAL")
                print("=" * 70)
                print("1. 📝 Create file")
                print("2. 📋 List local files")
                print("3. 📂 List available network files")
                print("4. 📥 Download file by index")
                print("5. 📄 Download file by name")
                print("6. 📦 Download multiple files")
                print("7. 📊 Show node statistics")
                print("8. 🌐 Show network status")
                print("9. ❌ Exit interactive mode")
                print("-" * 70)
                
                choice = input(f"[{self.node_id}] Enter your choice (1-9): ").strip()

                if choice == '1':
                    self._interactive_create_file()
                elif choice == '2':
                    self.list_files()
                elif choice == '3':
                    self.list_available_files()
                elif choice == '4':
                    self._interactive_download_file_by_index()
                elif choice == '5':
                    self._interactive_download_file_by_name()
                elif choice == '6':
                    self._interactive_download_multiple_files()
                elif choice == '7':
                    self._show_statistics()
                elif choice == '8':
                    self._show_network_status()
                elif choice == '9':
                    print("👋 Exiting interactive mode...")
                    break
                else:
                    print("❌ Invalid choice. Please try again.")
                    
                input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Interactive error: {e}")
    
    def _interactive_create_file(self):
        """Interactive file creation"""
        try:
            print(f"\n📝 Create File on {self.node_id}")
            print("-" * 35)
            
            file_name = input("Enter file name: ").strip()
            if not file_name:
                print("❌ File name cannot be empty")
                return
            
            size_input = input("Enter file size in MB (max 1000 MB): ").strip()
            try:
                size_mb = int(size_input)
                if size_mb <= 0 or size_mb > 1000:
                    print("❌ File size must be between 1 and 1000 MB")
                    return
            except ValueError:
                print("❌ Invalid file size")
                return
            
            success = self.create_file(file_name, size_mb)
            if success:
                print(f"🎉 File {file_name} created and registered successfully!")
            else:
                print(f"❌ Failed to create or register {file_name}")
                
        except Exception as e:
            print(f"❌ File creation error: {e}")

    def _interactive_download_file_by_index(self):
        """Interactive file download by index"""
        try:
            if not hasattr(self, '_available_files') or not self._available_files:
                print("❌ No available files. Please list network files first (option 3).")
                return

            print(f"\n📥 Download File by Index to {self.node_id}")
            print("-" * 50)

            index_input = input(f"Enter file index (1-{len(self._available_files)}): ").strip()
            try:
                index = int(index_input)
                if index < 1 or index > len(self._available_files):
                    print(f"❌ Invalid index. Choose between 1 and {len(self._available_files)}")
                    return
            except ValueError:
                print("❌ Invalid index")
                return

            file_info = self._available_files[index - 1]
            file_name = file_info['file_name']
            file_size_mb = file_info['file_size'] / (1024 * 1024)

            # Check if file already exists locally
            for local_file in self.files.values():
                if local_file['name'] == file_name:
                    print(f"⚠️  File {file_name} already exists locally")
                    overwrite = input("Overwrite? (y/n): ").strip().lower()
                    if overwrite != 'y':
                        return
                    break

            print(f"🚀 Starting download of {file_name} ({file_size_mb:.1f} MB)...")
            success = self.download_file_by_index(index)

            if success:
                print(f"🎉 Download initiated successfully!")
            else:
                print(f"❌ Failed to initiate download")

        except Exception as e:
            print(f"❌ Download error: {e}")

    def _interactive_download_file_by_name(self):
        """Interactive file download by name"""
        try:
            if not hasattr(self, '_available_files') or not self._available_files:
                print("❌ No available files. Please list network files first (option 3).")
                return

            print(f"\n📄 Download File by Name to {self.node_id}")
            print("-" * 50)
            print("💡 You can enter:")
            print("   • Exact file name: 'document.pdf'")
            print("   • Partial name: 'doc' (will show matches)")
            print("   • Leave empty to see all available files")

            file_name = input("Enter file name: ").strip()

            if not file_name:
                # Show available files for reference
                print("\n📂 Available files:")
                for i, file_info in enumerate(self._available_files, 1):
                    size_mb = file_info['file_size'] / (1024 * 1024)
                    print(f"   {i:2}. {file_info['file_name']} ({size_mb:.1f} MB)")
                return

            print(f"🔍 Searching for '{file_name}'...")
            success = self.download_file_by_name(file_name)

            if success:
                print(f"🎉 Download completed successfully!")
            else:
                print(f"❌ Download failed or cancelled")

        except Exception as e:
            print(f"❌ Download error: {e}")

    def _interactive_download_multiple_files(self):
        """Interactive multiple file download"""
        try:
            if not hasattr(self, '_available_files') or not self._available_files:
                print("❌ No available files. Please list network files first (option 3).")
                return

            print(f"\n📦 Download Multiple Files to {self.node_id}")
            print("-" * 60)
            print("💡 Enter file names separated by commas:")
            print("   Example: file1.txt, document.pdf, image.jpg")
            print("   Or enter 'all' to download all available files")

            # Show available files for reference
            print(f"\n📂 Available files ({len(self._available_files)} total):")
            total_size = 0
            for i, file_info in enumerate(self._available_files, 1):
                size_mb = file_info['file_size'] / (1024 * 1024)
                total_size += file_info['file_size']
                print(f"   {i:2}. {file_info['file_name']:<30} ({size_mb:>6.1f} MB)")

            print(f"\nTotal size of all files: {total_size/(1024*1024):.1f} MB")
            print("-" * 60)

            user_input = input("Enter file names (or 'all'): ").strip()

            if not user_input:
                print("❌ No files specified")
                return

            if user_input.lower() == 'all':
                file_names = [f['file_name'] for f in self._available_files]
                print(f"📦 Selected all {len(file_names)} files for download")
            else:
                # Parse comma-separated file names
                file_names = [name.strip() for name in user_input.split(',') if name.strip()]
                if not file_names:
                    print("❌ No valid file names provided")
                    return
                print(f"📦 Selected {len(file_names)} files for download")

            success = self.download_multiple_files(file_names)

            if success:
                print(f"🎉 Batch download completed!")
            else:
                print(f"❌ Batch download failed")

        except Exception as e:
            print(f"❌ Multiple download error: {e}")

    def _show_network_status(self):
        """Show network status from node perspective"""
        print(f"\n🌐 Network Status from {self.node_id}")
        print("-" * 50)
        print(f"🔗 Controller: {'✅ Connected' if time.time() - self.last_heartbeat_success < 30 else '❌ Disconnected'}")
        print(f"📊 Active Transfers: {self.active_transfers}/{self.max_concurrent_transfers}")
        print(f"📈 Total Uploads: {self.total_uploads}")
        print(f"📉 Total Downloads: {self.total_downloads}")
        print(f"💾 Data Transferred: {self.bytes_transferred / (1024**2):.1f} MB")

    def _show_statistics(self):
        """Show enhanced node statistics"""
        print(f"\n📊 Node {self.node_id} Enhanced Statistics")
        print("-" * 60)

        # Resource information
        print("🖥️  RESOURCES:")
        print(f"   CPU Cores: {self.cpu_cores}")
        print(f"   Memory: {self.memory_gb} GB")
        print(f"   Bandwidth: {self.bandwidth_mbps} Mbps")

        # Storage information
        storage_used_gb = self.used_storage / (1024**3)
        storage_percent = (self.used_storage / self.total_storage) * 100
        print(f"\n💾 STORAGE:")
        print(f"   Used: {storage_used_gb:.2f} GB / {self.storage_gb} GB ({storage_percent:.1f}%)")
        print(f"   Available: {(self.total_storage - self.used_storage) / (1024**3):.2f} GB")
        print(f"   Files: {len(self.files)}")

        # Transfer statistics
        print(f"\n📊 TRANSFERS:")
        print(f"   Active: {self.active_transfers}/{self.max_concurrent_transfers}")
        print(f"   Total Uploads: {self.total_uploads}")
        print(f"   Total Downloads: {self.total_downloads}")
        print(f"   Data Transferred: {self.bytes_transferred / (1024**2):.1f} MB")

        # Connection status
        connection_status = "✅ Active" if time.time() - self.last_heartbeat_success < 30 else "❌ Inactive"
        print(f"\n🔗 CONNECTION:")
        print(f"   Controller: {connection_status}")
        print(f"   Last Heartbeat: {time.time() - self.last_heartbeat_success:.1f}s ago")

        # System status
        print(f"\n⚡ STATUS:")
        print(f"   Node: {'🟢 Running' if self.running else '🔴 Stopped'}")
        print(f"   Storage Directory: {self.storage_dir}")
        print(f"   Interactive Mode: {'✅ Enabled' if self.interactive else '❌ Disabled'}")
    
    def stop(self):
        """Stop the node"""
        self.running = False
        print(f"🛑 Node {self.node_id} stopped")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Distributed Cloud Storage Node')
    parser.add_argument('--node-id', required=True, help='Node identifier')
    parser.add_argument('--cpu', type=int, required=True, help='CPU cores (required)')
    parser.add_argument('--memory', type=int, required=True, help='Memory in GB (required)')
    parser.add_argument('--storage', type=int, required=True, help='Storage capacity in GB (required)')
    parser.add_argument('--bandwidth', type=int, required=True, help='Bandwidth in Mbps (required)')
    parser.add_argument('--controller-host', default='localhost', help='Controller host')
    parser.add_argument('--controller-port', type=int, default=5000, help='Controller port')
    parser.add_argument('--interactive', action='store_true', help='Enable interactive mode')

    args = parser.parse_args()

    print(f"🚀 ENHANCED DISTRIBUTED STORAGE NODE: {args.node_id}")
    print("=" * 70)
    print("✅ Resource-aware node management")
    print("✅ Chunked file transfers with progress tracking")
    print("✅ Bandwidth-aware transfer timing")
    print("✅ Automatic storage validation")
    print("✅ Real-time transfer statistics")
    print("✅ Fault-tolerant file replication")
    print("=" * 70)
    print(f"🖥️  Resources: {args.cpu} CPU, {args.memory}GB RAM, {args.storage}GB Storage, {args.bandwidth}Mbps")
    print("=" * 70)
    
    node = CleanNode(
        node_id=args.node_id,
        cpu_cores=args.cpu,
        memory_gb=args.memory,
        storage_gb=args.storage,
        bandwidth_mbps=args.bandwidth,
        controller_host=args.controller_host,
        controller_port=args.controller_port,
        interactive=args.interactive
    )
    
    try:
        if node.start():
            if args.interactive:
                print(f"🎮 Node {args.node_id} running in INTERACTIVE MODE!")
                print("Use the interactive terminal above.")
                print("Press Ctrl+C to stop the node.")
            else:
                print(f"✅ Node {args.node_id} running. Press Ctrl+C to stop.")
            
            # Keep running
            while node.running:
                time.sleep(1)
        else:
            print(f"❌ Failed to start node {args.node_id}")
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Stopping node {args.node_id}...")
    finally:
        node.stop()


if __name__ == "__main__":
    main()
