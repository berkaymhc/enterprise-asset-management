import random
from app import create_app, db
from app.models import Demirbas
from datetime import datetime

app = create_app()

def veri_yukle():
    with app.app_context():
        print("🌱 Örnek veriler hazırlanıyor...")

        # Örnek Veri Listesi
        kampusler = ['Mühendislik Fakültesi', 'Hukuk Fakültesi', 'Rektörlük', 'Yabancı Diller']
        konumlar = ['Z-10 Lab', '101 Nolu Sınıf', 'Toplantı Odası A', 'Bilgi İşlem Ofisi', 'Kütüphane']
        markalar = ['Dell', 'HP', 'Lenovo', 'Canon', 'Epson', 'Samsung', 'Ikea', 'Bürotime']
        
        # Demirbaş Tipleri
        tipler = [
            {'ad': 'Laptop Bilgisayar', 'cinsi': 'Elektronik', 'kategori': 'Bilgisayar'},
            {'ad': 'Lazer Yazıcı', 'cinsi': 'Elektronik', 'kategori': 'Yazıcı'},
            {'ad': 'Projeksiyon Cihazı', 'cinsi': 'Elektronik', 'kategori': 'Görüntüleme'},
            {'ad': 'Ofis Sandalyesi', 'cinsi': 'Mobilya', 'kategori': 'Ofis Mobilyası'},
            {'ad': 'Çalışma Masası', 'cinsi': 'Mobilya', 'kategori': 'Ofis Mobilyası'},
            {'ad': 'Klima Ünitesi', 'cinsi': 'Demirbaş', 'kategori': 'İklimlendirme'}
        ]

        eklenen_sayisi = 0
        
        # 50 Adet Rastgele Demirbaş Üret
        for i in range(1, 51):
            secilen_tip = random.choice(tipler)
            secilen_kampus = random.choice(kampusler)
            
            # Benzersiz Demirbaş No Üret (D-2024-001 gibi)
            d_no = f"D-2026-{1000 + i}"
            s_no = f"SN-{random.randint(10000, 99999)}"
            
            # Veritabanında var mı kontrol et (Hata almamak için)
            if Demirbas.query.filter_by(demirbas_no=d_no).first():
                continue

            yeni_urun = Demirbas(
                ad=f"{secilen_tip['ad']} - {i}",
                marka=random.choice(markalar),
                model=f"Model-{random.randint(10, 99)}X",
                seri_no=s_no,
                demirbas_no=d_no,
                cinsi=secilen_tip['cinsi'],
                kategori=secilen_tip['kategori'],
                konum=random.choice(konumlar),
                kampus=secilen_kampus,
                birim='İdari İşler',
                adet=1,
                durum='Aktif',
                kayit_tarihi=datetime.now()
            )
            
            db.session.add(yeni_urun)
            eklenen_sayisi += 1

        db.session.commit()
        print(f"✅ BAŞARILI: Toplam {eklenen_sayisi} adet örnek demirbaş veritabanına eklendi.")
        print("📊 Şimdi Dashboard'u kontrol edebilirsin!")

if __name__ == "__main__":
    veri_yukle()