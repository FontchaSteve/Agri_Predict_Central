import socket
import json
import threading
import time
import uuid
import sys
from datetime import datetime

class VirtualNode:
    def __init__(self, node_name, storage_capacity, cpu_cores, memory,
                 hub_host='localhost', hub_port=5555):
        self.node_id = str(uuid.uuid4())[:8]
        self.node_name = node_name
        self.storage_capacity = storage_capacity
        self.cpu_cores = cpu_cores
        self.memory = memory
        self.hub_host = hub_host
        self.hub_port = hub_port
        self.socket = None
        self.connected = False
        self.running = False
        
    def connect_to_network(self):
        """Connect this node to the network hub"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.hub_host, self.hub_port))
            
            # Send node information to hub
            node_data = {
                'node_id': self.node_id,
                'node_name': self.node_name,
                'storage_capacity': self.storage_capacity,
                'cpu_cores': self.cpu_cores,
                'memory': self.memory,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.socket.send(json.dumps(node_data).encode('utf-8'))
            
            # Wait for acknowledgment
            response = self.socket.recv(4096).decode('utf-8')
            response_data = json.loads(response)
            
            if response_data.get('status') == 'connected':
                self.connected = True
                self.running = True
                print("=" * 60)
                print("[SUCCESS] NODE CONNECTED TO NETWORK")
                print("=" * 60)
                print(f"Node ID:     {self.node_id}")
                print(f"Node Name:   {self.node_name}")
                print(f"Hub:         {self.hub_host}:{self.hub_port}")
                print("=" * 60)
                print("\n[ACTIVE] Node is now active and running...")
                print("Press Ctrl+C to disconnect\n")
                
                # Start heartbeat thread
                heartbeat_thread = threading.Thread(target=self.send_heartbeat)
                heartbeat_thread.daemon = True
                heartbeat_thread.start()
                
                # Keep node running
                while self.running:
                    time.sleep(1)
                    
            else:
                print("[ERROR] Failed to connect to network hub")
                
        except ConnectionRefusedError:
            print("[ERROR] Connection refused. Make sure the network hub is running!")
        except Exception as e:
            print(f"[ERROR] Error connecting to network: {e}")
        finally:
            self.disconnect()
            
    def send_heartbeat(self):
        """Send periodic heartbeat to hub"""
        while self.running and self.connected:
            try:
                heartbeat = {
                    'type': 'heartbeat',
                    'node_id': self.node_id,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                self.socket.send(json.dumps(heartbeat).encode('utf-8'))
                time.sleep(30)  # Send heartbeat every 30 seconds
            except:
                break
                
    def disconnect(self):
        """Disconnect from network hub"""
        self.running = False
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        print("\n[DISCONNECT] Node disconnected from network")

def get_user_input():
    """Get node configuration from user"""
    # Set UTF-8 encoding for Windows
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("\n" + "=" * 60)
    print("VIRTUAL NODE CREATION")
    print("=" * 60)
    
    node_name = input("\n[INPUT] Enter node name: ").strip()
    
    while True:
        try:
            storage = int(input("[INPUT] Enter storage capacity (GB): "))
            if storage > 0:
                break
            print("[ERROR] Storage must be positive")
        except ValueError:
            print("[ERROR] Please enter a valid number")
    
    while True:
        try:
            cpu_cores = int(input("[INPUT] Enter number of CPU cores: "))
            if cpu_cores > 0:
                break
            print("[ERROR] CPU cores must be positive")
        except ValueError:
            print("[ERROR] Please enter a valid number")
    
    while True:
        try:
            memory = int(input("[INPUT] Enter memory (GB): "))
            if memory > 0:
                break
            print("[ERROR] Memory must be positive")
        except ValueError:
            print("[ERROR] Please enter a valid number")
    
    
    
    
    # Network hub configuration
    print("\n[CONFIG] Network Hub Configuration:")
    hub_host = input("[INPUT] Enter hub host (default: localhost): ").strip() or 'localhost'
    
    while True:
        hub_port_input = input("[INPUT] Enter hub port (default: 5555): ").strip() or '5555'
        try:
            hub_port = int(hub_port_input)
            if 1024 <= hub_port <= 65535:
                break
            print("[ERROR] Port must be between 1024 and 65535")
        except ValueError:
            print("[ERROR] Please enter a valid port number")
    
    return {
        'node_name': node_name,
        'storage_capacity': storage,
        'cpu_cores': cpu_cores,
        'memory': memory,
        'hub_host': hub_host,
        'hub_port': hub_port
    }

if __name__ == "__main__":
    # Get node configuration from user
    config = get_user_input()
    
    # Create and connect node
    node = VirtualNode(
        node_name=config['node_name'],
        storage_capacity=config['storage_capacity'],
        cpu_cores=config['cpu_cores'],
        memory=config['memory'],
        hub_host=config['hub_host'],
        hub_port=config['hub_port']
    )
    
    try:
        node.connect_to_network()
    except KeyboardInterrupt:
        print("\n\nDisconnecting node...")
        node.disconnect()