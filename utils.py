import bcrypt
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from params import from_email, app_password  # This should now use juniorwanda687@gmail.com
import datetime

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), 
                         bcrypt.gensalt()).decode('utf-8')

def generate_otp():
    """Generate a 6-digit OTP code"""
    return str(random.randint(100000, 999999))

def send_otp(to_email, otp_code=None):
    """Send OTP code to user's email"""
    
    # Generate OTP if not provided
    if otp_code is None:
        otp_code = generate_otp()
    
    # Sender configuration - NOW USING YOUR EMAIL
    subject = "Your OTP Code for Cloud Security System"
    body = f"""
    Your One-Time Password (OTP) for login is:

    🔐 {otp_code}

    This code will expire in 5 minutes.

    If you didn't request this code, please ignore this email.

    Best regards,
    Cloud Security Team
    """

    # Create the email - NOW FROM YOUR EMAIL
    msg = MIMEMultipart()
    msg['From'] = from_email  # This should be juniorwanda97@gmail.com
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect and send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            print(f"📧 Starting TLS session on smtp.gmail.com:587...", end='')
            server.starttls()
            print('[OK]')
            
            print(f"🔐 Logging in to email server with {from_email}...", end='')
            server.login(from_email, app_password)  # Using your email and app password
            print('[OK]')
            
            print(f"📨 Sending OTP to {to_email}...", end='')
            server.send_message(msg)
            print('[OK]')
            
            return f"OTP sent to {to_email}"
            
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return f"Failed to send OTP: {e}"