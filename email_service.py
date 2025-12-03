"""
Email Service for AgriPredict Cloud Storage
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class EmailService:
    def __init__(self):
        # Get email configuration from .env file
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.sender_email = os.getenv('SENDER_EMAIL', '')
        self.sender_password = os.getenv('SENDER_PASSWORD', '').replace(" ", "")  # Remove spaces!
        
        print("=" * 60)
        print("📧 Email Service Initialization")
        print("=" * 60)
        print(f"SMTP Server: {self.smtp_server}:{self.smtp_port}")
        print(f"Sender Email: {self.sender_email}")
        
        if self.sender_password:
            # Show first 4 chars for verification (security)
            masked_pw = self.sender_password[:4] + "*" * (len(self.sender_password) - 4)
            print(f"App Password: {masked_pw}")
            print(f"Password Length: {len(self.sender_password)} chars")
            
            if " " in os.getenv('SENDER_PASSWORD', ''):
                print("⚠️  WARNING: Password contains spaces! Removing them...")
            
            if len(self.sender_password) != 16:
                print(f"⚠️  WARNING: App password should be 16 chars, got {len(self.sender_password)}")
        else:
            print("❌ No app password configured")
        
        print("=" * 60)
        
    def test_email_connection(self):
        """Test if email configuration works"""
        if not self.sender_email or not self.sender_password:
            print("❌ Email not configured - check .env file")
            return False
            
        try:
            print("Testing email connection...")
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.quit()
            print("✅ Email connection successful!")
            return True
        except Exception as e:
            print(f"❌ Email connection failed: {str(e)}")
            return False
    
    def send_otp_email(self, recipient_email, otp_code, username):
        """Send OTP email to user"""
        try:
            # If email credentials are not configured, use console fallback
            if not self.sender_email or not self.sender_password:
                print("=" * 60)
                print(f"📧 OTP for {recipient_email}: {otp_code}")
                print("=" * 60)
                return True
            
            # Create message
            subject = "Your AgriPredict Cloud OTP Code"
            
            # HTML email content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; }}
                    .otp-code {{ font-size: 36px; font-weight: bold; letter-spacing: 10px; text-align: center; margin: 30px 0; color: #333; }}
                    .info-box {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ margin-top: 30px; text-align: center; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 AgriPredict Cloud</h1>
                        <p>Two-Factor Authentication</p>
                    </div>
                    
                    <h2>Hello {username},</h2>
                    <p>Your OTP code for AgriPredict Cloud login is:</p>
                    
                    <div class="otp-code">{otp_code}</div>
                    
                    <div class="info-box">
                        <p><strong>⚠️ Important:</strong></p>
                        <ul>
                            <li>This OTP is valid for 10 minutes</li>
                            <li>Do not share this code with anyone</li>
                            <li>If you didn't request this OTP, please ignore this email</li>
                        </ul>
                    </div>
                    
                    <p>Thank you for using AgriPredict Cloud Storage!</p>
                    
                    <div class="footer">
                        <p>AgriPredict Cloud Storage System</p>
                        <p>This is an automated email, please do not reply</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text alternative
            text_content = f"""
            AgriPredict Cloud - OTP Verification
            
            Hello {username},
            
            Your OTP code is: {otp_code}
            
            This code is valid for 10 minutes.
            
            Do not share this code with anyone.
            
            If you didn't request this OTP, please ignore this email.
            
            Thank you,
            AgriPredict Cloud Team
            """
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            # Attach both HTML and plain text
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"✅ OTP email sent to {recipient_email}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to send OTP email: {error_msg}")
            
            # Common error messages and solutions
            if "Username and Password not accepted" in error_msg:
                print("\n⚠️  TROUBLESHOOTING:")
                print("   1. Make sure 2-Step Verification is ON")
                print("   2. Generate a NEW app password")
                print("   3. Remove spaces from the app password")
                print("   4. Update .env file and restart the app")
            
            elif "Application-specific password required" in error_msg:
                print("\n⚠️  You need to use an App Password, not your regular password!")
                print("   Go to: https://myaccount.google.com/apppasswords")
            
            elif "Bad credentials" in error_msg:
                print("\n⚠️  Check your .env file:")
                print("   - Remove spaces from SENDER_PASSWORD")
                print("   - Make sure SENDER_EMAIL is correct")
            
            # Fallback to console
            print("=" * 60)
            print(f"📧 OTP for {recipient_email}: {otp_code}")
            print("=" * 60)
            return False

# Create a global instance
email_service = EmailService()