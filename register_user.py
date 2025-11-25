import bcrypt
from firebase_config import db
from utils import hash_password
import datetime
import re
import getpass

def validate_email(email):
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username):
    """Username validation"""
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, "Valid username"

def register_user(username, email, password, name=""):
    """Register a new user in Firebase"""
    try:
        if db is None:
            print("❌ Firebase not initialized.")
            return False
        
        # Validate inputs
        if not validate_email(email):
            print("❌ Invalid email format.")
            return False
            
        valid_username, username_msg = validate_username(username)
        if not valid_username:
            print(f"❌ {username_msg}")
            return False
            
        if len(password) < 6:
            print("❌ Password must be at least 6 characters long.")
            return False
        
        print("🔍 Checking if user exists...")
        
        # Check if user already exists
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username)
        existing_users = list(query.get())
        
        if existing_users:
            print(f"❌ Username '{username}' is already taken!")
            return False
        
        # Check if email already exists
        email_query = users_ref.where('email', '==', email)
        existing_emails = list(email_query.get())
        
        if existing_emails:
            print(f"❌ Email '{email}' is already registered!")
            return False
        
        print("🔐 Hashing password...")
        # Hash password
        hashed_password = hash_password(password)
        
        # Create user document
        user_data = {
            'username': username,
            'email': email,
            'password': hashed_password,
            'name': name if name else username,
            'created_at': datetime.datetime.utcnow()
        }
        
        print("💾 Saving user to Firebase...")
        # Add to Firebase
        doc_ref = users_ref.add(user_data)
        print(f"✅ User '{username}' registered successfully!")
        print(f"📄 Document ID: {doc_ref[1].id}")  # Show the Firestore document ID
        
        # Verify the user was saved
        print("🔎 Verifying user in database...")
        verify_query = users_ref.where('username', '==', username).limit(1)
        saved_users = list(verify_query.get())
        
        if saved_users:
            saved_user = saved_users[0].to_dict()
            print(f"✅ Verification successful!")
            print(f"📧 Email in DB: {saved_user.get('email')}")
            print(f"👤 Name in DB: {saved_user.get('name')}")
            print(f"🕒 Created: {saved_user.get('created_at')}")
        else:
            print("❌ Verification failed - user not found in database")
            
        return True
        
    except Exception as e:
        print(f"❌ Error registering user: {e}")
        return False

def get_user_input():
    """Get user registration details from command line input"""
    print("🚀 User Registration System")
    print("=" * 30)
    
    username = input("Enter username: ").strip()
    email = input("Enter email: ").strip()
    
    while True:
        password = getpass.getpass("Enter password: ")
        confirm_password = getpass.getpass("Confirm password: ")
        
        if password == confirm_password:
            if len(password) >= 6:
                break
            else:
                print("❌ Password must be at least 6 characters long.")
        else:
            print("❌ Passwords do not match. Please try again.")
    
    name = input("Enter full name (optional): ").strip()
    
    return username, email, password, name

def main():
    """Main function for interactive registration"""
    try:
        print("📌 Firebase initialized successfully with service account")
        print("🚀 Starting user registration...")
        
        username, email, password, name = get_user_input()
        
        print(f"\n📋 Registration Summary:")
        print(f"👤 Username: {username}")
        print(f"📧 Email: {email}")
        print(f"👤 Name: {name if name else 'Not provided'}")
        
        confirm = input("\nProceed with registration? (y/n): ").strip().lower()
        if confirm in ['y', 'yes']:
            print("\n⏳ Registering user...")
            success = register_user(username, email, password, name)
            if success:
                print(f"\n🎉 Registration completed successfully!")
                print(f"💡 You can now login with: python client.py login {username} [your_password]")
            else:
                print("\n❌ Registration failed. Please try again.")
        else:
            print("❌ Registration cancelled.")
            
    except KeyboardInterrupt:
        print("\n❌ Registration cancelled by user.")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")

if __name__ == '__main__':
    main()