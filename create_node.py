import socket
import json
import threading
import time
import uuid
import sys
from datetime import datetime

class VirtualNode:
    def __init__(self, node_name, storage_capacity, cpu_cores, memory, node_type,
                 hub_host='127.0.0.1', hub_port=5555):

        self.node_id = str(uuid.uuid4())[:8]
        self.node_name = node_name
        self.storage_capacity = storage_capacity
        self.cpu_cores = cpu_cores
        self.memory = memory
        self.node_type = node_type
        self.hub_host = hub_host
        self.hub_port = hub_port
        self.socket = None

    def connect_to_network(self):
        try:
            print(f"🔌 Connecting to hub at {self.hub_host}:{self.hub_port} ...")

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.hub_host, self.hub_port))

            node_info = {
                "node_id": self.node_id,
                "node_name": self.node_name,
                "storage_capacity": self.storage_capacity,
                "cpu_cores": self.cpu_cores,
                "memory": self.memory,
                "node_type": self.node_type,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            self.socket.send(json.dumps(node_info).encode("utf-8"))
            response = json.loads(self.socket.recv(4096).decode("utf-8"))

            if response.get("status") == "connected":
                print("🟢 Node successfully connected to hub!")
            else:
                print("❌ Hub returned error:", response)

        except Exception as e:
            print("Connection failed:", e)

def get_user_input():
    print("\n=== CREATE NEW NODE ===")
    name = input("Node name: ")
    storage = int(input("Storage (GB): "))
    cpu = int(input("CPU cores: "))
    mem = int(input("Memory (GB): "))

    print("\nNode types:\n1. Storage\n2. Compute\n3. Gateway\n4. Hybrid")
    t = int(input("Select type (1-4): "))
    node_type = ["Storage", "Compute", "Gateway", "Hybrid"][t-1]

    return name, storage, cpu, mem, node_type

if __name__ == "__main__":
    n, s, c, m, t = get_user_input()
    node = VirtualNode(n, s, c, m, t)
    node.connect_to_network()
