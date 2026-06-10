import os
from app import create_app, db
from app.models import User, Asset, MaintenanceLog
from werkzeug.security import generate_password_hash

app = create_app()

def reset_database():
    # Remove existing db if exists
    db_path = os.path.join(app.instance_path, 'demirbas.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️  Old database deleted: {db_path}")
    
    if os.path.exists('demirbas.db'):
        os.remove('demirbas.db')
        print("🗑️  Old database deleted (root).")

    with app.app_context():
        # 1. Create all tables according to new models
        db.create_all()
        print("✅ New tables created.")

        # 2. Create Admin with Full Permissions
        admin = User(
            username='admin',
            email='admin@avrasya.edu.tr',
            password=generate_password_hash('password123'),
            full_name='System Administrator',
            department='IT',
            role='admin',         
            auth_level=3       # Highest permission
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print("------------------------------------------------")
        print("✅ SYSTEM READY!")
        print("👤 Username: admin")
        print("🔑 Password: password123")
        print("------------------------------------------------")

if __name__ == "__main__":
    reset_database()