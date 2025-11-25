import firebase_admin
from firebase_admin import credentials, firestore
import os

def initialize_firebase():
    try:
        # Method 1: Use service account key file
        if os.path.exists('firebase-service-account-key.json'):
            cred = credentials.Certificate('firebase-service-account-key.json')
            firebase_admin.initialize_app(cred)
            print("✅ Firebase initialized successfully with service account")
            return firestore.client()
        else:
            print("❌ Service account file not found. Please download it from Firebase Console.")
            return None
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        return None

# Initialize Firebase
db = initialize_firebase()