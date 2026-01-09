from app import create_app, db
from app.models import Kullanici
from sqlalchemy import text

app = create_app()

def fix_admin_user():
    with app.app_context():
        # Veritabanı sütunları eksikse ekle (Migration yoksa manuel ekleme)
        try:
            db.session.execute(text("ALTER TABLE kullanici ADD COLUMN yetki_duzeyi INTEGER DEFAULT 0"))
            print("Sütun eklendi: yetki_duzeyi")
        except:
            print("Sütun zaten var: yetki_duzeyi")

        try:
            db.session.execute(text("ALTER TABLE kullanici ADD COLUMN rol VARCHAR(20) DEFAULT 'personel'"))
            print("Sütun eklendi: rol")
        except:
            print("Sütun zaten var: rol")
            
        db.session.commit()

        # Admin kullanıcısını güncelle
        admin = Kullanici.query.filter_by(kullanici_adi='admin').first()
        if admin:
            admin.rol = 'admin'
            admin.yetki_duzeyi = 3  # EN YÜKSEK SEVİYE
            admin.ad_soyad = 'Sistem Yöneticisi'
            db.session.commit()
            print(f"✅ BAŞARILI: Admin yetkileri güncellendi! (Rol: {admin.rol}, Yetki: {admin.yetki_duzeyi})")
        else:
            print("❌ Admin kullanıcısı bulunamadı!")

if __name__ == "__main__":
    fix_admin_user()