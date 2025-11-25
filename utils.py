import bcrypt
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from params import from_email, from_password

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), 
                         bcrypt.gensalt()).decode('utf-8')

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(to_email) -> str:

    otp = generate_otp()

    # Sender configuration
    subject = "Your OTP Code for the cloud security simulator"
    body = f"Your OTP code is: {otp}"

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = 'sasbergson@gmail.com'
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect and send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            print(f"Starting tls session on smtp.gmail.com:587 .........", end='')
            server.starttls()  # Upgrade the connection to a secure encrypted SSL/TLS connection
            print('[OK]')
            print(f"login to the server with {from_email} .........", end='')
            server.login('sasbergson@gmail.com', 'tgnw azxw lfjr jsuz')
            print('[OK]')
            print(f"Sending OTP data to {to_email}  .........", end='')
            server.send_message(msg)
            print('[OK]')
            print(f"OTP data sent to {to_email} successfully!")
            return f"OTP data sent to your email: {to_email} successfully!"
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    credentials = {}
    file_path = 'ids'
    with open(file_path, 'r') as file:
        for line in file:
            username, password = line.strip().split(',')
            credentials[username] = password

    with open('credentials', 'w') as file:
        for username, password in credentials.items():
            file.write(f'{username},{hash_password(password)}\n')