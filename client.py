import sys
import grpc
#from concurrent import futures
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc


def run(request, login, password):
    with grpc.insecure_channel('localhost:51234') as channel:
        stub = cloudsecurity_pb2_grpc.UserServiceStub(channel)
        if (request == "login"):
            response = stub.login(cloudsecurity_pb2.Request(login=login, password=password))
        else:
            print("Invalid request")
            exit()
    print(f"Result: {response.result}")


if __name__ == '__main__':
    # Get user Input 
    request = sys.argv[1]
    login = sys.argv[2]
    password = sys.argv[3]
    run(request, login, password)