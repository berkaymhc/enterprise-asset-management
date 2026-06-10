from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime

# ----------------------------------------------------
# 1. USER MODEL
# ----------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    
    # Role: 'admin', 'personnel', 'technician'
    role = db.Column(db.String(20), default='personnel') 
    # Auth Level: 0 (Read-only), 1 (Responsible), 2 (Auditor), 3 (Full Admin)
    auth_level = db.Column(db.Integer, default=0) 
    
    created_date = db.Column(db.String(20))

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ----------------------------------------------------
# 2. ASSET MODEL
# ----------------------------------------------------
class Asset(db.Model):
    __tablename__ = 'assets'
    __table_args__ = (
        db.Index('idx_asset_campus', 'campus'),
        db.Index('idx_asset_location', 'location'),
        db.Index('idx_asset_name', 'name'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(50))
    model = db.Column(db.String(50))
    serial_number = db.Column(db.String(50), unique=True)
    asset_tag = db.Column(db.String(50), unique=True, nullable=False)
    
    type = db.Column(db.String(50)) 
    purchase_date = db.Column(db.String(20)) # 'YYYY-MM-DD'
    
    category = db.Column(db.String(50))
    location = db.Column(db.String(100))
    campus = db.Column(db.String(100))
    department = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    qr_code = db.Column(db.String(200))
    photo = db.Column(db.String(100))
    
    maintenance_logs = db.relationship('MaintenanceLog', backref='asset', lazy=True)

# ----------------------------------------------------
# 3. PERSONNEL MODEL
# ----------------------------------------------------
class Personnel(db.Model):
    __tablename__ = 'personnel'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    title = db.Column(db.String(100))
    department = db.Column(db.String(100))
    registration_no = db.Column(db.String(50))
    office = db.Column(db.String(50))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    start_date = db.Column(db.String(20))
    campus = db.Column(db.String(100))

# ----------------------------------------------------
# 4. MAINTENANCE LOG MODEL
# ----------------------------------------------------
class MaintenanceLog(db.Model):
    __tablename__ = 'maintenance_logs'
    __table_args__ = (
        db.Index('idx_maintenance_asset_id', 'asset_id'),
        db.Index('idx_maintenance_status', 'status'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    
    priority = db.Column(db.String(20), default='Normal') 
    location = db.Column(db.String(100)) 
    
    date_reported = db.Column(db.DateTime, default=datetime.utcnow)
    
    reported_by = db.Column(db.String(100)) 

    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# ----------------------------------------------------
# 5. UPLOAD HISTORY MODEL
# ----------------------------------------------------
class UploadHistory(db.Model):
    __tablename__ = 'upload_history'
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255))
    upload_date = db.Column(db.String(30))
    uploaded_by = db.Column(db.String(100))
    type = db.Column(db.String(50)) 
    target_location = db.Column(db.String(255))