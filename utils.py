import bcrypt
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from params import from_email, app_password

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
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect and send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            print(f"Starting tls session on smtp.gmail.com:587 .........", end='')
            server.starttls()
            print('[OK]')
            print(f"login to the server with {from_email} .........", end='')
            server.login(from_email, app_password)
            print('[OK]')
            print(f"Sending OTP data to {to_email}  .........", end='')
            server.send_message(msg)
            print('[OK]')
            print(f"OTP data sent to {to_email} successfully!")
            return f"OTP data sent to your email: {to_email} successfully!"
    except Exception as e:
        print(f"Failed to send email: {e}")
        return f"Failed to send OTP: {e}"

# Remove the file-based credential creation part since we're using Firebase