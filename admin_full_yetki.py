import sqlite3
import os

# Veritabanı dosyanın tam adını buraya yaz (önceki adımdan 'demirbas.db' olduğunu öğrenmiştik)
DB_ADI = 'demirbas.db'

if not os.path.exists(DB_ADI):
    print(f"HATA: '{DB_ADI}' bulunamadı!")
else:
    conn = sqlite3.connect(DB_ADI)
    cursor = conn.cursor()

    try:
        # admin kullanıcısını bul ve FULL YETKİ ver
        # yetki_duzeyi = 3 (En yüksek admin yetkisi)
        # rol = 'teknik' (Arıza butonlarını görebilmesi için geçici olarak teknik yapıyoruz)
        
        cursor.execute("""
            UPDATE kullanicilar 
            SET yetki_duzeyi = 3, rol = 'teknik' 
            WHERE kullanici_adi = 'admin'
        """)
        
        if cursor.rowcount > 0:
            print("✅ BAŞARILI: 'admin' kullanıcısı artık SÜPER YÖNETİCİ ve TEKNİK yetkili!")
        else:
            print("❌ HATA: 'admin' kullanıcısı bulunamadı. Kullanıcı adını kontrol et.")
            
        conn.commit()
        
    except Exception as e:
        print(f"Bir hata oluştu: {e}")
    finally:
        conn.close()