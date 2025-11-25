from firebase_config import db

def view_all_users():
    """View all users in the Firebase database"""
    try:
        print("🔍 Fetching all users from Firebase...")
        
        if db is None:
            print("❌ Firebase not initialized.")
            return
        
        users_ref = db.collection('users')
        docs = users_ref.get()
        
        if not docs:
            print("❌ No users found in the database.")
            return
        
        print(f"\n📊 Found {len(docs)} user(s) in the database:")
        print("=" * 60)
        
        for i, doc in enumerate(docs, 1):
            user_data = doc.to_dict()
            print(f"👤 User #{i}:")
            print(f"   📄 Document ID: {doc.id}")
            print(f"   👤 Username: {user_data.get('username', 'N/A')}")
            print(f"   📧 Email: {user_data.get('email', 'N/A')}")
            print(f"   🏷️ Name: {user_data.get('name', 'N/A')}")
            print(f"   🔐 Password: {user_data.get('password', 'N/A')[:20]}...")  # Show first 20 chars of hash
            print(f"   🕒 Created: {user_data.get('created_at', 'N/A')}")
            print("-" * 40)
            
    except Exception as e:
        print(f"❌ Error fetching users: {e}")

if __name__ == '__main__':
    view_all_users()