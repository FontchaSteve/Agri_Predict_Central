import sys
import getpass
from register_user import register_user

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
    try:
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
                print(f"\n🎉 Registration successful!")
                print(f"💡 You can now login with your username and password")
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