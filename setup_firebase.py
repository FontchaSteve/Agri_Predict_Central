from firebase_config import db

def setup_firestore():
    """Initialize Firestore with some test data"""
    try:
        # Test data
        test_users = [
            {
                'username': 'test_user',
                'email': 'test@example.com', 
                'password': '$2b$12$hashedpassword123', # You'll hash real passwords
                'name': 'Test User'
            }
        ]
        
        # Add test users
        for user in test_users:
            db.collection('users').add(user)
        
        print("✅ Firebase Firestore setup completed!")
        print("✅ Test data added successfully!")
        
    except Exception as e:
        print(f"❌ Error setting up Firebase: {e}")

if __name__ == '__main__':
    setup_firestore()