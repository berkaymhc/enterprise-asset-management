import sqlite3
import os

# --- BURAYI KONTROL ET ---
# app.py içindeki veritabanı ismin neyse onu yaz (tırnaklar kalsın)
DB_ADI = 'demirbas.db' 
# -------------------------

if not os.path.exists(DB_ADI):
    print(f"HATA: '{DB_ADI}' isimli dosya bulunamadı! İsmi doğru yazdığına emin misin?")
else:
    print(f"'{DB_ADI}' bulundu, bağlanılıyor...")
    conn = sqlite3.connect(DB_ADI)
    cursor = conn.cursor()

    try:
        # Sütunu eklemeyi dene
        print("Sütun ekleniyor...")
        cursor.execute("ALTER TABLE arizalar ADD COLUMN demirbas_id INTEGER DEFAULT 0")
        conn.commit()
        print("✅ BAŞARILI! 'demirbas_id' sütunu veritabanına eklendi.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️ BİLGİ: Bu sütun zaten ekliymiş, tekrar eklenemez. Sorun yok.")
        else:
            print(f"❌ HATA OLUŞTU: {e}")
    finally:
        conn.close()