import bcrypt
import grpc
from concurrent import futures
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc
from utils import send_otp

class UserServiceSkeleton(cloudsecurity_pb2_grpc.UserServiceServicer):
    def login(self, request, context) -> cloudsecurity_pb2.Response:
        print(f'new incoming request ... \nrequest: {request}')
        result = self.checkId(request.login, request.password)
        return cloudsecurity_pb2.Response(result=result)

    def checkId(self, login, pwd) -> str:
        credentials = {} # dictionary to store credentials
        emails = {}
        file_path = 'credentials'
        with open(file_path, 'r') as file:
            for line in file:
                username, email, password = line.strip().split(',')
                credentials[username] = password
                emails[username] = email
        if (credentials.get(login,None) and 
            bcrypt.checkpw(pwd.encode('utf-8'), credentials[login].encode('utf-8'))):
            return send_otp(emails[login])
        else:
            return "Unauthorized"

def run():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cloudsecurity_pb2_grpc.add_UserServiceServicer_to_server(UserServiceSkeleton(), server)
    server.add_insecure_port('[::]:51234')
    print('Starting Server on port 51234 ............', end='')
    server.start()
    print('[OK]')
    server.wait_for_termination()

if __name__ == '__main__':
    run()