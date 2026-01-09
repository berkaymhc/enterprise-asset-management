import os
from app import create_app, db
from app.models import Kullanici, Demirbas, Ariza
from werkzeug.security import generate_password_hash

app = create_app()

def reset_database():
    # Veritabanı dosyası varsa sil (Temiz başlangıç)
    db_path = os.path.join(app.instance_path, 'demirbas.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️  Eski veritabanı silindi: {db_path}")
    
    # Alternatif yol (instance klasöründe değilse)
    if os.path.exists('demirbas.db'):
        os.remove('demirbas.db')
        print("🗑️  Eski veritabanı silindi (ana dizin).")

    with app.app_context():
        # 1. Tabloları Yeni Modele Göre Oluştur
        db.create_all()
        print("✅ Yeni tablolar (cinsi, yetki_duzeyi dahil) oluşturuldu.")

        # 2. Full Yetkili Admin Oluştur
        admin = Kullanici(
            kullanici_adi='admin',
            email='admin@avrasya.edu.tr',
            sifre=generate_password_hash('12345'),
            ad_soyad='Sistem Yöneticisi',
            birim='Bilgi İşlem',
            # KRİTİK NOKTALAR:
            rol='admin',         
            yetki_duzeyi=3       # En yüksek yetki
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print("------------------------------------------------")
        print("✅ SİSTEM HAZIR!")
        print("👤 Kullanıcı: admin")
        print("🔑 Şifre: 12345")
        print("------------------------------------------------")

if __name__ == "__main__":
    reset_database()