from app import create_app, db
from app.models import Kullanici
from werkzeug.security import generate_password_hash
import datetime

# Uygulamayı başlat
app = create_app()

with app.app_context():
    # Tabloları garantiye al (Zaten varsa bir şey yapmaz)
    db.create_all()
    
    # Admin var mı kontrol et?
    mevcut_admin = Kullanici.query.filter_by(kullanici_adi="admin").first()
    
    if not mevcut_admin:
        print("Admin oluşturuluyor...")
        admin = Kullanici(
            kullanici_adi="admin",
            sifre=generate_password_hash("12345"),
            ad_soyad="Sistem Yöneticisi",
            birim="Bilgi İşlem",
            rol="admin",
            yetki_duzeyi=3,
            tarih=datetime.datetime.now().strftime("%Y-%m-%d")
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ BAŞARILI: Admin kullanıcısı eklendi!")
        print("➡️  Kullanıcı Adı: admin")
        print("➡️  Şifre: 12345")
    else:
        print("⚠️  Admin kullanıcısı zaten veritabanında mevcut.")