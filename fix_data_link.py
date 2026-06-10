from app import create_app, db
from app.models import Personnel, Asset

app = create_app()

def establish_connection():
    with app.app_context():
        print("🔗 Establishing data connections...")

        # 1. Find an office with an asset in it
        sample_asset = Asset.query.first()
        if not sample_asset:
            print("❌ ERROR: No assets in the system! Run seed_full.py first.")
            return
            
        target_office = sample_asset.location # e.g. 'Z-10 Lab'
        print(f"📍 Target Office: {target_office} (Contains assets)")
        
        # 2. Test Users' Emails
        test_users = [
            {'email': 'staff@avrasya.edu.tr', 'name': 'Mehmet Staff'},
            {'email': 'tech@avrasya.edu.tr', 'name': 'Ali Tech'},
            {'email': 'manager@avrasya.edu.tr', 'name': 'Ayse Manager'}
        ]

        for k in test_users:
            p = Personnel.query.filter_by(email=k['email']).first()
            
            if not p:
                p = Personnel(
                    full_name=k['name'],
                    email=k['email'],
                    title='Personnel',
                    department='IT',
                    campus='Main Campus',
                    phone='0500 123 45 67'
                )
                db.session.add(p)
                print(f"➕ Added {k['name']} to personnel list.")
            
            # 3. Assign them to the target office
            p.office = target_office
            print(f"✅ {k['name']} -> assigned to office {target_office}.")

        db.session.commit()
        print("\n🚀 DONE! Now you can login with the 'staff' user and try it.")

if __name__ == '__main__':
    establish_connection()