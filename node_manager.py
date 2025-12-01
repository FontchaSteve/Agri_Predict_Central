"""
Automated Node Manager - Starts and manages multiple nodes
"""
import subprocess
import time
import threading
import os
import sys
from typing import List, Dict

from config import Config


class NodeManager:
    """Manages multiple storage nodes"""
    
    def __init__(self):
        self.nodes: Dict[str, subprocess.Popen] = {}
        self.node_processes: List[subprocess.Popen] = []
        
    def start_nodes(self, count: int = Config.DEFAULT_NODE_COUNT):
        """Start multiple storage nodes"""
        print(f"🚀 Starting {count} storage nodes...")
        
        for i in range(1, count + 1):
            node_id = f"node{i}"
            print(f"  Starting {node_id}...")
            
            # Start node process
            proc = subprocess.Popen(
                [sys.executable, "storage_node.py", node_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.nodes[node_id] = proc
            self.node_processes.append(proc)
            
            # Give node time to start
            time.sleep(1)
            
            # Monitor node output
            threading.Thread(
                target=self._monitor_node_output,
                args=(node_id, proc),
                daemon=True
            ).start()
        
        print(f"✅ {count} nodes started successfully")
        print("=" * 60)
    
    def _monitor_node_output(self, node_id: str, process: subprocess.Popen):
        """Monitor node process output"""
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(f"[{node_id}] {line.strip()}")
        except:
            pass
    
    def stop_all_nodes(self):
        """Stop all running nodes"""
        print("\n🛑 Stopping all nodes...")
        
        for node_id, process in self.nodes.items():
            print(f"  Stopping {node_id}...")
            process.terminate()
        
        # Wait for processes to terminate
        time.sleep(2)
        
        # Force kill if still running
        for process in self.node_processes:
            if process.poll() is None:
                process.kill()
        
        print("✅ All nodes stopped")
    
    def get_node_status(self) -> Dict[str, str]:
        """Get status of all nodes"""
        status = {}
        for node_id, process in self.nodes.items():
            if process.poll() is None:
                status[node_id] = "running"
            else:
                status[node_id] = "stopped"
        return status
    
    def restart_node(self, node_id: str):
        """Restart a specific node"""
        if node_id in self.nodes:
            print(f"🔄 Restarting {node_id}...")
            
            # Stop existing process
            old_proc = self.nodes[node_id]
            old_proc.terminate()
            time.sleep(1)
            
            # Start new process
            new_proc = subprocess.Popen(
                [sys.executable, "storage_node.py", node_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.nodes[node_id] = new_proc
            
            # Update monitoring
            threading.Thread(
                target=self._monitor_node_output,
                args=(node_id, new_proc),
                daemon=True
            ).start()
            
            print(f"✅ {node_id} restarted")


def start_network():
    """Start the complete network (controller and nodes)"""
    import multiprocessing
    
    # Initialize directories
    Config.init_directories()
    
    print("=" * 60)
    print("🌐 DISTRIBUTED CLOUD STORAGE SYSTEM")
    print("=" * 60)
    
    # Start controller in separate process
    print("🚀 Starting Network Controller...")
    controller_proc = multiprocessing.Process(
        target=lambda: __import__('network_controller').NetworkController().start()
    )
    controller_proc.start()
    time.sleep(2)  # Wait for controller to start
    
    # Start nodes
    manager = NodeManager()
    manager.start_nodes()
    
    print("\n✅ Network is ready!")
    print("🌐 Controller: http://localhost:5001")
    print("📁 Web Interface: http://localhost:5000")
    print("=" * 60)
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down network...")
        manager.stop_all_nodes()
        controller_proc.terminate()
        print("✅ Network shutdown complete")


if __name__ == "__main__":
    start_network()