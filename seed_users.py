from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

def create_users():
    with app.app_context():
        print("👥 CREATING USER SCENARIOS...")
        print("-------------------------------------------------")

        # Test Users List
        users = [
            {
                'username': 'tech',
                'password': 'password123',
                'full_name': 'Ali Tech',
                'role': 'technician',
                'auth_level': 1,
                'department': 'IT',
                'desc': '🔧 TECHNICIAN: Directed only to Maintenance. Cannot add assets.'
            },
            {
                'username': 'manager',
                'password': 'password123',
                'full_name': 'Ayse Manager',
                'role': 'admin',
                'auth_level': 2,
                'department': 'Administrative',
                'desc': '👔 DEPARTMENT MANAGER: Can update and move assets but CANNOT DELETE (Auth < 3).'
            },
            {
                'username': 'staff',
                'password': 'password123',
                'full_name': 'Mehmet Staff',
                'role': 'personnel',
                'auth_level': 0,
                'department': 'Student Affairs',
                'desc': '👀 STANDARD STAFF: View-only. No buttons are active.'
            }
        ]

        # Admin Check
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("❌ You must first create an Admin using 'reset_db.py'.")
        else:
            print(f"👑 ADMIN (Exists): Full Permissions (Level 3)")

        for k in users:
            existing = User.query.filter_by(username=k['username']).first()
            if not existing:
                new_user = User(
                    username=k['username'],
                    email=f"{k['username']}@avrasya.edu.tr",
                    password=generate_password_hash(k['password']),
                    full_name=k['full_name'],
                    role=k['role'],
                    auth_level=k['auth_level'],
                    department=k['department']
                )
                db.session.add(new_user)
                print(f"✅ Added: {k['username']} ({k['desc']})")
            else:
                existing.role = k['role']
                existing.auth_level = k['auth_level']
                existing.password = generate_password_hash(k['password'])
                print(f"🔄 Updated: {k['username']}")

        db.session.commit()
        print("\n🚀 ALL USERS READY! Passwords are: password123")

if __name__ == "__main__":
    create_users()