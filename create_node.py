import socket
import json
import threading
import time
import uuid
import sys
import os
from datetime import datetime

class VirtualNode:
    def __init__(self, node_name, storage_capacity, cpu_cores, memory, node_type,
                 hub_host='localhost', hub_port=5555):
        self.node_id = str(uuid.uuid4())[:8]
        self.node_name = node_name
        self.storage_capacity = storage_capacity
        self.cpu_cores = cpu_cores
        self.memory = memory
        self.node_type = node_type
        self.hub_host = hub_host
        self.hub_port = hub_port
        self.socket = None
        self.connected = False
        self.running = False
        self.local_files = {}
        self.message_queue = []
        self.message_lock = threading.Lock()
        
    def connect_to_network(self):
        """Connect this node to the network hub"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((self.hub_host, self.hub_port))
            
            # Send node information to hub
            node_data = {
                'node_id': self.node_id,
                'node_name': self.node_name,
                'storage_capacity': self.storage_capacity,
                'cpu_cores': self.cpu_cores,
                'memory': self.memory,
                'node_type': self.node_type,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.socket.send(json.dumps(node_data).encode('utf-8'))
            
            # Wait for acknowledgment
            response = self.socket.recv(4096).decode('utf-8')
            
            if not response:
                print("❌ No response from hub")
                return
                
            response_data = json.loads(response)
            
            if response_data.get('status') == 'connected':
                self.connected = True
                self.running = True
                
                print("\n" + "=" * 50)
                print("✅ NODE CONNECTED TO NETWORK")
                print("=" * 50)
                print(f"Node ID:    {self.node_id}")
                print(f"Node Name:  {self.node_name}")
                print(f"Node Type:  {self.node_type}")
                print(f"Hub:        {self.hub_host}:{self.hub_port}")
                print("=" * 50)
                
                # Start heartbeat thread
                heartbeat_thread = threading.Thread(target=self.send_heartbeat)
                heartbeat_thread.daemon = True
                heartbeat_thread.start()
                
                # Start message listener thread
                listener_thread = threading.Thread(target=self.listen_for_messages)
                listener_thread.daemon = True
                listener_thread.start()
                
                # Start node OS interface
                self.node_os_interface()
                
            else:
                print(f"❌ Connection failed: {response_data}")
                
        except ConnectionRefusedError:
            print("❌ Connection refused. Make sure the network hub is running!")
            print("💡 Run 'python network_hub.py' in another terminal first")
        except socket.timeout:
            print("❌ Connection timeout. Check hub address and port")
        except Exception as e:
            print(f"❌ Error connecting to network: {e}")
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
                
    def listen_for_messages(self):
        """Listen for incoming messages from hub"""
        self.socket.settimeout(1.0)
        while self.running and self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if data:
                    message = json.loads(data)
                    with self.message_lock:
                        self.message_queue.append(message)
            except socket.timeout:
                continue
            except:
                break
                
    def node_os_interface(self):
        """Mini Operating System Interface for the node"""
        print("\n🖥️  NODE OPERATING SYSTEM STARTED")
        print("Type 'help' for available commands\n")
        
        while self.running and self.connected:
            try:
                # Check for new messages
                self.process_messages()
                
                command = input(f"node@{self.node_name}> ").strip().lower()
                
                if command == 'help':
                    self.show_help()
                elif command == 'status':
                    self.show_status()
                elif command == 'files':
                    self.list_files()
                elif command.startswith('create '):
                    filename = command[7:].strip()
                    self.create_file(filename)
                elif command.startswith('send '):
                    self.send_message(command[5:])
                elif command == 'messages':
                    self.show_messages()
                elif command == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                elif command == 'disconnect':
                    break
                elif command == 'exit':
                    break
                else:
                    print("❌ Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                
    def process_messages(self):
        """Process incoming messages"""
        with self.message_lock:
            while self.message_queue:
                message = self.message_queue.pop(0)
                self.handle_message(message)
                
    def handle_message(self, message):
        """Handle incoming message"""
        msg_type = message.get('type')
        
        if msg_type == 'node_message':
            print(f"\n📨 Message from {message.get('from_node')}: {message.get('content')}")
        elif msg_type == 'broadcast':
            print(f"\n📢 Broadcast from {message.get('from_node')}: {message.get('content')}")
        elif msg_type == 'error':
            print(f"\n❌ Error: {message.get('message')}")
            
    def show_help(self):
        """Show available commands"""
        print("\n📋 AVAILABLE COMMANDS:")
        print("  status      - Show node status")
        print("  files       - List local files")
        print("  create <name> - Create a new file")
        print("  send <node_id> <message> - Send message to another node")
        print("  send all <message> - Broadcast message to all nodes")
        print("  messages    - Show recent messages")
        print("  clear       - Clear screen")
        print("  disconnect  - Disconnect from network")
        print("  exit        - Exit node")
        
    def show_status(self):
        """Show node status"""
        print(f"\n📊 NODE STATUS:")
        print(f"  ID: {self.node_id}")
        print(f"  Name: {self.node_name}")
        print(f"  Type: {self.node_type}")
        print(f"  Storage: {self.storage_capacity} GB")
        print(f"  CPU Cores: {self.cpu_cores}")
        print(f"  Memory: {self.memory} GB")
        print(f"  Files: {len(self.local_files)}")
        print(f"  Status: {'Connected' if self.connected else 'Disconnected'}")
        
    def list_files(self):
        """List local files"""
        if not self.local_files:
            print("\n📁 No files stored locally")
        else:
            print("\n📁 LOCAL FILES:")
            for filename, content in self.local_files.items():
                print(f"  {filename} ({len(content)} bytes)")
                
    def create_file(self, filename):
        """Create a new file"""
        if not filename:
            print("❌ Please specify a filename")
            return
            
        content = input("Enter file content: ")
        self.local_files[filename] = content
        print(f"✅ File '{filename}' created with {len(content)} bytes")
        
    def send_message(self, command):
        """Send message to another node or broadcast"""
        parts = command.split(' ', 1)
        if len(parts) < 2:
            print("❌ Usage: send <node_id|all> <message>")
            return
            
        target = parts[0]
        message_content = parts[1]
        
        if target == 'all':
            # Broadcast message
            message = {
                'type': 'broadcast',
                'content': message_content,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            # Send to specific node
            message = {
                'type': 'node_message',
                'target_node': target,
                'content': message_content,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        try:
            self.socket.send(json.dumps(message).encode('utf-8'))
            print(f"✅ Message sent to {target}")
        except:
            print("❌ Failed to send message")
            
    def show_messages(self):
        """Show recent messages"""
        print("\n📨 No persistent message storage implemented yet")
        print("Messages are displayed in real-time when received")
        
    def disconnect(self):
        """Disconnect from network hub"""
        self.running = False
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        print("\n🔴 Node disconnected from network")

def get_user_input():
    """Get node configuration from user"""
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("\n" + "=" * 50)
    print("🌐 VIRTUAL NODE CREATION")
    print("=" * 50)
    
    node_name = input("\nEnter node name: ").strip()
    
    while True:
        try:
            storage = int(input("Enter storage capacity (GB): "))
            if storage > 0:
                break
            print("Storage must be positive")
        except ValueError:
            print("Please enter a valid number")
    
    while True:
        try:
            cpu_cores = int(input("Enter number of CPU cores: "))
            if cpu_cores > 0:
                break
            print("CPU cores must be positive")
        except ValueError:
            print("Please enter a valid number")
    
    while True:
        try:
            memory = int(input("Enter memory (GB): "))
            if memory > 0:
                break
            print("Memory must be positive")
        except ValueError:
            print("Please enter a valid number")
    
    # Node type selection
    print("\nNode types:")
    print("  1. Storage Node")
    print("  2. Compute Node") 
    print("  3. Gateway Node")
    print("  4. Hybrid Node")
    
    while True:
        try:
            type_choice = int(input("Select node type (1-4): "))
            if 1 <= type_choice <= 4:
                break
            print("Please enter 1, 2, 3, or 4")
        except ValueError:
            print("Please enter a valid number")
    
    node_types = {
        1: "Storage",
        2: "Compute", 
        3: "Gateway",
        4: "Hybrid"
    }
    node_type = node_types[type_choice]
    
    # Network hub configuration
    print("\nNetwork Hub Configuration:")
    hub_host = input("Enter hub host (default: localhost): ").strip() or 'localhost'
    
    while True:
        hub_port_input = input("Enter hub port (default: 5555): ").strip() or '5555'
        try:
            hub_port = int(hub_port_input)
            if 1024 <= hub_port <= 65535:
                break
            print("Port must be between 1024 and 65535")
        except ValueError:
            print("Please enter a valid port number")
    
    return {
        'node_name': node_name,
        'storage_capacity': storage,
        'cpu_cores': cpu_cores,
        'memory': memory,
        'node_type': node_type,
        'hub_host': hub_host,
        'hub_port': hub_port
    }

if __name__ == "__main__":
    config = get_user_input()
    
    node = VirtualNode(
        node_name=config['node_name'],
        storage_capacity=config['storage_capacity'],
        cpu_cores=config['cpu_cores'],
        memory=config['memory'],
        node_type=config['node_type'],
        hub_host=config['hub_host'],
        hub_port=config['hub_port']
    )
    
    try:
        node.connect_to_network()
    except KeyboardInterrupt:
        print("\nDisconnecting node...")
        node.disconnect()