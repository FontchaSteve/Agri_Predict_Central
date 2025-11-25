from firebase_config import db
import bcrypt
from utils import hash_password
import datetime

def debug_registration():
    """Debug the registration process step by step"""
    print("🐛 DEBUG MODE: Step-by-step registration test")
    print("=" * 50)
    
    # Test data
    username = "steve"
    email = "wandasteve@gmail.com"
    password = "test123"
    name = "stevejunior"
    
    try:
        # Step 1: Check Firebase connection
        print("1. 🔌 Checking Firebase connection...")
        if db is None:
            print("   ❌ Firebase not initialized")
            return False
        print("   ✅ Firebase connected")
        
        # Step 2: Check if user exists
        print("2. 🔍 Checking if user exists...")
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username)
        existing_users = list(query.get())
        print(f"   ✅ Query executed. Found {len(existing_users)} existing users")
        
        if existing_users:
            print("   ❌ User already exists")
            return False
        
        # Step 3: Check if email exists
        print("3. 📧 Checking if email exists...")
        email_query = users_ref.where('email', '==', email)
        existing_emails = list(email_query.get())
        print(f"   ✅ Email check done. Found {len(existing_emails)} existing emails")
        
        if existing_emails:
            print("   ❌ Email already exists")
            return False
        
        # Step 4: Hash password
        print("4. 🔐 Hashing password...")
        hashed_password = hash_password(password)
        print("   ✅ Password hashed")
        
        # Step 5: Prepare user data
        print("5. 📝 Preparing user data...")
        user_data = {
            'username': username,
            'email': email,
            'password': hashed_password,
            'name': name,
            'created_at': datetime.datetime.utcnow()
        }
        print("   ✅ User data prepared")
        
        # Step 6: Save to Firebase
        print("6. 💾 Saving to Firebase...")
        result = users_ref.add(user_data)
        print(f"   ✅ User saved with document ID: {result[1].id}")
        
        # Step 7: Verify save
        print("7. 🔎 Verifying save...")
        verify_query = users_ref.where('username', '==', username)
        saved_users = list(verify_query.get())
        
        if saved_users:
            print("   ✅ User verified in database!")
            user_data = saved_users[0].to_dict()
            print(f"   📧 Email: {user_data.get('email')}")
            print(f"   👤 Name: {user_data.get('name')}")
        else:
            print("   ❌ User not found in database after save")
            return False
            
        print("🎉 DEBUG COMPLETE: Registration should work!")
        return True
        
    except Exception as e:
        print(f"❌ DEBUG ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    debug_registration()