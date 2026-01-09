from app import create_app, db
from app.models import Personel, Demirbas

app = create_app()

def baglantiyi_kur():
    with app.app_context():
        print("🔗 Veri bağlantıları kuruluyor...")

        # 1. İçinde eşya olan bir ofis bulalım (Garanti olsun)
        ornek_demirbas = Demirbas.query.first()
        if not ornek_demirbas:
            print("❌ HATA: Sistemde hiç demirbaş yok! Önce seed_full.py çalıştır.")
            return
            
        hedef_ofis = ornek_demirbas.konum # Örn: 'Z-10 Lab'
        print(f"📍 Hedef Ofis: {hedef_ofis} (Bu ofiste eşya var)")
        
        # 2. Test Kullanıcılarımızın E-postaları
        test_kullanicilari = [
            {'email': 'personel@avrasya.edu.tr', 'ad': 'Mehmet Memur'},
            {'email': 'teknik@avrasya.edu.tr', 'ad': 'Ali Tekniker'},
            {'email': 'sorumlu@avrasya.edu.tr', 'ad': 'Ayşe Müdür'}
        ]

        for k in test_kullanicilari:
            # Bu e-postaya sahip bir Personel var mı?
            p = Personel.query.filter_by(email=k['email']).first()
            
            if not p:
                # Yoksa oluşturalım
                p = Personel(
                    ad_soyad=k['ad'],
                    email=k['email'],
                    unvan='Personel',
                    birimi='Bilgi İşlem',
                    kampus='Merkez',
                    telefon='0500 123 45 67'
                )
                db.session.add(p)
                print(f"➕ {k['ad']} personel listesine eklendi.")
            
            # 3. Ofisini, içinde eşya olan ofis yapalım
            p.ofis = hedef_ofis
            print(f"✅ {k['ad']} -> {hedef_ofis} ofisine atandı.")

        db.session.commit()
        print("\n🚀 İŞLEM TAMAM! Şimdi 'personel' kullanıcısı ile giriş yapıp deneyebilirsin.")

if __name__ == '__main__':
    baglantiyi_kur()