from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
from datetime import datetime
import openpyxl
import io
import qrcode
import os  # <--- Hatanın çözümü: Bu import en üstte olmalı
from io import BytesIO
from openpyxl.styles import Font, Alignment, PatternFill
import os
import base64  # <--- YENİ EKLENDİ
from dotenv import load_dotenv

# --- KONFİGÜRASYON ---
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
    # Mevcut tablolara yeni sütunlar eklenmesi gerekirse buraya yazılır
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
    # Demirbaşlar Tablosu
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
    # Personeller Tablosu
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
    # YENİ TABLO: Yükleme Geçmişi
    conn.execute('''
        CREATE TABLE IF NOT EXISTS yukleme_gecmisi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_adi TEXT,
            hedef_konum TEXT,
            tur TEXT,
            tarih TEXT
        )
    ''')
    conn.commit()
    conn.close()
    veritabani_guncelle()

# Uygulama başlarken tabloları kontrol et
tablolari_olustur()

# --- ANA SAYFA ---
@app.route('/')
def index():
    # Genel Değişkenler
    aktif_tab = request.args.get('tab', 'demirbas')
    arama_terimi = request.args.get('q', '') 
    
    # İstatistik Filtreleri
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    
    # -- Demirbaş Filtreleri
    ist_malzeme = request.args.get('ist_malzeme', '')
    ist_kampus = request.args.get('ist_kampus', '')
    ist_konum = request.args.get('ist_konum', '')
    
    # -- Personel Filtreleri
    ist_p_ad = request.args.get('ist_p_ad', '')
    ist_p_birim = request.args.get('ist_p_birim', '')
    ist_p_kampus = request.args.get('ist_p_kampus', '')
    ist_p_ofis = request.args.get('ist_p_ofis', '')

    sayfa_d = request.args.get('sayfa_d', 1, type=int)
    sayfa_p = request.args.get('sayfa_p', 1, type=int)
    limit = 20
    offset_d = (sayfa_d - 1) * limit
    offset_p = (sayfa_p - 1) * limit

    conn = baglanti_kur()
    cur = conn.cursor()
    
    # 1. Demirbaş Listesi Sorgusu
    d_sql = "SELECT * FROM demirbaslar"
    d_c_sql = "SELECT COUNT(*) FROM demirbaslar"
    d_p = []
    if arama_terimi and aktif_tab == 'demirbas':
        t = f"%{turkce_normalize(arama_terimi)}%"
        f = " WHERE NORMALIZE(ad) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(kampus) LIKE ?"
        d_sql += f; d_c_sql += f; d_p = [t, t, t]
    
    cur.execute(d_c_sql, d_p)
    total_d = cur.fetchone()[0]
    total_pages_d = (total_d + limit - 1) // limit
    
    d_sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    d_p.extend([limit, offset_d])
    cur.execute(d_sql, d_p)
    demirbaslar = cur.fetchall()
    
    # 2. Personel Listesi Sorgusu
    p_sql = "SELECT * FROM personeller"
    p_c_sql = "SELECT COUNT(*) FROM personeller"
    p_p = []
    if arama_terimi and aktif_tab == 'personel':
        t = f"%{turkce_normalize(arama_terimi)}%"
        f = " WHERE NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(ofis) LIKE ? OR NORMALIZE(birimi) LIKE ?"
        p_sql += f; p_c_sql += f; p_p = [t, t, t]
    
    cur.execute(p_c_sql, p_p)
    total_p = cur.fetchone()[0]
    total_pages_p = (total_p + limit - 1) // limit
    
    p_sql += " ORDER BY ofis ASC LIMIT ? OFFSET ?"
    p_p.extend([limit, offset_p])
    cur.execute(p_sql, p_p)
    personeller = cur.fetchall()

    # 3. İstatistik & Analiz Sorguları
    analiz_sonuclari = []
    analiz_toplam = 0
    
    if aktif_tab == 'istatistik':
        if analiz_turu == 'personel':
            sql = "SELECT * FROM personeller WHERE 1=1"
            params = []
            if ist_p_ad:
                sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ?)"
                params.extend([f"%{turkce_normalize(ist_p_ad)}%", f"%{turkce_normalize(ist_p_ad)}%"])
            if ist_p_birim:
                sql += " AND NORMALIZE(birimi) LIKE ?"
                params.append(f"%{turkce_normalize(ist_p_birim)}%")
            if ist_p_kampus and ist_p_kampus != "Tümü":
                sql += " AND kampus = ?"
                params.append(ist_p_kampus)
            if ist_p_ofis:
                sql += " AND NORMALIZE(ofis) LIKE ?"
                params.append(f"%{turkce_normalize(ist_p_ofis)}%")
            
            sql += " ORDER BY birimi ASC, ad_soyad ASC"
            
            # Sadece filtre varsa çalıştır (Performans için)
            if ist_p_ad or ist_p_birim or (ist_p_kampus and ist_p_kampus != "Tümü") or ist_p_ofis:
                cur.execute(sql, params)
                analiz_sonuclari = cur.fetchall()
                analiz_toplam = len(analiz_sonuclari)

        else: # Demirbaş Analizi
            sql = "SELECT ad, kampus, konum, SUM(adet) as toplam_adet FROM demirbaslar WHERE 1=1"
            params = []
            if ist_malzeme:
                sql += " AND NORMALIZE(ad) LIKE ?"
                params.append(f"%{turkce_normalize(ist_malzeme)}%")
            if ist_kampus and ist_kampus != "Tümü":
                sql += " AND kampus = ?"
                params.append(ist_kampus)
            if ist_konum:
                sql += " AND NORMALIZE(konum) LIKE ?"
                params.append(f"%{turkce_normalize(ist_konum)}%")
            
            sql += " GROUP BY ad, kampus, konum ORDER BY kampus ASC, konum ASC"
            
            if ist_malzeme or (ist_kampus and ist_kampus != "Tümü") or ist_konum:
                cur.execute(sql, params)
                analiz_sonuclari = cur.fetchall()
                for row in analiz_sonuclari: analiz_toplam += row['toplam_adet']

    # 4. Son Yükleme Bilgisi
    try:
        cur.execute("SELECT * FROM yukleme_gecmisi ORDER BY id DESC LIMIT 1")
        son_yukleme = cur.fetchone()
    except:
        son_yukleme = None
    
    conn.close()
    
    return render_template('index.html', 
                           demirbaslar=demirbaslar, personeller=personeller, 
                           analiz_sonuclari=analiz_sonuclari, analiz_toplam=analiz_toplam, analiz_turu=analiz_turu,
                           yerleskeler=YERLESKELER, arama_terimi=arama_terimi, aktif_tab=aktif_tab,
                           sayfa_d=sayfa_d, toplam_sayfa_demirbas=total_pages_d,
                           sayfa_p=sayfa_p, toplam_sayfa_personel=total_pages_p,
                           ist_malzeme=ist_malzeme, ist_kampus=ist_kampus, ist_konum=ist_konum,
                           ist_p_ad=ist_p_ad, ist_p_birim=ist_p_birim, ist_p_kampus=ist_p_kampus, ist_p_ofis=ist_p_ofis,
                           son_yukleme=son_yukleme)

