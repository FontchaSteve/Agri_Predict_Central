import socket
import threading
import json
import time
import sys
from datetime import datetime

class NetworkHub:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host  # FORCE IPv4
        self.port = port
        self.server_socket = None
        self.connected_nodes = {}
        self.node_lock = threading.Lock()
        self.running = False

    def recv_json(self, client_socket):
        buffer = ""
        while True:
            try:
                chunk = client_socket.recv(4096).decode("utf-8")
                if not chunk:
                    return None
                buffer += chunk
                try:
                    return json.loads(buffer)
                except json.JSONDecodeError:
                    continue
            except:
                return None

    def start(self):
        """Start the network hub server"""
        if sys.platform.startswith('win'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except:
                pass

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

        print("=" * 50)
        print("🌐 NETWORK HUB STARTED")
        print("=" * 50)
        print(f"Host: {self.host}:{self.port}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        print("\nWaiting for nodes to connect...\n")

        threading.Thread(target=self.accept_connections, daemon=True).start()

        while self.running:
            time.sleep(1)

    def accept_connections(self):
        while self.running:
            try:
                print("🔔 Waiting for incoming connection...")
                client_socket, address = self.server_socket.accept()
                print(f"🔗 Connection attempt received from {address}")

                threading.Thread(
                    target=self.handle_node,
                    args=(client_socket, address),
                    daemon=True
                ).start()

            except Exception as e:
                print("Hub accept error:", e)

    def handle_node(self, client_socket, address):
        node_id = None

        try:
            node_info = self.recv_json(client_socket)
            if not node_info:
                print(f"❌ Invalid registration from {address}")
                return

            node_id = node_info["node_id"]

            with self.node_lock:
                self.connected_nodes[node_id] = {
                    "socket": client_socket,
                    "address": address,
                    "info": node_info,
                    "connected_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            self.display_new_node(node_info, address)

            client_socket.send(json.dumps({
                "status": "connected",
                "message": "Node successfully registered"
            }).encode("utf-8"))

            while True:
                msg = self.recv_json(client_socket)
                if not msg:
                    break

        finally:
            if node_id and node_id in self.connected_nodes:
                del self.connected_nodes[node_id]
                print(f"🔴 Node disconnected: {node_id}")

            try:
                client_socket.close()
            except:
                pass

    def display_new_node(self, info, addr):
        print("\n" + "=" * 50)
        print("🟢 NEW NODE CONNECTED")
        print("=" * 50)
        print(f"Node ID:    {info['node_id']}")
        print(f"Node Name:  {info['node_name']}")
        print(f"Node Type:  {info['node_type']}")
        print(f"IP Address: {addr[0]}:{addr[1]}")
        print(f"Storage:    {info['storage_capacity']} GB")
        print(f"CPU:        {info['cpu_cores']} cores")
        print(f"Memory:     {info['memory']} GB")
        print("=" * 50)
        print(f"Total Active Nodes: {len(self.connected_nodes)}")
        print("=" * 50 + "\n")


if __name__ == "__main__":
    hub = NetworkHub(host="127.0.0.1", port=5555)
    try:
        hub.start()
    except KeyboardInterrupt:
        print("\nStopping hub...")
