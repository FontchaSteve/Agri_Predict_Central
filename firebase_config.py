import firebase_admin
from firebase_admin import credentials, firestore
import os
import datetime

def initialize_firebase():
    try:
        # Check if already initialized
        if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
            app = firebase_admin.get_app()
            print("✅ Firebase already initialized")
            return firestore.client(app=app)
        
        # Check service account file
        service_account_path = 'firebase-service-account-key.json'
        if not os.path.exists(service_account_path):
            print(f"❌ Service account file not found: {service_account_path}")
            return None
        
        print(f"🔌 Initializing Firebase with: {service_account_path}")
        
        # Initialize Firebase
        cred = credentials.Certificate(service_account_path)
        app = firebase_admin.initialize_app(cred)
        
        # Test the connection
        db = firestore.client(app=app)
        
        # Try a simple operation to verify connection
        test_ref = db.collection('test_connection')
        test_ref.limit(1).get()
        
        print("✅ Firebase initialized and connected successfully!")
        print(f"🕒 Connection time: {datetime.datetime.now()}")
        
        return db
        
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        print("💡 Solutions:")
        print("   1. Download a NEW service account key from Firebase Console")
        print("   2. Check if your project exists and Firestore is enabled")
        print("   3. Check your internet connection")
        return None

# Initialize Firebase
db = initialize_firebase()