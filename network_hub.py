import socket
import threading
import json
import time
import sys
from datetime import datetime

class NetworkHub:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.server_socket = None
        self.connected_nodes = {}
        self.node_lock = threading.Lock()
        self.running = False
        
    def start(self):
        """Start the network hub server"""
        if sys.platform.startswith('win'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except:
                pass
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True
            
            print("=" * 60)
            print("🌐 NETWORK HUB STARTED")
            print("=" * 60)
            print(f"Host: {self.host}:{self.port}")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            print("\n🟢 Waiting for nodes to connect...\n")
            sys.stdout.flush()
            
            # Start accepting connections
            accept_thread = threading.Thread(target=self.accept_connections)
            accept_thread.daemon = True
            accept_thread.start()
            
            # Start hub command interface
            command_thread = threading.Thread(target=self.hub_command_interface)
            command_thread.daemon = True
            command_thread.start()
            
            # Keep the main thread alive
            while self.running:
                time.sleep(0.5)
                
        except Exception as e:
            print(f"❌ Error starting network hub: {e}")
            sys.stdout.flush()
            self.running = False
            
    def accept_connections(self):
        """Accept incoming node connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_socket.settimeout(1.0)
                
                # Start a new thread to handle this node
                handler_thread = threading.Thread(
                    target=self.handle_node,
                    args=(client_socket, address)
                )
                handler_thread.daemon = True
                handler_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Error accepting connection: {e}")
                    sys.stdout.flush()
                    
    def handle_node(self, client_socket, address):
        """Handle communication with a connected node"""
        node_id = None
        
        try:
            # Receive node registration data
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return
                
            node_info = json.loads(data)
            node_id = node_info['node_id']
            
            # Store node information
            with self.node_lock:
                self.connected_nodes[node_id] = {
                    'socket': client_socket,
                    'address': address,
                    'info': node_info,
                    'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'last_heartbeat': time.time()
                }
            
            # Display connection information
            self.display_new_connection(node_info, address)
            sys.stdout.flush()
            
            # Send acknowledgment
            response = {
                'status': 'connected',
                'message': 'Successfully connected to network hub',
                'node_id': node_id
            }
            client_socket.send(json.dumps(response).encode('utf-8'))
            
            # Keep connection alive and listen for messages
            while self.running:
                try:
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        break
                        
                    message = json.loads(data)
                    
                    if message.get('type') == 'heartbeat':
                        # Update last heartbeat
                        with self.node_lock:
                            if node_id in self.connected_nodes:
                                self.connected_nodes[node_id]['last_heartbeat'] = time.time()
                        
                        # Respond to heartbeat
                        response = json.dumps({'status': 'alive'}).encode('utf-8')
                        client_socket.send(response)
                        
                    elif message.get('type') == 'node_message':
                        # Route message to target node
                        self.route_node_message(message, node_id)
                        
                    elif message.get('type') == 'broadcast':
                        # Broadcast message to all nodes
                        self.broadcast_message(message, node_id)
                        
                except socket.timeout:
                    continue
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    break
                    
        except Exception as e:
            print(f"❌ Error handling node {node_id}: {e}")
        finally:
            # Clean up when node disconnects
            if node_id:
                with self.node_lock:
                    if node_id in self.connected_nodes:
                        del self.connected_nodes[node_id]
                print(f"\n🔴 Node Disconnected: {node_id}")
                print(f"🟢 Active nodes: {len(self.connected_nodes)}")
                print("-" * 50 + "\n")
                sys.stdout.flush()
                
            try:
                client_socket.close()
            except:
                pass
                
    def route_node_message(self, message, source_node_id):
        """Route a message from one node to another"""
        target_node_id = message.get('target_node')
        if target_node_id and target_node_id in self.connected_nodes:
            try:
                target_socket = self.connected_nodes[target_node_id]['socket']
                message['from_node'] = source_node_id
                target_socket.send(json.dumps(message).encode('utf-8'))
            except:
                # If target node is unreachable, notify sender
                self.send_error(source_node_id, f"Node {target_node_id} is not reachable")
                
    def broadcast_message(self, message, source_node_id):
        """Broadcast a message to all connected nodes"""
        message['from_node'] = source_node_id
        with self.node_lock:
            for node_id, node_data in self.connected_nodes.items():
                if node_id != source_node_id:  # Don't send to self
                    try:
                        node_data['socket'].send(json.dumps(message).encode('utf-8'))
                    except:
                        continue
                        
    def send_error(self, node_id, error_message):
        """Send error message to a specific node"""
        if node_id in self.connected_nodes:
            try:
                error_msg = {
                    'type': 'error',
                    'message': error_message
                }
                self.connected_nodes[node_id]['socket'].send(json.dumps(error_msg).encode('utf-8'))
            except:
                pass
                
    def display_new_connection(self, node_info, address):
        """Display information about newly connected node"""
        print("\n" + "=" * 60)
        print("🟢 NEW NODE CONNECTED")
        print("=" * 60)
        print(f"Node ID:     {node_info['node_id']}")
        print(f"Node Name:   {node_info['node_name']}")
        print(f"Node Type:   {node_info.get('node_type', 'N/A')}")
        print(f"IP Address:  {address[0]}:{address[1]}")
        print(f"Connected:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        print("Resources:")
        print(f"  • Storage:  {node_info['storage_capacity']} GB")
        print(f"  • CPU:      {node_info['cpu_cores']} cores") 
        print(f"  • Memory:   {node_info['memory']} GB")
        print("=" * 60)
        print(f"Total Active Nodes: {len(self.connected_nodes)}")
        print("=" * 60 + "\n")
        
    def hub_command_interface(self):
        """Hub command interface for monitoring"""
        while self.running:
            try:
                time.sleep(2)
                # Display active nodes periodically
                with self.node_lock:
                    active_count = len(self.connected_nodes)
                
                if active_count > 0:
                    print(f"\n📊 Network Status: {active_count} active nodes")
                    print("Type 'list' to see all nodes, 'quit' to shutdown hub")
                    
            except:
                break
                
    def list_nodes(self):
        """List all connected nodes"""
        with self.node_lock:
            if not self.connected_nodes:
                print("\n📭 No nodes connected")
                return
                
            print("\n" + "=" * 60)
            print("📋 CONNECTED NODES")
            print("=" * 60)
            for node_id, node_data in self.connected_nodes.items():
                info = node_data['info']
                print(f"Node ID: {node_id} | Name: {info['node_name']} | Type: {info.get('node_type', 'N/A')}")
                print(f"  Resources: {info['storage_capacity']}GB storage, {info['cpu_cores']} cores, {info['memory']}GB memory")
                print(f"  Connected: {node_data['connected_at']}")
                print("-" * 50)
            print(f"Total: {len(self.connected_nodes)} nodes")
            print("=" * 60 + "\n")
        
    def stop(self):
        """Stop the network hub"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        print("\n🛑 Network hub stopped")
        sys.stdout.flush()

if __name__ == "__main__":
    hub = NetworkHub(host='localhost', port=5555)
    try:
        hub.start()
    except KeyboardInterrupt:
        print("\nShutting down network hub...")
        hub.stop()