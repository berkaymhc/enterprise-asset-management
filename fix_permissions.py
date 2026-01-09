from app import create_app, db
from app.models import Kullanici

app = create_app()

def yetkileri_duzelt():
    with app.app_context():
        print("🔧 YETKİLER DÜZENLENİYOR...\n")

        # 1. SORUMLU KULLANICIYI DÜZELT
        # Sorun: Rolü 'admin' olduğu için her yeri görüyor.
        # Çözüm: Rolünü 'personel' yapalım ama Yetki Düzeyi 2 (Yüksek) kalsın.
        sorumlu = Kullanici.query.filter_by(kullanici_adi='sorumlu').first()
        if sorumlu:
            sorumlu.rol = 'personel'  # Admin değil, personel sınıfında
            sorumlu.yetki_duzeyi = 2  # Ama yetkili bir personel (Birim Sorumlusu)
            print(f"✅ DÜZELTİLDİ: {sorumlu.ad_soyad} -> Rol: Personel, Yetki: 2 (Birim Sorumlusu)")
        else:
            print("⚠️ 'sorumlu' kullanıcısı bulunamadı.")

        # 2. TEKNİK SERVİSİ KONTROL ET
        teknik = Kullanici.query.filter_by(kullanici_adi='teknik').first()
        if teknik:
            teknik.rol = 'teknik'
            teknik.yetki_duzeyi = 1
            print(f"✅ KONTROL EDİLDİ: {teknik.ad_soyad} -> Rol: Teknik, Yetki: 1")

        # 3. STANDART PERSONELİ KONTROL ET
        personel = Kullanici.query.filter_by(kullanici_adi='personel').first()
        if personel:
            personel.rol = 'personel'
            personel.yetki_duzeyi = 0
            print(f"✅ KONTROL EDİLDİ: {personel.ad_soyad} -> Rol: Personel, Yetki: 0 (İzleyici)")

        # 4. ADMIN (PATRON) KONTROLÜ
        admin = Kullanici.query.filter_by(kullanici_adi='admin').first()
        if admin:
            admin.rol = 'admin'
            admin.yetki_duzeyi = 3
            print(f"✅ KONTROL EDİLDİ: {admin.ad_soyad} -> Rol: Admin, Yetki: 3 (Tam Yetki)")

        db.session.commit()
        print("\n🚀 İŞLEM TAMAM! Şimdi çıkış yapıp 'sorumlu' ile tekrar dene.")

if __name__ == "__main__":
    yetkileri_duzelt()