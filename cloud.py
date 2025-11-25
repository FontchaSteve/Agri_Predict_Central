import bcrypt
import grpc
from concurrent import futures
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc
from utils import send_otp
from firebase_config import db  # Import Firebase

class UserServiceSkeleton(cloudsecurity_pb2_grpc.UserServiceServicer):
    def login(self, request, context) -> cloudsecurity_pb2.Response:
        print(f'new incoming request ... \nrequest: {request}')
        result = self.checkId(request.login, request.password)
        return cloudsecurity_pb2.Response(result=result)

    def checkId(self, login, pwd) -> str:
        try:
            # Query Firebase for user
            users_ref = db.collection('users')
            query = users_ref.where('username', '==', login).limit(1)
            docs = query.get()
            
            if not docs:
                return "Unauthorized - User not found"
            
            # Get user data from Firebase
            user_data = docs[0].to_dict()
            stored_password = user_data.get('password')
            user_email = user_data.get('email')
            
            # Verify password
            if bcrypt.checkpw(pwd.encode('utf-8'), stored_password.encode('utf-8')):
                return send_otp(user_email)
            else:
                return "Unauthorized - Invalid password"
                
        except Exception as e:
            print(f"Error during authentication: {e}")
            return "Authentication error"

def run():
    if db is None:
        print("Failed to initialize Firebase. Exiting...")
        return
        
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cloudsecurity_pb2_grpc.add_UserServiceServicer_to_server(UserServiceSkeleton(), server)
    server.add_insecure_port('[::]:51234')
    print('Starting Server on port 51234 ............', end='')
    server.start()
    print('[OK]')
    server.wait_for_termination()

if __name__ == '__main__':
    run()