# --- YÜKLEME FONKSİYONLARI ---
@app.route('/yukle-demirbas', methods=['POST'])
def yukle_demirbas():
    if 'dosya' not in request.files: return redirect(url_for('index'))
    dosyalar = request.files.getlist('dosya')
    hedef_kampus = request.form.get('hedef_kampus', 'Merkez')
    bina_kat = request.form.get('bina_kat', '')

    conn = baglanti_kur()
    cur = conn.cursor()
    
    islem_yapildi = False

    for dosya in dosyalar:
        if dosya.filename == '': continue
        try:
            dosya_adi_temiz = dosya.filename.rsplit('.', 1)[0].replace('_', ' ').title()
            wb = openpyxl.load_workbook(dosya)
            for ws in wb.worksheets:
                parts = [p for p in [bina_kat, dosya_adi_temiz, ws.title] if p]
                tam_konum = " / ".join(parts)

                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or row[0] is None: continue
                    ad = row[0]; cinsi = row[1] if len(row)>1 else ""; adet = row[2] if len(row)>2 else 1
                    try: adet = int(adet)
                    except: adet = 1
                    
                    cur.execute("SELECT id FROM demirbaslar WHERE ad=? AND konum=?", (ad, tam_konum))
                    if not cur.fetchone():
                        cur.execute("INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) VALUES (?, ?, ?, ?, ?, ?)", 
                                    (ad, cinsi, hedef_kampus, tam_konum, adet, datetime.now().strftime("%Y-%m-%d")))
            islem_yapildi = True
        except Exception as e: print(f"Hata: {e}")

    if islem_yapildi and dosyalar:
        son_dosya = dosyalar[-1].filename
        tarih_saat = datetime.now().strftime("%d-%m-%Y %H:%M")
        cur.execute("INSERT INTO yukleme_gecmisi (dosya_adi, hedef_konum, tur, tarih) VALUES (?, ?, ?, ?)",
                    (son_dosya, bina_kat, "Demirbaş", tarih_saat))

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
                ad_soyad = row[0]
                unvan = row[1] if len(row)>1 else ""
                birim = row[2] if len(row)>2 else ""
                kampus = row[3] if len(row)>3 else "Merkez"
                ofis = row[4] if len(row)>4 else "Belirtilmedi"
                
                cur.execute("SELECT id FROM personeller WHERE ad_soyad=? AND ofis=?", (ad_soyad, ofis))
                if not cur.fetchone():
                    cur.execute("INSERT INTO personeller (ad_soyad, unvan, birimi, kampus, ofis) VALUES (?, ?, ?, ?, ?)", 
                                (ad_soyad, unvan, birim, kampus, ofis))
            
            # Log Kaydı
            tarih_saat = datetime.now().strftime("%d-%m-%Y %H:%M")
            cur.execute("INSERT INTO yukleme_gecmisi (dosya_adi, hedef_konum, tur, tarih) VALUES (?, ?, ?, ?)",
                        (dosya.filename, "Personel Listesi", "Personel", tarih_saat))
            
            conn.commit(); conn.close()
        except Exception: pass
    return redirect(url_for('index', tab='personel'))

