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

def get_user_input():
    """Get simulation parameters from user"""
    print("="*70)
    print("STORAGE VIRTUAL NETWORK SIMULATOR - INTERACTIVE MODE")
    print("="*70)
    
    # Get file size
    while True:
        try:
            file_size_mb = int(input("\nEnter file size (in MB, 1-500): "))
            if 1 <= file_size_mb <= 500:
                break
            print("  ⚠ Please enter a value between 1 and 500 MB")
        except ValueError:
            print("  ⚠ Please enter a valid number")
    
    # Get bandwidth
    while True:
        try:
            bandwidth = int(input("Enter bandwidth (in Mbps, 10-1000): "))
            if 10 <= bandwidth <= 1000:
                break
            print("  ⚠ Please enter a value between 10 and 1000 Mbps")
        except ValueError:
            print("  ⚠ Please enter a valid number")
    
    # Get number of transfers
    while True:
        try:
            num_transfers = int(input("Enter number of file transfers (1-5): "))
            if 1 <= num_transfers <= 5:
                break
            print("  ⚠ Please enter a value between 1 and 5")
        except ValueError:
            print("  ⚠ Please enter a valid number")
    
    return file_size_mb, bandwidth, num_transfers

def simulate_file_transfers():
    """Main simulation function"""
    
    # Get user input
    file_size_mb, bandwidth, num_transfers = get_user_input()
    file_size_bytes = file_size_mb * 1024 * 1024
    
    print_separator()
    
    # Create network
    print("[1] Creating network nodes...")
    network = StorageVirtualNetwork()
    
    # Create nodes with user-specified bandwidth
    node1 = StorageVirtualNode("Node-A", cpu_capacity=4, memory_capacity=8, 
                                storage_capacity=500, bandwidth=bandwidth)
    node2 = StorageVirtualNode("Node-B", cpu_capacity=8, memory_capacity=16, 
                                storage_capacity=500, bandwidth=bandwidth)
    node3 = StorageVirtualNode("Node-C", cpu_capacity=4, memory_capacity=8, 
                                storage_capacity=500, bandwidth=bandwidth)
    
    network.add_node(node1)
    network.add_node(node2)
    network.add_node(node3)
    
    print(f"  ✓ Created {node1.node_id}: {bandwidth} Mbps bandwidth")
    print(f"  ✓ Created {node2.node_id}: {bandwidth} Mbps bandwidth")
    print(f"  ✓ Created {node3.node_id}: {bandwidth} Mbps bandwidth")
    
    # Connect nodes with user-specified bandwidth
    print("\n[2] Establishing network connections...")
    network.connect_nodes("Node-A", "Node-B", bandwidth)
    network.connect_nodes("Node-B", "Node-C", bandwidth)
    network.connect_nodes("Node-A", "Node-C", bandwidth)
    print(f"  ✓ All nodes connected with {bandwidth} Mbps links")
    
    print_separator()
    
    # Define transfer routes
    transfer_routes = [
        ("Node-A", "Node-B", "dataset_1.csv"),
        ("Node-A", "Node-C", "model_weights.pkl"),
        ("Node-B", "Node-C", "training_data.zip"),
        ("Node-C", "Node-A", "results.json"),
        ("Node-B", "Node-A", "logs.txt")
    ]
    
    # Perform transfers
    print(f"[3] Starting {num_transfers} file transfer(s)...\n")
    
    for i in range(num_transfers):
        source, target, filename = transfer_routes[i]
        
        print(f"► Transfer {i+1}: {source} → {target}")
        print(f"  File: {filename} ({file_size_mb} MB)")
        
        # Start timing
        start_time = time.time()
        
        # Initiate transfer
        transfer = network.initiate_file_transfer(source, target, filename, file_size_bytes)
        
        if transfer:
            total_chunks = len(transfer.chunks)
            print(f"  Total chunks: {total_chunks}")
            
            # Process transfer (transfer all chunks at once for speed)
            while True:
                chunks_done, completed = network.process_file_transfer(
                    source, target, transfer.file_id, chunks_per_step=total_chunks
                )
                if completed:
                    break
            
            # Calculate transfer time
            end_time = time.time()
            transfer_time = end_time - start_time
            
            # Calculate theoretical transfer time
            file_size_bits = file_size_bytes * 8
            bandwidth_bps = bandwidth * 1_000_000
            theoretical_time = file_size_bits / bandwidth_bps
            
            print(f"  ✓ Transfer completed!")
            print(f"  ⏱  Actual time: {transfer_time:.3f} seconds")
            print(f"  📊 Theoretical time: {theoretical_time:.3f} seconds")
            
            # Calculate throughput (avoid division by zero)
            if transfer_time > 0:
                throughput_mbps = (file_size_mb / transfer_time)
                print(f"  📈 Effective throughput: {throughput_mbps:.2f} MB/s")
            else:
                print(f"  📈 Effective throughput: Instant (< 0.001s)")
            
        else:
            print(f"  ✗ Transfer failed (insufficient storage or bandwidth)")
        
        print()
    
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