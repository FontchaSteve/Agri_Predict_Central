import bcrypt
import grpc
from concurrent import futures
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc
from firebase_config import db
import datetime

class UserServiceSkeleton(cloudsecurity_pb2_grpc.UserServiceServicer):
    def login(self, request, context) -> cloudsecurity_pb2.Response:
        print(f'🚨 NEW LOGIN REQUEST RECEIVED!')
        print(f'   👤 Username: {request.login}')
        print(f'   🔐 Password: {request.password}')
        print(f'   🕒 Time: {datetime.datetime.now()}')
        print(f'   📍 Client: {context.peer()}')
        
        result = self.checkId(request.login, request.password)
        print(f'📤 SENDING RESPONSE: {result}')
        print('=' * 50)
        return cloudsecurity_pb2.Response(result=result)

    def checkId(self, login, pwd) -> str:
        try:
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
                return f"✅ Login successful! Welcome {login}"
            else:
                return "❌ Login failed: Invalid password"
                
        except Exception as e:
            error_msg = f"❌ Login error: {e}"
            print(error_msg)
            return error_msg

def run():
    print('🔥 STARTING FRESH SERVER INSTANCE')
    print(f'🕒 Server start time: {datetime.datetime.now()}')
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cloudsecurity_pb2_grpc.add_UserServiceServicer_to_server(UserServiceSkeleton(), server)
    server.add_insecure_port('[::]:51234')
    print('✅ Starting Server on port 51234...')
    server.start()
    print('✅ Server started successfully! Waiting for connections...')
    print('💡 Test with: python client.py')
    server.wait_for_termination()

if __name__ == '__main__':
    run()