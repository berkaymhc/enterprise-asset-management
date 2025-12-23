from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
from datetime import datetime
import openpyxl
import io
import qrcode
from io import BytesIO
from openpyxl.styles import Font, Alignment, PatternFill
import os
from dotenv import load_dotenv

load_dotenv() # .env dosyasını yükler
DB_NAME = os.getenv("DB_NAME", "demirbas.db") # Bulamazsa varsayılanı kullanır

app = Flask(__name__)
app.secret_key = 'universite_gizli_anahtar'

YERLESKELER = [
    "Pelitli Yerleşkesi", "Ömer Yıldız Yerleşkesi", "Yomra Yerleşkesi", 
    "Yalıncak Yerleşkesi", "Çimenli Yerleşkesi"
]

# --- YARDIMCI FONKSİYONLAR ---
def turkce_normalize(metin):
    if metin is None: return ""
    degisim = {
        'İ': 'i', 'I': 'i', 'ı': 'i', 'Ş': 's', 'ş': 's',
        'Ç': 'c', 'ç': 'c', 'Ö': 'o', 'ö': 'o',
        'Ü': 'u', 'ü': 'u', 'Ğ': 'g', 'ğ': 'g'
    }
    yeni_metin = ""
    for harf in metin:
        yeni_metin += degisim.get(harf, harf)
    return yeni_metin.lower()

# --- VERİTABANI YÖNETİMİ ---
def baglanti_kur():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.create_function("NORMALIZE", 1, turkce_normalize)
    return conn

def veritabani_guncelle():
    conn = baglanti_kur()
    cur = conn.cursor()
    try: cur.execute("ALTER TABLE demirbaslar ADD COLUMN cinsi TEXT")
    except: pass
    try: cur.execute("ALTER TABLE demirbaslar ADD COLUMN kampus TEXT")
    except: pass
    try: cur.execute("ALTER TABLE demirbaslar ADD COLUMN personel TEXT")
    except: pass
    try: cur.execute("ALTER TABLE personeller ADD COLUMN birimi TEXT")
    except: pass
    conn.commit()
    conn.close()

