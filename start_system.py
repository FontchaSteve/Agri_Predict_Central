#!/usr/bin/env python3
"""
Main System Launcher - Starts the complete distributed storage system
"""
import os
import sys
import time
import threading
import subprocess
import signal
import atexit
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configuration
from config import Config

# Global variables to track processes
processes = []
is_shutting_down = False


def setup_directories():
    """Create all necessary directories"""
    print("📁 Setting up directories...")
    
    # Create main directories
    Config.init_directories()
    
    # Create individual node directories
    for i in range(1, Config.DEFAULT_NODE_COUNT + 1):
        node_dir = current_dir / "data" / "node_storage" / f"node{i}"
        node_dir.mkdir(parents=True, exist_ok=True)
    
    # Create uploads directory
    upload_dir = current_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    print("✅ Directories created successfully")


def start_controller():
    """Start the network controller"""
    print("\n🌐 Starting Network Controller...")
    
    controller_script = current_dir / "network_controller.py"
    if not controller_script.exists():
        print(f"❌ Controller script not found: {controller_script}")
        return None
    
    try:
        proc = subprocess.Popen(
            [sys.executable, str(controller_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Give controller time to start
        time.sleep(2)
        
        if proc.poll() is None:
            print(f"✅ Controller started (PID: {proc.pid})")
            # Start thread to read output
            threading.Thread(
                target=read_process_output,
                args=(proc, "CONTROLLER"),
                daemon=True
            ).start()
            return proc
        else:
            print("❌ Controller failed to start")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start controller: {e}")
        return None


def start_storage_nodes():
    """Start multiple storage nodes"""
    print(f"\n🖥️ Starting {Config.DEFAULT_NODE_COUNT} Storage Nodes...")
    
    node_script = current_dir / "storage_node.py"
    if not node_script.exists():
        print(f"❌ Node script not found: {node_script}")
        return []
    
    node_processes = []
    
    for i in range(1, Config.DEFAULT_NODE_COUNT + 1):
        node_id = f"node{i}"
        print(f"  Starting {node_id}...")
        
        try:
            proc = subprocess.Popen(
                [sys.executable, str(node_script), node_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Give node time to start
            time.sleep(0.5)
            
            if proc.poll() is None:
                print(f"    ✅ {node_id} started (PID: {proc.pid})")
                # Start thread to read output
                threading.Thread(
                    target=read_process_output,
                    args=(proc, node_id),
                    daemon=True
                ).start()
                node_processes.append(proc)
            else:
                print(f"    ❌ {node_id} failed to start")
                
        except Exception as e:
            print(f"    ❌ Failed to start {node_id}: {e}")
    
    return node_processes


def start_web_interface():
    """Start the Flask web interface"""
    print("\n🌍 Starting Web Interface...")
    
    app_script = current_dir / "app.py"
    if not app_script.exists():
        print(f"❌ App script not found: {app_script}")
        return None
    
    try:
        # Set environment variable to run in production mode
        env = os.environ.copy()
        env['FLASK_ENV'] = 'production'
        
        proc = subprocess.Popen(
            [sys.executable, str(app_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        
        # Give web interface time to start
        time.sleep(3)
        
        if proc.poll() is None:
            print(f"✅ Web interface started (PID: {proc.pid})")
            print(f"   🌐 Open your browser at: http://localhost:5000")
            # Start thread to read output
            threading.Thread(
                target=read_process_output,
                args=(proc, "WEB"),
                daemon=True
            ).start()
            return proc
        else:
            print("❌ Web interface failed to start")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start web interface: {e}")
        return None


def read_process_output(process, name):
    """Read and print output from a process"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line and not is_shutting_down:
                print(f"[{name}] {line.strip()}")
    except:
        pass


def check_system_health():
    """Check if all components are running"""
    print("\n🔍 Checking system health...")
    
    healthy = True
    
    # Check controller
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', Config.CONTROLLER_PORT))
        if result == 0:
            print("✅ Controller: Running")
        else:
            print("❌ Controller: Not responding")
            healthy = False
        sock.close()
    except:
        print("❌ Controller: Connection failed")
        healthy = False
    
    # Check web interface
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 5000))
        if result == 0:
            print("✅ Web Interface: Running")
        else:
            print("❌ Web Interface: Not responding")
            healthy = False
        sock.close()
    except:
        print("❌ Web Interface: Connection failed")
        healthy = False
    
    return healthy


def display_system_info():
    """Display system information"""
    print("\n" + "="*70)
    print("🌟 DISTRIBUTED CLOUD STORAGE SYSTEM")
    print("="*70)
    
    total_storage = Config.DEFAULT_NODE_COUNT * Config.NODE_STORAGE_GB
    print(f"\n📊 SYSTEM CONFIGURATION:")
    print(f"   Storage Nodes:     {Config.DEFAULT_NODE_COUNT}")
    print(f"   Total Capacity:    {total_storage} GB")
    print(f"   Replication:       {Config.REPLICATION_FACTOR} copies per file")
    print(f"   Node Resources:    {Config.NODE_CPU_CORES} CPU, {Config.NODE_MEMORY_GB}GB RAM")
    print(f"   Bandwidth:         {Config.NODE_BANDWIDTH_MBPS} Mbps per node")
    
    print(f"\n🌐 NETWORK PORTS:")
    print(f"   Web Interface:     http://localhost:5000")
    print(f"   Controller:        localhost:{Config.CONTROLLER_PORT}")
    print(f"   Node Ports:        {Config.NODE_PORT_RANGE[0]}-{Config.NODE_PORT_RANGE[1]}")
    
    print(f"\n📁 STORAGE DIRECTORIES:")
    print(f"   Uploads:           {current_dir}/uploads")
    print(f"   Node Storage:      {current_dir}/data/node_storage/")
    
    print("\n" + "="*70)


def shutdown_handler(signum, frame):
    """Handle shutdown signals"""
    global is_shutting_down
    
    if is_shutting_down:
        return
    
    is_shutting_down = True
    print("\n\n🛑 Shutdown signal received. Stopping all components...")
    stop_all_processes()


def stop_all_processes():
    """Stop all running processes"""
    global processes
    
    print("\n⏹️  Stopping system components...")
    
    # Stop processes in reverse order
    for proc in reversed(processes):
        if proc and proc.poll() is None:
            try:
                print(f"   Stopping PID {proc.pid}...")
                proc.terminate()
                
                # Wait for process to terminate
                for _ in range(10):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.5)
                
                # Force kill if still running
                if proc.poll() is None:
                    proc.kill()
                    print(f"   Force killed PID {proc.pid}")
                    
            except Exception as e:
                print(f"   Error stopping process: {e}")
    
    print("\n✅ All components stopped")
    print("👋 Goodbye!")
    sys.exit(0)


def cleanup():
    """Cleanup function registered with atexit"""
    if not is_shutting_down:
        stop_all_processes()


def main():
    """Main entry point"""
    global processes
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Register cleanup function
    atexit.register(cleanup)
    
    # Display system information
    display_system_info()
    
    # Setup directories
    setup_directories()
    
    # Start components
    controller = start_controller()
    if controller:
        processes.append(controller)
    
    nodes = start_storage_nodes()
    processes.extend(nodes)
    
    web_interface = start_web_interface()
    if web_interface:
        processes.append(web_interface)
    
    # Check system health
    time.sleep(2)
    healthy = check_system_health()
    
    if healthy:
        print("\n" + "="*70)
        print("✅ SYSTEM STARTED SUCCESSFULLY!")
        print("="*70)
        print("\n📢 INSTRUCTIONS:")
        print("   1. Open your browser to http://localhost:5000")
        print("   2. Login with any username")
        print("   3. Start uploading files!")
        print("\n🔧 MANAGEMENT:")
        print("   - Press Ctrl+C to stop all components")
        print("   - Check the console for system logs")
        print("   - Files are stored in: data/node_storage/")
        print("="*70)
    else:
        print("\n⚠️  Some components failed to start. Check the logs above.")
        print("   Trying to continue anyway...")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_handler(None, None)


def quick_start():
    """Quick start with minimal configuration"""
    print("🚀 Starting Distributed Cloud Storage System...")
    
    # Setup directories
    setup_directories()
    
    # Import and start components directly
    try:
        # Start controller in thread
        from network_controller import NetworkController
        controller = NetworkController()
        
        controller_thread = threading.Thread(
            target=controller.start,
            daemon=True
        )
        controller_thread.start()
        time.sleep(2)
        
        # Start nodes
        node_threads = []
        for i in range(1, Config.DEFAULT_NODE_COUNT + 1):
            from storage_node import StorageNode
            node = StorageNode(f"node{i}")
            
            thread = threading.Thread(
                target=node.start,
                daemon=True
            )
            thread.start()
            node_threads.append(thread)
            time.sleep(0.5)
        
        # Start web interface
        from app import start_web_server
        web_thread = threading.Thread(
            target=start_web_server,
            daemon=True
        )
        web_thread.start()
        time.sleep(3)
        
        print(f"\n✅ System started!")
        print(f"🌐 Web Interface: http://localhost:5000")
        print(f"📁 Storage: {Config.DEFAULT_NODE_COUNT * Config.NODE_STORAGE_GB} GB total")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        quick_start()
    else:
        main()