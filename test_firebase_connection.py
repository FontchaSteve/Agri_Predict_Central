from firebase_config import db

def test_firebase_connection():
    print("🧪 TESTING FIREBASE CONNECTION")
    print("=" * 40)
    
    if db is None:
        print("❌ Firebase connection failed")
        return False
    
    try:
        # Test read operation
        users_ref = db.collection('users')
        docs = list(users_ref.limit(1).get())
        print(f"✅ Read test: Found {len(docs)} users")
        
        # Test write operation
        test_data = {
            'test_field': 'connection_test',
            'timestamp': 'now'
        }
        test_ref = db.collection('connection_tests').document()
        test_ref.set(test_data)
        print("✅ Write test: Successfully wrote to Firestore")
        
        # Clean up test data
        test_ref.delete()
        print("✅ Cleanup test: Successfully deleted test data")
        
        print("🎉 All Firebase tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Firebase test failed: {e}")
        return False

if __name__ == '__main__':
    test_firebase_connection()