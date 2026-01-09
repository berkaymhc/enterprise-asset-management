import random
from app import create_app, db
from app.models import Demirbas, Personel, Ariza, Kullanici
from datetime import datetime, timedelta

app = create_app()

def tam_veri_yukle():
    with app.app_context():
        print("🌱 SİSTEM VERİLERİ YÜKLENİYOR...")
        
        # ---------------------------------------------------------
        # 1. DEMİRBAŞ KONTROLÜ VE YÜKLEME
        # ---------------------------------------------------------
        if Demirbas.query.count() < 10:
            print("📦 Demirbaşlar ekleniyor...")
            kampusler = ['Mühendislik Fakültesi', 'Hukuk Fakültesi', 'Rektörlük', 'Yabancı Diller']
            konumlar = ['Z-10 Lab', '101 Nolu Sınıf', 'Toplantı Odası A', 'Bilgi İşlem Ofisi', 'Kütüphane']
            markalar = ['Dell', 'HP', 'Lenovo', 'Canon', 'Epson', 'Samsung', 'Ikea', 'Bürotime']
            tipler = [
                {'ad': 'Laptop Bilgisayar', 'cinsi': 'Elektronik', 'kategori': 'Bilgisayar'},
                {'ad': 'Lazer Yazıcı', 'cinsi': 'Elektronik', 'kategori': 'Yazıcı'},
                {'ad': 'Projeksiyon', 'cinsi': 'Elektronik', 'kategori': 'Görüntüleme'},
                {'ad': 'Ofis Sandalyesi', 'cinsi': 'Mobilya', 'kategori': 'Ofis Mobilyası'},
            ]
            
            for i in range(1, 41):
                tip = random.choice(tipler)
                db.session.add(Demirbas(
                    ad=f"{tip['ad']} - {i}",
                    marka=random.choice(markalar),
                    model=f"M-{random.randint(100,999)}",
                    seri_no=f"SN-{random.randint(10000, 99999)}",
                    demirbas_no=f"D-2026-{1000+i}",
                    cinsi=tip['cinsi'],
                    kategori=tip['kategori'],
                    konum=random.choice(konumlar),
                    kampus=random.choice(kampusler),
                    adet=1,
                    alim_tarihi=datetime.now().strftime("%Y-%m-%d")
                ))
            db.session.commit()
            print("✅ 40 Demirbaş eklendi.")
        else:
            print("ℹ️ Demirbaş verisi zaten var, atlanıyor.")

        # ---------------------------------------------------------
        # 2. PERSONEL YÜKLEME
        # ---------------------------------------------------------
        if Personel.query.count() < 5:
            print("👥 Personeller ekleniyor...")
            isimler = [
                "Ahmet Yılmaz", "Ayşe Demir", "Mehmet Öztürk", "Fatma Kaya", 
                "Mustafa Çelik", "Zeynep Şahin", "Ali Yıldız", "Esra Aydın",
                "Burak Arslan", "Selin Polat", "Caner Erkin", "Derya Ulu"
            ]
            unvanlar = ["Öğr. Gör.", "Dr. Öğr. Üyesi", "Memur", "Teknisyen", "Daire Bşk.", "Sekreter"]
            birimler = ["Bilgi İşlem", "Öğrenci İşleri", "Personel Daire Bşk.", "Mühendislik Fak.", "Hukuk Fak."]
            
            for isim in isimler:
                # Rastgele telefon üret
                tel = f"05{random.randint(30,55)} {random.randint(100,999)} {random.randint(10,99)}{random.randint(10,99)}"
                
                db.session.add(Personel(
                    ad_soyad=isim,
                    unvan=random.choice(unvanlar),
                    birimi=random.choice(birimler),
                    kampus=random.choice(['Merkez', 'Pelitli', 'Yomra']),
                    ofis=f"Oda-{random.randint(100, 400)}",
                    email=f"{isim.lower().replace(' ','.')}@avrasya.edu.tr",
                    telefon=tel
                ))
            db.session.commit()
            print(f"✅ {len(isimler)} Personel eklendi.")
        else:
            print("ℹ️ Personel verisi zaten var, atlanıyor.")

        # ---------------------------------------------------------
        # 3. ARIZA KAYITLARI YÜKLEME
        # ---------------------------------------------------------
        admin = Kullanici.query.filter_by(kullanici_adi='admin').first()
        tum_demirbaslar = Demirbas.query.all()
        
        if not admin:
            print("❌ Admin kullanıcısı bulunamadı! Önce reset_db.py çalıştırın.")
            return

        if Ariza.query.count() < 5:
            print("🔧 Arıza kayıtları oluşturuluyor...")
            ariza_basliklari = [
                "Yazıcı kağıt sıkıştırıyor", "Bilgisayar açılmıyor", "Ekran kırık", 
                "Tekerlek çıktı", "Mavi ekran hatası", "Projeksiyon lambası patlak",
                "Klima su akıtıyor", "İnternet bağlanmıyor", "Klavye tuşları basmıyor"
            ]
            durumlar = ['Beklemede', 'İşlemde', 'Parça Bekleniyor', 'Tamamlandı', 'Tamamlandı', 'İptal Edildi']
            
            for _ in range(15):
                secilen_demirbas = random.choice(tum_demirbaslar)
                secilen_durum = random.choice(durumlar)
                gecmis_zaman = datetime.now() - timedelta(days=random.randint(0, 30))
                
                ariza = Ariza(
                    baslik=random.choice(ariza_basliklari),
                    aciklama="Cihaz kullanım sırasında aniden bu hatayı verdi. Kontrol edilmesi gerekiyor.",
                    durum=secilen_durum,
                    tarih=gecmis_zaman,
                    demirbas_id=secilen_demirbas.id,
                    kullanici_id=admin.id
                    # 'bildiren' ve 'konum' ARTIK YOK. Modelden kaldırıldı.
                )
                db.session.add(ariza)
            
            db.session.commit()
            print("✅ 15 Arıza kaydı oluşturuldu.")
        else:
            print("ℹ️ Arıza verileri zaten var, atlanıyor.")

        print("\n🚀 TAMAMLANDI! Projeyi çalıştırıp test edebilirsin.")

if __name__ == "__main__":
    tam_veri_yukle()