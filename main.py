import time
from storage_virtual_network import StorageVirtualNetwork
from storage_virtual_node import StorageVirtualNode

def print_separator():
    print("\n" + "="*70 + "\n")

def display_node_stats(node: StorageVirtualNode):
    """Display statistics for a single node"""
    storage = node.get_storage_utilization()
    network = node.get_network_utilization()
    perf = node.get_performance_metrics()
    
    print(f"Node: {node.node_id}")
    print(f"  Storage: {storage['used_bytes'] / (1024**2):.2f} MB / {storage['total_bytes'] / (1024**2):.2f} MB ({storage['utilization_percent']:.2f}%)")
    print(f"  Files Stored: {storage['files_stored']}")
    print(f"  Active Transfers: {storage['active_transfers']}")
    print(f"  Network Usage: {network['utilization_percent']:.2f}%")
    print(f"  Total Requests Processed: {perf['total_requests_processed']}")
    print(f"  Total Data Transferred: {perf['total_data_transferred_bytes'] / (1024**2):.2f} MB")

def display_network_stats(network: StorageVirtualNetwork):
    """Display overall network statistics"""
    stats = network.get_network_stats()
    
    print("NETWORK STATISTICS:")
    print(f"  Total Nodes: {stats['total_nodes']}")
    print(f"  Storage Usage: {stats['used_storage_bytes'] / (1024**3):.2f} GB / {stats['total_storage_bytes'] / (1024**3):.2f} GB ({stats['storage_utilization']:.2f}%)")
    print(f"  Bandwidth Usage: {stats['bandwidth_utilization']:.2f}%")
    print(f"  Active Transfers: {stats['active_transfers']}")

def simulate_file_transfers():
    """Main simulation function"""
    print("="*70)
    print("STORAGE VIRTUAL NETWORK SIMULATOR")
    print("="*70)
    
    # Create network
    network = StorageVirtualNetwork()
    
    # Create nodes with different capacities
    print("\n[1] Creating network nodes...")
    node1 = StorageVirtualNode("Node-A", cpu_capacity=4, memory_capacity=8, storage_capacity=50, bandwidth=100)
    node2 = StorageVirtualNode("Node-B", cpu_capacity=8, memory_capacity=16, storage_capacity=100, bandwidth=200)
    node3 = StorageVirtualNode("Node-C", cpu_capacity=4, memory_capacity=8, storage_capacity=75, bandwidth=150)
    
    network.add_node(node1)
    network.add_node(node2)
    network.add_node(node3)
    
    print(f"  ✓ Created {node1.node_id}: {node1.total_storage / (1024**3):.0f} GB storage, {node1.bandwidth / 1000000:.0f} Mbps")
    print(f"  ✓ Created {node2.node_id}: {node2.total_storage / (1024**3):.0f} GB storage, {node2.bandwidth / 1000000:.0f} Mbps")
    print(f"  ✓ Created {node3.node_id}: {node3.total_storage / (1024**3):.0f} GB storage, {node3.bandwidth / 1000000:.0f} Mbps")
    
    # Connect nodes
    print("\n[2] Establishing network connections...")
    network.connect_nodes("Node-A", "Node-B", 100)
    network.connect_nodes("Node-B", "Node-C", 150)
    network.connect_nodes("Node-A", "Node-C", 80)
    print("  ✓ Node-A ←→ Node-B (100 Mbps)")
    print("  ✓ Node-B ←→ Node-C (150 Mbps)")
    print("  ✓ Node-A ←→ Node-C (80 Mbps)")
    
    print_separator()
    
    # Simulate file transfers
    print("[3] Starting file transfer simulations...")
    
    # Transfer 1: Node-A to Node-B
    print("\n► Transfer 1: Node-A → Node-B (50 MB file)")
    file_size_1 = 50 * 1024 * 1024  # 50 MB
    transfer1 = network.initiate_file_transfer("Node-A", "Node-B", "dataset_1.csv", file_size_1)
    
    if transfer1:
        print(f"  ✓ Transfer initiated: {transfer1.file_name} ({len(transfer1.chunks)} chunks)")
        
        # Process transfer in steps
        while True:
            chunks_done, completed = network.process_file_transfer("Node-A", "Node-B", transfer1.file_id, chunks_per_step=2)
            if completed:
                print(f"  ✓ Transfer completed!")
                break
            elif chunks_done > 0:
                completed_chunks = sum(1 for c in transfer1.chunks if c.status.name == "COMPLETED")
                print(f"  → Progress: {completed_chunks}/{len(transfer1.chunks)} chunks transferred")
            time.sleep(0.1)  # Small delay for readability
    
    print_separator()
    
    # Transfer 2: Node-A to Node-C
    print("► Transfer 2: Node-A → Node-C (30 MB file)")
    file_size_2 = 30 * 1024 * 1024  # 30 MB
    transfer2 = network.initiate_file_transfer("Node-A", "Node-C", "model_weights.pkl", file_size_2)
    
    if transfer2:
        print(f"  ✓ Transfer initiated: {transfer2.file_name} ({len(transfer2.chunks)} chunks)")
        
        while True:
            chunks_done, completed = network.process_file_transfer("Node-A", "Node-C", transfer2.file_id, chunks_per_step=3)
            if completed:
                print(f"  ✓ Transfer completed!")
                break
            elif chunks_done > 0:
                completed_chunks = sum(1 for c in transfer2.chunks if c.status.name == "COMPLETED")
                print(f"  → Progress: {completed_chunks}/{len(transfer2.chunks)} chunks transferred")
            time.sleep(0.1)
    
    print_separator()
    
    # Transfer 3: Node-B to Node-C
    print("► Transfer 3: Node-B → Node-C (80 MB file)")
    file_size_3 = 80 * 1024 * 1024  # 80 MB
    transfer3 = network.initiate_file_transfer("Node-B", "Node-C", "training_data.zip", file_size_3)
    
    if transfer3:
        print(f"  ✓ Transfer initiated: {transfer3.file_name} ({len(transfer3.chunks)} chunks)")
        
        while True:
            chunks_done, completed = network.process_file_transfer("Node-B", "Node-C", transfer3.file_id, chunks_per_step=2)
            if completed:
                print(f"  ✓ Transfer completed!")
                break
            elif chunks_done > 0:
                completed_chunks = sum(1 for c in transfer3.chunks if c.status.name == "COMPLETED")
                print(f"  → Progress: {completed_chunks}/{len(transfer3.chunks)} chunks transferred")
            time.sleep(0.1)
    
    print_separator()
    
    # Display final statistics
    print("[4] FINAL NETWORK STATUS")
    print_separator()
    
    display_network_stats(network)
    
    print_separator()
    
    print("INDIVIDUAL NODE STATISTICS:")
    print()
    display_node_stats(node1)
    print()
    display_node_stats(node2)
    print()
    display_node_stats(node3)
    
    print_separator()
    print("✓ Simulation completed successfully!")
    print("="*70)

if __name__ == "__main__":
    simulate_file_transfers()