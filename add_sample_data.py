import sqlite3
from datetime import datetime

conn = sqlite3.connect('demirbas.db')
cur = conn.cursor()

# Demirbaş ve Kullanıcı ID'lerini al
cur.execute('SELECT id FROM demirbas LIMIT 1')
row = cur.fetchone()
if not row:
    print("Hata: Demirbaş bulunamadı.")
    conn.close()
    exit()
d_id = row[0]

cur.execute('SELECT id FROM kullanici WHERE kullanici_adi="admin" LIMIT 1')
row = cur.fetchone()
if not row:
    print("Hata: Admin kullanıcısı bulunamadı.")
    conn.close()
    exit()
k_id = row[0]

# Örnek Arızaları Ekle
cur.execute("""
    INSERT INTO ariza (baslik, aciklama, durum, oncelik, konum, demirbas_id, kullanici_id, tarih) 
    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
""", ('İnternet Kablosu Kopuk', 'Oda girişindeki kablo ezilmiş.', 'Beklemede', 'Yüksek', 'Mmf Binası D-405', d_id, k_id))

cur.execute("""
    INSERT INTO ariza (baslik, aciklama, durum, oncelik, konum, demirbas_id, kullanici_id, tarih) 
    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
""", ('Klima Su Akıtıyor', 'Filtre temizliği gerekebilir.', 'İşlemde', 'Normal', 'Rektörlük 2. Kat', d_id, k_id))

conn.commit()
print("ÖRNEK VERİLER BAŞARIYLA EKLENDİ")
conn.close()
