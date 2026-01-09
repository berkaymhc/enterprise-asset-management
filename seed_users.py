from app import create_app, db
from app.models import Kullanici
from werkzeug.security import generate_password_hash

app = create_app()

def kullanicilari_olustur():
    with app.app_context():
        print("👥 KULLANICI SENARYOLARI OLUŞTURULUYOR...")
        print("-------------------------------------------------")

        # Test Kullanıcıları Listesi
        kullanicilar = [
            {
                'kadi': 'teknik',
                'sifre': '12345',
                'ad': 'Ali Tekniker',
                'rol': 'teknik',        # Teknik Servis Modu
                'yetki': 1,             # Düşük/Orta Yetki
                'birim': 'Bilgi İşlem',
                'desc': '🔧 TEKNİK SERVİS: Sadece Arıza tablosuna yönlendirilir. Demirbaş ekleyemez.'
            },
            {
                'kadi': 'sorumlu',
                'sifre': '12345',
                'ad': 'Ayşe Müdür',
                'rol': 'admin',         # Admin yetkileri var ama kısıtlı olabilir
                'yetki': 2,             # Seviye 2 (Birim Sorumlusu - Silme yapamaz)
                'birim': 'İdari İşler',
                'desc': '👔 BİRİM SORUMLUSU: Demirbaş günceller, taşır ama SİLEMEZ (Yetki < 3).'
            },
            {
                'kadi': 'personel',
                'sifre': '12345',
                'ad': 'Mehmet Memur',
                'rol': 'personel',      # Standart Kullanıcı
                'yetki': 0,             # İzleyici (Sadece Okuma)
                'birim': 'Öğrenci İşleri',
                'desc': '👀 STANDART PERSONEL: Sadece listeyi görür. Hiçbir buton aktif değildir.'
            }
        ]

        # Admin Kontrolü (Zaten varsa dokunma)
        admin = Kullanici.query.filter_by(kullanici_adi='admin').first()
        if not admin:
            print("❌ Önce 'reset_db.py' ile Admin oluşturmalısın.")
        else:
            print(f"👑 ADMIN (Mevcut): Tam Yetki (Seviye 3)")

        # Diğerlerini Ekle
        for k in kullanicilar:
            mevcut = Kullanici.query.filter_by(kullanici_adi=k['kadi']).first()
            if not mevcut:
                yeni = Kullanici(
                    kullanici_adi=k['kadi'],
                    email=f"{k['kadi']}@avrasya.edu.tr",
                    sifre=generate_password_hash(k['sifre']),
                    ad_soyad=k['ad'],
                    rol=k['rol'],
                    yetki_duzeyi=k['yetki'],
                    birim=k['birim']
                )
                db.session.add(yeni)
                print(f"✅ Eklendi: {k['kadi']} ({k['desc']})")
            else:
                # Mevcutsa özelliklerini güncelle (Test için emin olalım)
                mevcut.rol = k['rol']
                mevcut.yetki_duzeyi = k['yetki']
                mevcut.sifre = generate_password_hash(k['sifre'])
                print(f"🔄 Güncellendi: {k['kadi']}")

        db.session.commit()
        print("\n🚀 TÜM KULLANICILAR HAZIR! Şifrelerin hepsi: 12345")

if __name__ == "__main__":
    kullanicilari_olustur()