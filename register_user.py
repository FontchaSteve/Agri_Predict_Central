import bcrypt
from firebase_config import db
from utils import hash_password
from google.cloud import firestore  # ADD THIS IMPORT

def register_user(username, email, password, name=""):
    """Register a new user in Firebase"""
    try:
        if db is None:
            print("❌ Firebase not initialized. Please check your configuration.")
            return False
            
        # Check if user already exists
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1)
        existing_users = query.get()
        
        if existing_users:
            print(f"❌ User {username} already exists!")
            return False
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Create user document
        user_data = {
            'username': username,
            'email': email,
            'password': hashed_password,
            'name': name if name else username,
            'created_at': firestore.SERVER_TIMESTAMP  # NOW THIS WILL WORK
        }
        
        # Add to Firebase
        users_ref.add(user_data)
        print(f"✅ User {username} registered successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error registering user: {e}")
        return False

if __name__ == '__main__':
    # Example: Register a test user
    register_user("john_doe", "john@example.com", "password123", "John Doe")