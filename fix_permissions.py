from app import create_app, db
from app.models import User

app = create_app()

def fix_permissions():
    with app.app_context():
        print("🔧 FIXING PERMISSIONS...\n")

        # 1. FIX MANAGER USER
        manager = User.query.filter_by(username='manager').first()
        if manager:
            manager.role = 'personnel'
            manager.auth_level = 2
            print(f"✅ FIXED: {manager.full_name} -> Role: Personnel, Auth: 2 (Department Manager)")
        else:
            print("⚠️ 'manager' user not found.")

        # 2. CHECK TECHNICIAN
        tech = User.query.filter_by(username='tech').first()
        if tech:
            tech.role = 'technician'
            tech.auth_level = 1
            print(f"✅ CHECKED: {tech.full_name} -> Role: Technician, Auth: 1")

        # 3. CHECK STANDARD STAFF
        staff = User.query.filter_by(username='staff').first()
        if staff:
            staff.role = 'personnel'
            staff.auth_level = 0
            print(f"✅ CHECKED: {staff.full_name} -> Role: Personnel, Auth: 0 (View Only)")

        # 4. CHECK ADMIN
        admin = User.query.filter_by(username='admin').first()
        if admin:
            admin.role = 'admin'
            admin.auth_level = 3
            print(f"✅ CHECKED: {admin.full_name} -> Role: Admin, Auth: 3 (Full Access)")

        db.session.commit()
        print("\n🚀 DONE! Now logout and login with 'manager' to test.")

if __name__ == "__main__":
    fix_permissions()