import bcrypt
import grpc
from concurrent import futures
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc
from firebase_config import db
from utils import send_otp, generate_otp
import datetime

# Store OTP codes temporarily
otp_storage = {}

class UserServiceSkeleton(cloudsecurity_pb2_grpc.UserServiceServicer):
    def login(self, request, context) -> cloudsecurity_pb2.Response:
        print(f'🔐 Login attempt for user: {request.login}')
        result = self.checkId(request.login, request.password)
        return cloudsecurity_pb2.Response(result=result)

    def verifyOTP(self, request, context) -> cloudsecurity_pb2.Response:
        print(f'🔢 OTP verification for user: {request.username}')
        result = self.verify_otp_code(request.username, request.otp_code)
        return cloudsecurity_pb2.Response(result=result)

    def checkId(self, login, pwd) -> str:
        try:
            # Check Firebase connection first
            if db is None:
                return "❌ Login failed: Database connection error. Please try again later."
            
            print(f"🔍 Querying Firebase for user: {login}")
            
            # Query Firebase for user
            users_ref = db.collection('users')
            query = users_ref.where('username', '==', login).limit(1)
            docs = list(query.get())
            
            print(f"📊 Found {len(docs)} user(s) with username: {login}")
            
            if not docs:
                return "❌ Login failed: User not found"
            
            # Get user data from Firebase
            user_data = docs[0].to_dict()
            stored_password = user_data.get('password')
            user_email = user_data.get('email')
            
            print(f"📧 User email: {user_email}")
            print("🔐 Verifying password...")
            
            # Verify password
            if bcrypt.checkpw(pwd.encode('utf-8'), stored_password.encode('utf-8')):
                # Generate and send OTP
                otp_code = generate_otp()
                otp_storage[login] = {
                    'code': otp_code,
                    'email': user_email,
                    'timestamp': datetime.datetime.now(),
                    'attempts': 0
                }
                
                print(f"📨 Sending OTP {otp_code} to {user_email}...")
                otp_result = send_otp(user_email, otp_code)
                
                return f"✅ Password correct! {otp_result} Please check your email and enter the OTP code."
            else:
                return "❌ Login failed: Invalid password"
                
        except Exception as e:
            error_msg = f"❌ Login error: {e}"
            print(error_msg)
            return error_msg

    def verify_otp_code(self, username, otp_code) -> str:
        try:
            # Check if OTP exists for user
            if username not in otp_storage:
                return "❌ OTP verification failed: No OTP request found for this user. Please login again."
            
            otp_data = otp_storage[username]
            
            # Check if OTP is expired (5 minutes)
            time_diff = datetime.datetime.now() - otp_data['timestamp']
            if time_diff.total_seconds() > 300:  # 5 minutes
                del otp_storage[username]
                return "❌ OTP verification failed: OTP code has expired. Please login again."
            
            # Check attempts
            if otp_data['attempts'] >= 3:
                del otp_storage[username]
                return "❌ OTP verification failed: Too many attempts. Please login again."
            
            # Verify OTP code
            if otp_data['code'] == otp_code:
                # OTP is correct - login successful
                del otp_storage[username]
                return f"🎉 Login successful! Welcome {username}"
            else:
                # Wrong OTP code
                otp_storage[username]['attempts'] += 1
                remaining_attempts = 3 - otp_storage[username]['attempts']
                return f"❌ Invalid OTP code. {remaining_attempts} attempts remaining."
                
        except Exception as e:
            return f"❌ OTP verification error: {e}"

def run():
    # Check Firebase connection before starting server
    if db is None:
        print("❌ Cannot start server: Firebase connection failed")
        return
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cloudsecurity_pb2_grpc.add_UserServiceServicer_to_server(UserServiceSkeleton(), server)
    server.add_insecure_port('[::]:51234')
    print('✅ Starting Server on port 51234...')
    server.start()
    print('✅ Server started successfully! Waiting for connections...')
    server.wait_for_termination()

if __name__ == '__main__':
    run()