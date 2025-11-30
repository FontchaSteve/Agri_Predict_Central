import sys
import grpc
import getpass
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc
import subprocess
import os

def get_login_credentials():
    """Get login credentials from user input"""
    print("🔐 Login System")
    print("=" * 20)
    
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    
    return username, password

def get_otp_code():
    """Get OTP code from user"""
    print("\n" + "=" * 30)
    print("🔢 OTP VERIFICATION")
    print("=" * 30)
    otp_code = input("Enter the 6-digit OTP code sent to your email: ").strip()
    return otp_code

def run_login(login, password):
    """Execute the login request"""
    try:
        channel = grpc.insecure_channel('localhost:51234')
        stub = cloudsecurity_pb2_grpc.UserServiceStub(channel)
        
        print(f"⏳ Verifying credentials...")
        response = stub.login(cloudsecurity_pb2.Request(login=login, password=password), timeout=10)
        return response
        
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            return cloudsecurity_pb2.Response(result="❌ Login timeout: Server took too long to respond")
        else:
            return cloudsecurity_pb2.Response(result=f"❌ Connection error: {e.details()}")
    except Exception as e:
        return cloudsecurity_pb2.Response(result=f"❌ Error: {e}")

def run_otp_verification(username, otp_code):
    """Verify OTP code"""
    try:
        channel = grpc.insecure_channel('localhost:51234')
        stub = cloudsecurity_pb2_grpc.UserServiceStub(channel)
        
        print(f"⏳ Verifying OTP code...")
        response = stub.verifyOTP(cloudsecurity_pb2.OTPRequest(username=username, otp_code=otp_code), timeout=10)
        return response
        
    except Exception as e:
        return cloudsecurity_pb2.Response(result=f"❌ OTP verification error: {e}")

def run_registration():
    """Run the user registration directly"""
    try:
        print("\n🚀 Launching Registration System...")
        print("=" * 40)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        register_script = os.path.join(current_dir, "register_user.py")
        
        result = subprocess.run([sys.executable, register_script], 
                              capture_output=False,
                              text=True)
        
        if result.returncode == 0:
            print("\n✅ Registration process completed")
        else:
            print(f"\n❌ Registration process failed with code: {result.returncode}")
            
    except Exception as e:
        print(f"❌ Error launching registration: {e}")

def main():
    # If no arguments provided, use interactive mode
    if len(sys.argv) == 1:
        print("Welcome to Cloud Security System!")
        print("Choose an option:")
        print("1. Login")
        print("2. Register new user")
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            # Interactive login with OTP
            username, password = get_login_credentials()
            
            # Step 1: Initial login
            login_response = run_login(username, password)
            print(f"🔑 {login_response.result}")
            
            # Step 2: If OTP is required, verify it
            if "OTP" in login_response.result and "enter" in login_response.result.lower():
                otp_code = get_otp_code()
                otp_response = run_otp_verification(username, otp_code)
                print(f"✅ {otp_response.result}")
            
        elif choice == "2":
            # Run registration
            run_registration()
            
        else:
            print("❌ Invalid choice. Please run again.")
    
    # Command line mode for login
    elif len(sys.argv) == 4:
        request = sys.argv[1]
        login = sys.argv[2]
        password = sys.argv[3]
        
        if request == "login":
            response = run_login(login, password)
            print(f"Result: {response.result}")
        else:
            print("Invalid request. Use 'login'")
            
    else:
        print("Usage:")
        print("  Interactive mode: python client.py")
        print("  Command line: python client.py login <username> <password>")
        print("  Register: python register_user.py")

if __name__ == '__main__':
    main()