def tablolari_olustur():
    conn = baglanti_kur()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS demirbaslar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            cinsi TEXT,
            kampus TEXT,
            konum TEXT NOT NULL,
            adet INTEGER NOT NULL,
            tarih TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS personeller (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            unvan TEXT,
            birimi TEXT,
            kampus TEXT,
            ofis TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    veritabani_guncelle()

tablolari_olustur()

# --- ANA SAYFA ---
@app.route('/')
def index():
    arama_terimi = request.args.get('q', '')
    aktif_tab = request.args.get('tab', 'demirbas')
    
    sayfa_d = request.args.get('sayfa_d', 1, type=int)
    sayfa_p = request.args.get('sayfa_p', 1, type=int)
    limit = 20
    offset_d = (sayfa_d - 1) * limit
    offset_p = (sayfa_p - 1) * limit

    conn = baglanti_kur()
    cur = conn.cursor()
    
    # Demirbaş Sorgusu
    d_sql = "SELECT * FROM demirbaslar"
    d_count_sql = "SELECT COUNT(*) FROM demirbaslar"
    d_params = []
    if arama_terimi:
        terim = f"%{turkce_normalize(arama_terimi)}%"
        filtre = " WHERE NORMALIZE(ad) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(kampus) LIKE ?"
        d_sql += filtre; d_count_sql += filtre; d_params = [terim, terim, terim]
    
    cur.execute(d_count_sql, d_params)
    toplam_demirbas = cur.fetchone()[0]
    toplam_sayfa_demirbas = (toplam_demirbas + limit - 1) // limit
    d_sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    d_params.extend([limit, offset_d])
    cur.execute(d_sql, d_params)
    demirbaslar = cur.fetchall()
    
    # Personel Sorgusu
    p_sql = "SELECT * FROM personeller"
    p_count_sql = "SELECT COUNT(*) FROM personeller"
    p_params = []
    if arama_terimi:
        terim = f"%{turkce_normalize(arama_terimi)}%"
        filtre = " WHERE NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(ofis) LIKE ? OR NORMALIZE(birimi) LIKE ?"
        p_sql += filtre; p_count_sql += filtre; p_params = [terim, terim, terim]

    cur.execute(p_count_sql, p_params)
    toplam_personel = cur.fetchone()[0]
    toplam_sayfa_personel = (toplam_personel + limit - 1) // limit
    p_sql += " ORDER BY ofis ASC LIMIT ? OFFSET ?"
    p_params.extend([limit, offset_p])
    cur.execute(p_sql, p_params)
    personeller = cur.fetchall()
    
    conn.close()
    return render_template('index.html', 
                           demirbaslar=demirbaslar, personeller=personeller, 
                           yerleskeler=YERLESKELER, arama_terimi=arama_terimi, aktif_tab=aktif_tab,
                           sayfa_d=sayfa_d, toplam_sayfa_demirbas=toplam_sayfa_demirbas,
                           sayfa_p=sayfa_p, toplam_sayfa_personel=toplam_sayfa_personel)

# --- YÜKLEME FONKSİYONLARI ---

@app.route('/yukle-demirbas', methods=['POST'])
def yukle_demirbas():
    if 'dosya' not in request.files: return redirect(url_for('index'))
    dosyalar = request.files.getlist('dosya')
    hedef_kampus = request.form.get('hedef_kampus', 'Merkez')
    bina_kat = request.form.get('bina_kat', '')

    conn = baglanti_kur()
    cur = conn.cursor()

    for dosya in dosyalar:
        if dosya.filename == '': continue
        try:
            dosya_adi_temiz = dosya.filename.rsplit('.', 1)[0].replace('_', ' ').title()
            wb = openpyxl.load_workbook(dosya)
            for ws in wb.worksheets:
                # KONUM OLUŞTURMA (DÜZELTİLEN KISIM: Araya Slash Koyduk)
                # Örnek: Yurtlar / Kat 1 / A101
                parts = [p for p in [bina_kat, dosya_adi_temiz, ws.title] if p]
                tam_konum = " / ".join(parts) # <-- BURASI DEĞİŞTİ (" - " yerine " / ")

                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or row[0] is None: continue
                    
                    ad = row[0]; cinsi = row[1] if len(row)>1 else ""; adet = row[2] if len(row)>2 else 1
                    try: adet = int(adet)
                    except: adet = 1
                    
                    # Çift Kayıt Kontrolü
                    cur.execute("SELECT id FROM demirbaslar WHERE ad=? AND konum=?", (ad, tam_konum))
                    if not cur.fetchone():
                        cur.execute("INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) VALUES (?, ?, ?, ?, ?, ?)", 
                                    (ad, cinsi, hedef_kampus, tam_konum, adet, datetime.now().strftime("%Y-%m-%d")))
        except Exception as e: print(f"Hata: {e}")

    conn.commit(); conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/yukle-personel', methods=['POST'])
def yukle_personel():
    if 'dosya' not in request.files: return redirect(url_for('index'))
    dosya = request.files['dosya']

    if dosya and dosya.filename != '':
        try:
            conn = baglanti_kur(); cur = conn.cursor()
            wb = openpyxl.load_workbook(dosya); ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or row[0] is None: continue
                ad_soyad = row[0]; unvan = row[1] if len(row)>1 else ""; birim = row[2] if len(row)>2 else ""
                kampus = row[3] if len(row)>3 else "Merkez"; ofis = row[4] if len(row)>4 else "Belirtilmedi"
                
                cur.execute("SELECT id FROM personeller WHERE ad_soyad=? AND ofis=?", (ad_soyad, ofis))
                if not cur.fetchone():
                    cur.execute("INSERT INTO personeller (ad_soyad, unvan, birimi, kampus, ofis) VALUES (?, ?, ?, ?, ?)", 
                                (ad_soyad, unvan, birim, kampus, ofis))
            conn.commit(); conn.close()
        except Exception: pass
    return redirect(url_for('index', tab='personel'))

# --- TEKİL İŞLEMLER ---
@app.route('/ekle-demirbas', methods=['POST'])
def ekle_demirbas():
    conn = baglanti_kur()
    conn.execute("INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) VALUES (?, ?, ?, ?, ?, ?)", 
                 (request.form['ad'], request.form['cinsi'], request.form['kampus'], request.form['konum'], request.form['adet'], datetime.now().strftime("%Y-%m-%d")))
    conn.commit(); conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/guncelle-demirbas', methods=['POST'])
def guncelle_demirbas():
    conn = baglanti_kur()
    conn.execute("UPDATE demirbaslar SET ad=?, cinsi=?, kampus=?, konum=?, adet=? WHERE id=?", 
                 (request.form['ad'], request.form['cinsi'], request.form['kampus'], request.form['konum'], request.form['adet'], request.form['id']))
    conn.commit(); conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/sil-demirbas/<int:id>')
def sil_demirbas(id):
    conn = baglanti_kur(); conn.execute("DELETE FROM demirbaslar WHERE id = ?", (id,)); conn.commit(); conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/ekle-personel', methods=['POST'])
def ekle_personel():
    conn = baglanti_kur()
    conn.execute("INSERT INTO personeller (ad_soyad, unvan, birimi, kampus, ofis) VALUES (?, ?, ?, ?, ?)", 
                 (request.form['ad_soyad'], request.form['unvan'], request.form['birimi'], request.form['kampus'], request.form['ofis']))
    conn.commit(); conn.close()
    return redirect(url_for('index', tab='personel'))

@app.route('/guncelle-personel', methods=['POST'])
def guncelle_personel():
    conn = baglanti_kur()
    conn.execute("UPDATE personeller SET ad_soyad=?, unvan=?, birimi=?, kampus=?, ofis=? WHERE id=?", 
                 (request.form['ad_soyad'], request.form['unvan'], request.form['birimi'], request.form['kampus'], request.form['ofis'], request.form['id']))
    conn.commit(); conn.close()
    return redirect(url_for('index', tab='personel'))

@app.route('/tasi-personel', methods=['POST'])
def tasi_personel():
    conn = baglanti_kur()
    conn.execute("UPDATE personeller SET kampus = ?, ofis = ? WHERE id = ?", (request.form['yeni_kampus'], request.form['yeni_ofis'], request.form['personel_id']))
    conn.commit(); conn.close()
    return redirect(url_for('index', tab='personel'))

@app.route('/sil-personel/<int:id>')
def sil_personel(id):
    conn = baglanti_kur(); conn.execute("DELETE FROM personeller WHERE id = ?", (id,)); conn.commit(); conn.close()
    return redirect(url_for('index', tab='personel'))

@app.route('/sifirla-demirbas')
def sifirla_demirbas():
    conn = baglanti_kur(); conn.execute("DELETE FROM demirbaslar"); conn.commit(); conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/sifirla-personel')
def sifirla_personel():
    conn = baglanti_kur(); conn.execute("DELETE FROM personeller"); conn.commit(); conn.close()
    return redirect(url_for('index', tab='personel'))

# --- DETAY SAYFALARI ---
@app.route('/personel-detay/<int:id>')
def personel_detay(id):
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT * FROM personeller WHERE id = ?", (id,)); kisi = cur.fetchone()
    if not kisi: return "Bulunamadı", 404
    cur.execute("SELECT * FROM personeller WHERE ofis = ? AND id != ?", (kisi['ofis'], id)); arkadaslar = cur.fetchall()
    k_ofis = turkce_normalize(kisi['ofis'])
    cur.execute("SELECT * FROM demirbaslar WHERE NORMALIZE(konum) LIKE ?", (f"%{k_ofis}%",)); esyalar = cur.fetchall()
    conn.close()
    return render_template('personel_detay.html', kisi=kisi, arkadaslar=arkadaslar, esyalar=esyalar)

@app.route('/ofis/<path:konum_adi>')
def ofis_detay(konum_adi):
    conn = baglanti_kur(); cur = conn.cursor()
    k_konum = turkce_normalize(konum_adi)
    cur.execute("SELECT * FROM demirbaslar WHERE NORMALIZE(konum) LIKE ?", (f"%{k_konum}%",)); esyalar = cur.fetchall()
    cur.execute("SELECT * FROM personeller WHERE NORMALIZE(ofis) LIKE ?", (f"%{k_konum}%",)); personeller = cur.fetchall()
    conn.close()
    return render_template('oda_detay.html', konum=konum_adi, esyalar=esyalar, personeller=personeller)

@app.route('/qr-olustur/<path:konum_adi>')
def qr_olustur(konum_adi):
    link = url_for('ofis_detay', konum_adi=konum_adi, _external=True)
    qr = qrcode.QRCode(box_size=10, border=4); qr.add_data(link); qr.make(fit=True)
    img_io = BytesIO(); qr.make_image(fill='black', back_color='white').save(img_io, 'PNG'); img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@app.route('/rapor')
def rapor():
    conn = baglanti_kur()
    wb = openpyxl.Workbook(); ws1 = wb.active; ws1.title = "Demirbaşlar"
    
    ws1.append(['Sıra No', 'Malzeme Adı', 'Cinsi', 'Kampüs', 'Konum', 'Adet', 'Kayıt Tarihi'])
    header_font = Font(bold=True, color="FFFFFF"); header_fill = PatternFill(start_color="4F81BD", fill_type="solid")
    for cell in ws1[1]: cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal='center')
    
    for i, row in enumerate(conn.execute("SELECT * FROM demirbaslar").fetchall(), 1):
        ws1.append([i, row['ad'], row['cinsi'], row['kampus'], row['konum'], row['adet'], row['tarih']])
        ws1[f'A{i+1}'].font = Font(bold=True) # Sıra No Kalın

    for column_cells in ws1.columns:
        length = max(len(str(cell.value) or "") for cell in column_cells)
        ws1.column_dimensions[column_cells[0].column_letter].width = length + 2

    ws2 = wb.create_sheet("Personeller")
    ws2.append(['Sıra No', 'Ad Soyad', 'Ünvan', 'Birimi', 'Kampüs', 'Ofis'])
    for cell in ws2[1]: cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal='center')

    for i, row in enumerate(conn.execute("SELECT * FROM personeller").fetchall(), 1):
        ws2.append([i, row['ad_soyad'], row['unvan'], row['birimi'], row['kampus'], row['ofis']])
        ws2[f'A{i+1}'].font = Font(bold=True)

    for column_cells in ws2.columns:
        length = max(len(str(cell.value) or "") for cell in column_cells)
        ws2.column_dimensions[column_cells[0].column_letter].width = length + 2

    conn.close(); output = io.BytesIO(); wb.save(output); output.seek(0)
    return send_file(output, download_name=f"Envanter_Rapor_{datetime.now().strftime('%Y-%m-%d')}.xlsx", as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)