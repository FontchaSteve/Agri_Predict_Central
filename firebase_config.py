import firebase_admin
from firebase_admin import credentials, firestore
import os
import datetime

def initialize_firebase():
    try:
        # Check if Firebase is already initialized
        if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
            print("✅ Firebase already initialized")
            return firestore.client()
        
        # Check if service account file exists
        service_account_path = 'firebase-service-account-key.json'
        if not os.path.exists(service_account_path):
            print(f"❌ Service account file not found: {service_account_path}")
            print("💡 Please download it from Firebase Console:")
            print("   https://console.firebase.google.com/project/cloudgrpc-b1d3f/settings/serviceaccounts/adminsdk")
            return None
        
        print("🔌 Initializing Firebase...")
        
        # Initialize with the service account
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        
        print("✅ Firebase initialized successfully")
        print(f"🕒 Current system time: {datetime.datetime.now()}")
        
        return firestore.client()
        
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        print("💡 Possible solutions:")
        print("   1. Download a new service account key from Firebase Console")
        print("   2. Check your system clock is synchronized")
        print("   3. Check your internet connection")
        return None

# Initialize Firebase
db = initialize_firebase()