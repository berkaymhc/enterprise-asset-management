import random
from app import create_app, db
from app.models import Asset
from datetime import datetime

app = create_app()

def load_data():
    with app.app_context():
        print("🌱 Preparing sample data...")

        # Sample Data Lists
        campuses = ['Engineering Faculty', 'Law Faculty', 'Rectorate', 'Foreign Languages']
        locations = ['Z-10 Lab', 'Room 101', 'Meeting Room A', 'IT Office', 'Library']
        brands = ['Dell', 'HP', 'Lenovo', 'Canon', 'Epson', 'Samsung', 'Ikea', 'Bürotime']
        
        # Asset Types
        types = [
            {'name': 'Laptop Computer', 'type': 'Electronic', 'category': 'Computer'},
            {'name': 'Laser Printer', 'type': 'Electronic', 'category': 'Printer'},
            {'name': 'Projector', 'type': 'Electronic', 'category': 'Display'},
            {'name': 'Office Chair', 'type': 'Furniture', 'category': 'Office Furniture'},
            {'name': 'Work Desk', 'type': 'Furniture', 'category': 'Office Furniture'},
            {'name': 'Air Conditioner', 'type': 'Asset', 'category': 'HVAC'}
        ]

        added_count = 0
        
        # Generate 50 Random Assets
        for i in range(1, 51):
            selected_type = random.choice(types)
            selected_campus = random.choice(campuses)
            
            # Generate Unique Asset No (e.g. D-2024-001)
            d_no = f"A-2026-{1000 + i}"
            s_no = f"SN-{random.randint(10000, 99999)}"
            
            # Check if exists in DB to prevent errors
            if Asset.query.filter_by(asset_tag=d_no).first():
                continue

            new_item = Asset(
                name=f"{selected_type['name']} - {i}",
                brand=random.choice(brands),
                model=f"Model-{random.randint(10, 99)}X",
                serial_number=s_no,
                asset_tag=d_no,
                type=selected_type['type'],
                category=selected_type['category'],
                location=random.choice(locations),
                campus=selected_campus,
                department='Administrative',
                quantity=1,
                status='Active',
                purchase_date=datetime.now().strftime("%Y-%m-%d")
            )
            
            db.session.add(new_item)
            added_count += 1

        db.session.commit()
        print(f"✅ SUCCESS: A total of {added_count} sample assets were added to the database.")
        print("📊 Now you can check the Dashboard!")

if __name__ == "__main__":
    load_data()