# --- TEKİL İŞLEMLER (CRUD) ---
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

# --- DETAY VE RAPORLAMA ---
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
        ws1[f'A{i+1}'].font = Font(bold=True)

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

@app.route('/rapor-analiz')
def rapor_analiz():
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    
    # Filtreler
    ist_malzeme = request.args.get('ist_malzeme', '')
    ist_kampus = request.args.get('ist_kampus', '')
    ist_konum = request.args.get('ist_konum', '')
    ist_p_ad = request.args.get('ist_p_ad', '')
    ist_p_birim = request.args.get('ist_p_birim', '')
    ist_p_kampus = request.args.get('ist_p_kampus', '')
    ist_p_ofis = request.args.get('ist_p_ofis', '')

    conn = baglanti_kur()
    wb = openpyxl.Workbook()
    ws = wb.active
    
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="198754", fill_type="solid")
    total_font = Font(bold=True, color="000000")
    total_fill = PatternFill(start_color="FFC107", fill_type="solid")
    
    genel_toplam = 0

    if analiz_turu == 'personel':
        ws.title = "Personel Analiz Raporu"
        ws.append(['Sıra No', 'Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis'])
        
        sql = "SELECT * FROM personeller WHERE 1=1"
        params = []
        if ist_p_ad: sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ?)"; params.extend([f"%{turkce_normalize(ist_p_ad)}%", f"%{turkce_normalize(ist_p_ad)}%"])
        if ist_p_birim: sql += " AND NORMALIZE(birimi) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_birim)}%")
        if ist_p_kampus and ist_p_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_p_kampus)
        if ist_p_ofis: sql += " AND NORMALIZE(ofis) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_ofis)}%")
        sql += " ORDER BY birimi ASC, ad_soyad ASC"
        
        veriler = conn.execute(sql, params).fetchall()
        for i, row in enumerate(veriler, 1):
            ws.append([i, row['ad_soyad'], row['unvan'], row['birimi'], row['kampus'], row['ofis']])
            genel_toplam += 1

        ws.append(['', '', '', '', 'GENEL TOPLAM:', genel_toplam])
        last_row = ws.max_row
        ws[f'E{last_row}'].font = total_font; ws[f'E{last_row}'].fill = total_fill
        ws[f'F{last_row}'].font = total_font; ws[f'F{last_row}'].fill = total_fill

    else:
        ws.title = "Demirbaş Analiz Raporu"
        ws.append(['Sıra No', 'Malzeme Adı', 'Kampüs', 'Konum / Ofis', 'Adet'])
        
        sql = "SELECT ad, kampus, konum, SUM(adet) as toplam_adet FROM demirbaslar WHERE 1=1"
        params = []
        if ist_malzeme: sql += " AND NORMALIZE(ad) LIKE ?"; params.append(f"%{turkce_normalize(ist_malzeme)}%")
        if ist_kampus and ist_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_kampus)
        if ist_konum: sql += " AND NORMALIZE(konum) LIKE ?"; params.append(f"%{turkce_normalize(ist_konum)}%")
        sql += " GROUP BY ad, kampus, konum ORDER BY kampus ASC, konum ASC"
        
        veriler = conn.execute(sql, params).fetchall()
        for i, row in enumerate(veriler, 1):
            ws.append([i, row['ad'], row['kampus'], row['konum'], row['toplam_adet']])
            genel_toplam += row['toplam_adet']

        ws.append(['', '', '', 'GENEL TOPLAM:', genel_toplam])
        last_row = ws.max_row
        ws[f'D{last_row}'].font = total_font; ws[f'D{last_row}'].fill = total_fill
        ws[f'E{last_row}'].font = total_font; ws[f'E{last_row}'].fill = total_fill

    for cell in ws[1]:
        cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal='center')

    for column_cells in ws.columns:
        length = max(len(str(cell.value) or "") for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 3

    conn.close()
    output = io.BytesIO()
    wb.save(output); output.seek(0)
    dosya_adi = f"Analiz_Raporu_{analiz_turu}_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    return send_file(output, download_name=dosya_adi, as_attachment=True)

@app.route('/kapi-karti/<path:konum_adi>')
def kapi_karti(konum_adi):
    # QR Kodun yönleneceği adres (Ofis Detay Sayfası)
    hedef_url = url_for('ofis_detay', konum_adi=konum_adi, _external=True)
    
    # QR Kodu oluştur ve Base64 formatına çevir (Resim dosyası kaydetmeden direkt HTML'e gömmek için)
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(hedef_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Resmi bellekte tut ve HTML'e gönder
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return render_template('kapi_karti.html', konum=konum_adi, qr_code=qr_base64)

# --- ŞABLON İNDİRME FONKSİYONU ---
@app.route('/indir-sablon/<tur>')
def indir_sablon(tur):
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # Başlık Stili (Kalın Yazı)
    header_font = Font(bold=True)
    
    if tur == 'personel':
        # Başlıklar
        ws.append(['Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis'])
        # Örnek Veri (Kullanıcı ne yazacağını anlasın diye)
        ws.append(['Ahmet Yılmaz', 'Memur', 'Öğrenci İşleri', 'Merkez', 'Z-10'])
        ws.title = "Personel Listesi"
        filename = "sablon_personel_listesi.xlsx"
        
        # Sütun Genişlikleri
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 10

    else: # Demirbaş
        # Başlıklar
        ws.append(['Malzeme Adı', 'Cinsi', 'Adet'])
        # Örnek Veri
        ws.append(['Çalışma Masası', 'Ahşap', '1'])
        ws.title = "Demirbaş Listesi"
        filename = "sablon_demirbas_listesi.xlsx"
        
        # Sütun Genişlikleri
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 10

    # Başlıkları Kalın Yap
    for cell in ws[1]:
        cell.font = header_font

    # Dosyayı Belleğe Kaydet ve Gönder
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(output, download_name=filename, as_attachment=True)

if __name__ == '__main__':
    # host='0.0.0.0' dışarıdan erişime açar
    app.run(host='0.0.0.0', port=5000, debug=True)