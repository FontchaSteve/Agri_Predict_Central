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
        # Set UTF-8 encoding for Windows
        if sys.platform.startswith('win'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except:
                pass
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)  # Add timeout to allow checking running flag
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True
            
            print("=" * 60)
            print("VIRTUAL NETWORK HUB STARTED")
            print("=" * 60)
            print(f"Listening on: {self.host}:{self.port}")
            print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            print("\nWaiting for nodes to connect...\n")
            sys.stdout.flush()  # Force output to display immediately
            
            # Start accepting connections
            accept_thread = threading.Thread(target=self.accept_connections)
            accept_thread.daemon = True
            accept_thread.start()
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            print(f"[ERROR] Error starting network hub: {e}")
            sys.stdout.flush()
            self.running = False
            
    def accept_connections(self):
        """Accept incoming node connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_socket.settimeout(5.0)  # Set timeout for client socket
                
                # Start a new thread to handle this node
                handler_thread = threading.Thread(
                    target=self.handle_node,
                    args=(client_socket, address)
                )
                handler_thread.daemon = True
                handler_thread.start()
                
            except socket.timeout:
                # This is expected, continue loop to check running flag
                continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] Error accepting connection: {e}")
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
                    'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            # Display connection information immediately
            self.display_new_connection(node_info, address)
            sys.stdout.flush()  # Force immediate display
            
            # Send acknowledgment
            response = {
                'status': 'connected',
                'message': 'Successfully connected to network hub'
            }
            client_socket.send(json.dumps(response).encode('utf-8'))
            
            # Keep connection alive and listen for messages
            while self.running:
                try:
                    client_socket.settimeout(1.0)
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        break
                        
                    message = json.loads(data)
                    if message.get('type') == 'heartbeat':
                        # Respond to heartbeat
                        response = json.dumps({'status': 'alive'}).encode('utf-8')
                        client_socket.send(response)
                    elif message.get('type') == 'status_update':
                        # Update node status
                        with self.node_lock:
                            if node_id in self.connected_nodes:
                                self.connected_nodes[node_id]['info'].update(message.get('data', {}))
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    break
                    
        except Exception as e:
            print(f"[ERROR] Error handling node: {e}")
            sys.stdout.flush()
        finally:
            # Clean up when node disconnects
            if node_id:
                with self.node_lock:
                    if node_id in self.connected_nodes:
                        del self.connected_nodes[node_id]
                print(f"\n[DISCONNECT] Node Disconnected: {node_id}")
                print(f"Active nodes: {len(self.connected_nodes)}")
                print("-" * 60 + "\n")
                sys.stdout.flush()
                
            try:
                client_socket.close()
            except:
                pass
                
    def display_new_connection(self, node_info, address):
        """Display information about newly connected node"""
        print("\n" + "=" * 60)
        print("[NEW CONNECTION] NODE CONNECTED")
        print("=" * 60)
        print(f"Node ID:        {node_info['node_id']}")
        print(f"Node Name:      {node_info['node_name']}")
        print(f"IP Address:     {address[0]}:{address[1]}")
        print(f"Connected At:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        print("Node Statistics:")
        print(f"  - Storage:    {node_info['storage_capacity']} GB")
        print(f"  - CPU Cores:  {node_info['cpu_cores']}")
        print(f"  - Memory:     {node_info['memory']} GB")
        print(f"  - Node Type:  {node_info['node_type']}")
        print("=" * 60)
        print(f"Total Active Nodes: {len(self.connected_nodes)}")
        print("=" * 60 + "\n")
        
    def stop(self):
        """Stop the network hub"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        print("\n[SHUTDOWN] Network hub stopped")
        sys.stdout.flush()

if __name__ == "__main__":
    hub = NetworkHub(host='localhost', port=5555)
    try:
        hub.start()
    except KeyboardInterrupt:
        print("\n\nShutting down network hub...")
        hub.stop()