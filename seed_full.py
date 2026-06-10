import random
from app import create_app, db
from app.models import Asset, Personnel, MaintenanceLog, User
from datetime import datetime, timedelta

app = create_app()

def full_data_load():
    with app.app_context():
        print("🌱 LOADING SYSTEM DATA...")
        
        # ---------------------------------------------------------
        # 1. ASSET CHECK AND LOAD
        # ---------------------------------------------------------
        if Asset.query.count() < 10:
            print("📦 Adding assets...")
            campuses = ['Engineering Faculty', 'Law Faculty', 'Rectorate', 'Foreign Languages']
            locations = ['Z-10 Lab', 'Room 101', 'Meeting Room A', 'IT Office', 'Library']
            brands = ['Dell', 'HP', 'Lenovo', 'Canon', 'Epson', 'Samsung', 'Ikea', 'Bürotime']
            types = [
                {'name': 'Laptop Computer', 'type': 'Electronic', 'category': 'Computer'},
                {'name': 'Laser Printer', 'type': 'Electronic', 'category': 'Printer'},
                {'name': 'Projector', 'type': 'Electronic', 'category': 'Display'},
                {'name': 'Office Chair', 'type': 'Furniture', 'category': 'Office Furniture'},
            ]
            
            for i in range(1, 41):
                t = random.choice(types)
                db.session.add(Asset(
                    name=f"{t['name']} - {i}",
                    brand=random.choice(brands),
                    model=f"M-{random.randint(100,999)}",
                    serial_number=f"SN-{random.randint(10000, 99999)}",
                    asset_tag=f"A-2026-{1000+i}",
                    type=t['type'],
                    category=t['category'],
                    location=random.choice(locations),
                    campus=random.choice(campuses),
                    quantity=1,
                    purchase_date=datetime.now().strftime("%Y-%m-%d")
                ))
            db.session.commit()
            print("✅ 40 Assets added.")
        else:
            print("ℹ️ Asset data already exists, skipping.")

        # ---------------------------------------------------------
        # 2. PERSONNEL LOAD
        # ---------------------------------------------------------
        if Personnel.query.count() < 5:
            print("👥 Adding personnel...")
            names = [
                "Ahmet Yilmaz", "Ayse Demir", "Mehmet Ozturk", "Fatma Kaya", 
                "Mustafa Celik", "Zeynep Sahin", "Ali Yildiz", "Esra Aydin",
                "Burak Arslan", "Selin Polat", "Caner Erkin", "Derya Ulu"
            ]
            titles = ["Lecturer", "Asst. Prof.", "Clerk", "Technician", "Dept. Head", "Secretary"]
            departments = ["IT", "Student Affairs", "Personnel Dept.", "Engineering Fac.", "Law Fac."]
            
            for name in names:
                # Random phone
                phone = f"05{random.randint(30,55)} {random.randint(100,999)} {random.randint(10,99)}{random.randint(10,99)}"
                
                db.session.add(Personnel(
                    full_name=name,
                    title=random.choice(titles),
                    department=random.choice(departments),
                    campus=random.choice(['Main Campus', 'Pelitli', 'Yomra']),
                    office=f"Room-{random.randint(100, 400)}",
                    email=f"{name.lower().replace(' ','.')}@avrasya.edu.tr",
                    phone=phone
                ))
            db.session.commit()
            print(f"✅ {len(names)} Personnel added.")
        else:
            print("ℹ️ Personnel data already exists, skipping.")

        # ---------------------------------------------------------
        # 3. MAINTENANCE LOG LOAD
        # ---------------------------------------------------------
        admin = User.query.filter_by(username='admin').first()
        all_assets = Asset.query.all()
        
        if not admin:
            print("❌ Admin user not found! Run reset_db.py first.")
            return

        if MaintenanceLog.query.count() < 5:
            print("🔧 Creating maintenance logs...")
            titles = [
                "Printer jamming paper", "Computer not booting", "Broken screen", 
                "Wheel fell off", "Blue screen error", "Projector lamp blown",
                "AC leaking water", "No internet connection", "Keyboard keys stuck"
            ]
            statuses = ['Pending', 'In Progress', 'Waiting for Parts', 'Completed', 'Completed', 'Cancelled']
            
            for _ in range(15):
                selected_asset = random.choice(all_assets)
                selected_status = random.choice(statuses)
                past_time = datetime.now() - timedelta(days=random.randint(0, 30))
                
                log = MaintenanceLog(
                    title=random.choice(titles),
                    description="Device unexpectedly gave this error during use. Needs inspection.",
                    status=selected_status,
                    date_reported=past_time,
                    asset_id=selected_asset.id,
                    user_id=admin.id
                )
                db.session.add(log)
            
            db.session.commit()
            print("✅ 15 Maintenance logs created.")
        else:
            print("ℹ️ Maintenance data already exists, skipping.")

        print("\n🚀 DONE! You can now run the project and test it.")

if __name__ == "__main__":
    full_data_load()