from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
import sqlite3
from datetime import datetime
import openpyxl
import io
import qrcode
import os
import base64
from io import BytesIO
from openpyxl.styles import Font, Alignment, PatternFill
from dotenv import load_dotenv

# --- KONFİGÜRASYON ---
load_dotenv()
DB_NAME = os.getenv("DB_NAME", "demirbas.db")

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

def baglanti_kur():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.create_function("NORMALIZE", 1, turkce_normalize)
    return conn

# --- MERKEZİ LOG SİSTEMİ ---
def log_kaydet(baslik, detay, tur="İşlem"):
    try:
        conn = baglanti_kur()
        cur = conn.cursor()
        tarih_saat = datetime.now().strftime("%d-%m-%Y %H:%M")
        cur.execute("INSERT INTO yukleme_gecmisi (dosya_adi, hedef_konum, tur, tarih) VALUES (?, ?, ?, ?)",
                    (baslik, detay, tur, tarih_saat))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log hatası: {e}")

# --- VERİTABANI KURULUMU ---
def tablolari_olustur():
    conn = baglanti_kur()
    conn.execute('''CREATE TABLE IF NOT EXISTS demirbaslar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL, cinsi TEXT, kampus TEXT, 
                    konum TEXT NOT NULL, adet INTEGER NOT NULL, tarih TEXT NOT NULL)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS personeller (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, ad_soyad TEXT NOT NULL, unvan TEXT, 
                    birimi TEXT, kampus TEXT, ofis TEXT NOT NULL)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS yukleme_gecmisi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, dosya_adi TEXT, hedef_konum TEXT, 
                    tur TEXT, tarih TEXT)''')
    
    # --- YENİ EKLENEN: ARIZALAR TABLOSU ---
    conn.execute('''CREATE TABLE IF NOT EXISTS arizalar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    konum TEXT NOT NULL,
                    baslik TEXT NOT NULL,
                    aciklama TEXT,
                    bildiren TEXT,
                    durum TEXT DEFAULT 'Bekliyor',
                    oncelik TEXT DEFAULT 'Normal',
                    tarih TEXT)''')
    
    conn.commit()
    conn.close()

tablolari_olustur()

# --- ANA SAYFA ---
@app.route('/')
def index():
    aktif_tab = request.args.get('tab', 'demirbas')
    arama_terimi = request.args.get('q', '') 
    
    # İstatistik Filtreleri
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    ist_malzeme = request.args.get('ist_malzeme', '')
    ist_kampus = request.args.get('ist_kampus', '')
    ist_konum = request.args.get('ist_konum', '')
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
    
    # 1. Demirbaş Listesi
    d_sql = "SELECT * FROM demirbaslar"
    d_c_sql = "SELECT COUNT(*) FROM demirbaslar"
    d_p = []
    if arama_terimi and aktif_tab == 'demirbas':
        t = f"%{turkce_normalize(arama_terimi)}%"
        f = " WHERE NORMALIZE(ad) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(kampus) LIKE ?"
        d_sql += f; d_c_sql += f; d_p = [t, t, t]
    
    cur.execute(d_c_sql, d_p); total_d = cur.fetchone()[0]
    total_pages_d = (total_d + limit - 1) // limit
    d_sql += " ORDER BY id DESC LIMIT ? OFFSET ?"; d_p.extend([limit, offset_d])
    cur.execute(d_sql, d_p); demirbaslar = cur.fetchall()
    
    # 2. Personel Listesi
    p_sql = "SELECT * FROM personeller"
    p_c_sql = "SELECT COUNT(*) FROM personeller"
    p_p = []
    if arama_terimi and aktif_tab == 'personel':
        t = f"%{turkce_normalize(arama_terimi)}%"
        f = " WHERE NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(ofis) LIKE ? OR NORMALIZE(birimi) LIKE ?"
        p_sql += f; p_c_sql += f; p_p = [t, t, t]
    
    cur.execute(p_c_sql, p_p); total_p = cur.fetchone()[0]
    total_pages_p = (total_p + limit - 1) // limit
    p_sql += " ORDER BY ofis ASC LIMIT ? OFFSET ?"; p_p.extend([limit, offset_p])
    cur.execute(p_sql, p_p); personeller = cur.fetchall()

    # 3. İstatistik & Analiz
    analiz_sonuclari = []; analiz_toplam = 0
    f_labels_1 = []; f_values_1 = []
    f_labels_2 = []; f_values_2 = []

    if aktif_tab == 'istatistik':
        if analiz_turu == 'personel':
            sql = "SELECT * FROM personeller WHERE 1=1"
            params = []
            if ist_p_ad: sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ?)"; params.extend([f"%{turkce_normalize(ist_p_ad)}%", f"%{turkce_normalize(ist_p_ad)}%"])
            if ist_p_birim: sql += " AND NORMALIZE(birimi) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_birim)}%")
            if ist_p_kampus and ist_p_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_p_kampus)
            if ist_p_ofis: sql += " AND NORMALIZE(ofis) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_ofis)}%")
            sql += " ORDER BY birimi ASC, ad_soyad ASC"
            
            if ist_p_ad or ist_p_birim or (ist_p_kampus and ist_p_kampus != "Tümü") or ist_p_ofis:
                cur.execute(sql, params); analiz_sonuclari = cur.fetchall(); analiz_toplam = len(analiz_sonuclari)
                
                temp_kampus = {}; temp_unvan = {}
                for row in analiz_sonuclari:
                    k = row['kampus'] if row['kampus'] else "Belirtilmedi"
                    temp_kampus[k] = temp_kampus.get(k, 0) + 1
                    u = row['unvan'] if row['unvan'] else "Diğer"
                    temp_unvan[u] = temp_unvan.get(u, 0) + 1
                f_labels_1 = list(temp_kampus.keys()); f_values_1 = list(temp_kampus.values())
                f_labels_2 = list(temp_unvan.keys()); f_values_2 = list(temp_unvan.values())

        else: # Demirbaş
            sql = "SELECT ad, kampus, konum, SUM(adet) as toplam_adet FROM demirbaslar WHERE 1=1"
            params = []
            if ist_malzeme: sql += " AND NORMALIZE(ad) LIKE ?"; params.append(f"%{turkce_normalize(ist_malzeme)}%")
            if ist_kampus and ist_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_kampus)
            if ist_konum: sql += " AND NORMALIZE(konum) LIKE ?"; params.append(f"%{turkce_normalize(ist_konum)}%")
            sql += " GROUP BY ad, kampus, konum ORDER BY kampus ASC, konum ASC"
            
            if ist_malzeme or (ist_kampus and ist_kampus != "Tümü") or ist_konum:
                cur.execute(sql, params); analiz_sonuclari = cur.fetchall()
                for row in analiz_sonuclari: analiz_toplam += row['toplam_adet']
                
                temp_kampus = {}; temp_konum = {}
                for row in analiz_sonuclari:
                    k = row['kampus']
                    temp_kampus[k] = temp_kampus.get(k, 0) + row['toplam_adet']
                    try: loc = row['konum'].split('/')[1].strip() 
                    except: loc = row['konum'][:15]
                    temp_konum[loc] = temp_konum.get(loc, 0) + row['toplam_adet']
                f_labels_1 = list(temp_kampus.keys()); f_values_1 = list(temp_kampus.values())
                sorted_locs = sorted(temp_konum.items(), key=lambda item: item[1], reverse=True)[:8]
                f_labels_2 = [x[0] for x in sorted_locs]; f_values_2 = [x[1] for x in sorted_locs]

    # 4. LOG YÖNETİMİ
    cur.execute("SELECT * FROM yukleme_gecmisi WHERE tur = 'Yükleme' ORDER BY id DESC LIMIT 1")
    son_yukleme = cur.fetchone()
    cur.execute("SELECT * FROM yukleme_gecmisi ORDER BY id DESC LIMIT 100")
    tum_gecmis = cur.fetchall()

    # 5. GENEL DASHBOARD
    # Grafik 1: Kampüs
    cur.execute("SELECT kampus, SUM(adet) FROM demirbaslar GROUP BY kampus")
    kampus_grafik_veri = cur.fetchall()
    chart_kampus_labels = [row[0] for row in kampus_grafik_veri if row[0]]
    chart_kampus_values = [row[1] for row in kampus_grafik_veri if row[1]]

    # Grafik 2: Malzeme (Top 10)
    cur.execute("SELECT ad, SUM(adet) FROM demirbaslar GROUP BY ad ORDER BY SUM(adet) DESC LIMIT 10")
    esya_grafik_veri = cur.fetchall()
    chart_esya_labels = [row[0] for row in esya_grafik_veri if row[0]]
    chart_esya_values = [row[1] for row in esya_grafik_veri if row[1]]

    # Grafik 3: Personel
    cur.execute("SELECT birimi, COUNT(*) FROM personeller GROUP BY birimi ORDER BY COUNT(*) DESC LIMIT 8")
    personel_grafik_veri = cur.fetchall()
    chart_personel_labels = [row[0] for row in personel_grafik_veri if row[0]]
    chart_personel_values = [row[1] for row in personel_grafik_veri if row[1]]

    # Grafik 4: Malzeme Cinsi
    cur.execute("SELECT cinsi, SUM(adet) FROM demirbaslar GROUP BY cinsi")
    tur_grafik_veri = cur.fetchall()
    chart_tur_labels = []
    chart_tur_values = []
    for row in tur_grafik_veri:
        tur_adi = row['cinsi'] if row['cinsi'] and row['cinsi'].strip() != "" else "Belirtilmedi"
        chart_tur_labels.append(tur_adi)
        chart_tur_values.append(row[1])

    # --- YENİ EKLENEN: ARIZA VERİLERİNİ ÇEK ---
    cur.execute("SELECT * FROM arizalar ORDER BY id DESC")
    arizalar = cur.fetchall()
    
    cur.execute("SELECT COUNT(*) FROM arizalar WHERE durum='Bekliyor'")
    bekleyen_ariza_sayisi = cur.fetchone()[0]

    conn.close() 

    return render_template('index.html', 
                           demirbaslar=demirbaslar, personeller=personeller, yerleskeler=YERLESKELER,
                           aktif_tab=aktif_tab, sayfa_d=sayfa_d, sayfa_p=sayfa_p,
                           toplam_sayfa_demirbas=total_pages_d, toplam_sayfa_personel=total_pages_p,
                           arama_terimi=arama_terimi, son_yukleme=son_yukleme, tum_gecmis=tum_gecmis,
                           analiz_sonuclari=analiz_sonuclari, analiz_toplam=analiz_toplam,
                           analiz_turu=analiz_turu, ist_malzeme=ist_malzeme, ist_kampus=ist_kampus,
                           ist_konum=ist_konum, ist_p_ad=ist_p_ad, ist_p_birim=ist_p_birim,
                           ist_p_kampus=ist_p_kampus, ist_p_ofis=ist_p_ofis,
                           chart_kampus_labels=chart_kampus_labels, chart_kampus_values=chart_kampus_values,
                           chart_esya_labels=chart_esya_labels, chart_esya_values=chart_esya_values,
                           chart_personel_labels=chart_personel_labels, chart_personel_values=chart_personel_values,
                           chart_tur_labels=chart_tur_labels, chart_tur_values=chart_tur_values,
                           f_labels_1=f_labels_1, f_values_1=f_values_1,
                           f_labels_2=f_labels_2, f_values_2=f_values_2,
                           # YENİLER
                           arizalar=arizalar, bekleyen_ariza_sayisi=bekleyen_ariza_sayisi)

# --- YÜKLEME VE İŞLEM FONKSİYONLARI ---
@app.route('/yukle-demirbas', methods=['POST'])
def yukle_demirbas():
    if 'dosya' not in request.files: return redirect(url_for('index'))
    dosyalar = request.files.getlist('dosya')
    hedef_kampus = request.form.get('hedef_kampus', 'Merkez')
    bina_kat = request.form.get('bina_kat', '')
    conn = baglanti_kur(); cur = conn.cursor(); islem_yapildi = False

    for dosya in dosyalar:
        if dosya.filename == '': continue
        try:
            dosya_adi_temiz = dosya.filename.rsplit('.', 1)[0].replace('_', ' ').title()
            wb = openpyxl.load_workbook(dosya)
            for ws in wb.worksheets:
                tam_konum = " / ".join([p for p in [bina_kat, dosya_adi_temiz, ws.title] if p])
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
        except Exception: pass
    conn.commit(); conn.close()
    if islem_yapildi: log_kaydet(f"{len(dosyalar)} Dosya Yüklendi", f"{bina_kat}", "Yükleme")
    return redirect(url_for('index', tab='demirbas'))

# --- AKILLI KLASÖR YÜKLEME FONKSİYONU ---
@app.route('/yukle-klasor', methods=['POST'])
def yukle_klasor():
    if 'dosya' not in request.files: return redirect(url_for('index'))
    dosyalar = request.files.getlist('dosya')
    hedef_kampus = request.form.get('hedef_kampus', 'Merkez')
    
    conn = baglanti_kur()
    cur = conn.cursor()
    islem_sayisi = 0
    kaydedilen_yerler = set()

    # --- YARDIMCI: TÜRKÇE BÜYÜTME VE BAŞLIKLANDIRMA ---
    def tr_upper(text):
        return text.replace('i', 'İ').replace('ı', 'I').upper()

    def tr_title(text):
        kelimeler = text.split()
        yeni_kelimeler = []
        for kelime in kelimeler:
            if not kelime: continue
            ilk = kelime[0]
            kalan = kelime[1:].replace('I', 'ı').replace('İ', 'i').lower()
            yeni_kelimeler.append(ilk + kalan)
        return " ".join(yeni_kelimeler)

    SILINECEK_KELIMELER = [
        "LİSTESİ", "LISTESI", "LİSTE", "LISTE", 
        "DEMİRBAŞLARI", "DEMİRBAŞ", "DEMIRBAS", "ENVANTER", "SAYIM",
        "SİSTEMİ", "SISTEMI", "YAPILDI", "YAPILAN", "YENİ", "ESKİ", 
        "COPY", "KOPYA", "YEDEK", "REVİZE", "REVIZE",
        "DÜZENLEME", "DÜZENLENEN", "KONTROL", "TASLAK", "SON", "FİNAL", "FINAL",
        "MASAÜSTÜ", "DOWNLOADS", "BELGELERİM", "TABLO", "TÜMÜ", "TUMU",
        "YALINCAK", "PELİTLİ", "KANUNİ", "MERKEZ", "YERLEŞKESİ", "YERLESKESI"
    ]

    ONEMLI_KELIMELER = [
        "BLOK", "KAT", "ODA", "BİNA", "BINA", "YURT", "OFİS", "OFFICE", 
        "HALL", "SALON", "LAB", "DEPO", "ZEMİN", "GİRİŞ", "SİSTEM", "KAZAN",
        "RESTORAN", "YEMEKHANE", "KANTİN", "LOBİ", "MESCİT", "GUVENLIK", "GÜVENLİK",
        "AMBAR", "ATÖLYE", "ARŞİV", "LİSE", "FAKÜLTE", "MYO", "MEMUR", "PERSONEL",
        "PATOLOJİ", "KLİNİK", "POLİKLİNİK", "SERVİS", "BÖLÜM", "BOLUM", "BİRİM", "LABORATUVAR"
    ]

    for dosya in dosyalar:
        if not dosya.filename.endswith('.xlsx') or '~$' in dosya.filename:
            continue
            
        try:
            full_path = dosya.filename.replace('\\', '/')
            path_parts = full_path.split('/')
            
            dosya_adi_ham = path_parts[-1].rsplit('.', 1)[0]
            tum_parcalar = path_parts[:-1] + [dosya_adi_ham]
            
            anlamli_yol_parcalari = []

            for parca in tum_parcalar:
                temiz_parca = tr_upper(parca)
                for yasakli in SILINECEK_KELIMELER:
                    temiz_parca = temiz_parca.replace(yasakli, "")
                
                temiz_parca = temiz_parca.replace("_", " ").replace("-", " ").strip()
                if len(temiz_parca) < 3 and not any(c.isdigit() for c in temiz_parca):
                    continue

                is_onemli = any(k in temiz_parca for k in ONEMLI_KELIMELER)
                is_blok_kodu = (len(temiz_parca) > 0 and len(temiz_parca) < 6 and any(c.isdigit() for c in temiz_parca))
                
                if (is_onemli or is_blok_kodu or len(temiz_parca) > 3):
                    temiz_parca_title = tr_title(temiz_parca)
                    if anlamli_yol_parcalari:
                        son_eklenen = anlamli_yol_parcalari[-1]
                        if temiz_parca_title in son_eklenen or son_eklenen in temiz_parca_title:
                            if len(temiz_parca_title) > len(son_eklenen):
                                anlamli_yol_parcalari[-1] = temiz_parca_title
                            continue 
                    
                    anlamli_yol_parcalari.append(temiz_parca_title)

            temiz_yol_str = " / ".join(anlamli_yol_parcalari)

            wb = openpyxl.load_workbook(dosya)
            
            for ws in wb.worksheets:
                sheet_adi = ws.title.strip()
                if "Sheet" in sheet_adi or "Sayfa" in sheet_adi:
                    tam_konum = temiz_yol_str if temiz_yol_str else "Genel"
                else:
                    if temiz_yol_str:
                        if sheet_adi in temiz_yol_str:
                            tam_konum = temiz_yol_str
                        else:
                            tam_konum = f"{temiz_yol_str} / {sheet_adi}"
                    else:
                        tam_konum = sheet_adi 

                if len(tam_konum) > 150: tam_konum = tam_konum[:147] + "..."
                kaydedilen_yerler.add(tam_konum)

                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or row[0] is None: continue
                    ad = row[0]; cinsi = row[1] if len(row)>1 else ""; adet = row[2] if len(row)>2 else 1
                    try: adet = int(adet)
                    except: adet = 1
                    cur.execute("SELECT id FROM demirbaslar WHERE ad=? AND konum=?", (ad, tam_konum))
                    if not cur.fetchone():
                        cur.execute("INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) VALUES (?, ?, ?, ?, ?, ?)", 
                                    (ad, cinsi, hedef_kampus, tam_konum, adet, datetime.now().strftime("%Y-%m-%d")))
            
            islem_sayisi += 1

        except Exception as e:
            print(f"Hata ({dosya.filename}): {e}")

    if islem_sayisi > 0:
        aciklama = f"Toplu Klasör ({islem_sayisi} dosya)"
        konum_ozeti = f"{hedef_kampus} - Karışık"
        if len(kaydedilen_yerler) > 0:
            ornek = list(kaydedilen_yerler)[0]
            konum_ozeti = f"{hedef_kampus} / {ornek}"
        log_kaydet(aciklama, konum_ozeti, "Yükleme")

    conn.commit()
    conn.close()
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
                cur.execute("SELECT id FROM personeller WHERE ad_soyad=? AND ofis=?", (row[0], row[4] if len(row)>4 else ""))
                if not cur.fetchone():
                    cur.execute("INSERT INTO personeller (ad_soyad, unvan, birimi, kampus, ofis) VALUES (?, ?, ?, ?, ?)", 
                                (row[0], row[1] if len(row)>1 else "", row[2] if len(row)>2 else "", row[3] if len(row)>3 else "Merkez", row[4] if len(row)>4 else ""))
            conn.commit(); conn.close()
            log_kaydet(f"Personel Listesi Yüklendi", dosya.filename, "Yükleme")
        except Exception: pass
    return redirect(url_for('index', tab='personel'))

# --- CRUD İŞLEMLERİ ---
@app.route('/ekle-demirbas', methods=['POST'])
def ekle_demirbas():
    conn = baglanti_kur()
    conn.execute("INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) VALUES (?, ?, ?, ?, ?, ?)", 
                 (request.form['ad'], request.form['cinsi'], request.form['kampus'], request.form['konum'], request.form['adet'], datetime.now().strftime("%Y-%m-%d")))
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad']} Eklendi", f"Konum: {request.form['konum']}", "Ekleme")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/guncelle-demirbas', methods=['POST'])
def guncelle_demirbas():
    conn = baglanti_kur()
    conn.execute("UPDATE demirbaslar SET ad=?, cinsi=?, kampus=?, konum=?, adet=? WHERE id=?", 
                 (request.form['ad'], request.form['cinsi'], request.form['kampus'], request.form['konum'], request.form['adet'], request.form['id']))
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad']} Güncellendi", f"Yeni Konum: {request.form['konum']}", "Düzenleme")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/sil-demirbas/<int:id>')
def sil_demirbas(id):
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT ad, konum FROM demirbaslar WHERE id=?", (id,)); kayit = cur.fetchone()
    if kayit:
        log_kaydet(f"{kayit['ad']} Silindi", f"Eski Konum: {kayit['konum']}", "Silme")
        cur.execute("DELETE FROM demirbaslar WHERE id=?", (id,)); conn.commit()
    conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/ekle-personel', methods=['POST'])
def ekle_personel():
    conn = baglanti_kur()
    conn.execute("INSERT INTO personeller (ad_soyad, unvan, birimi, kampus, ofis) VALUES (?, ?, ?, ?, ?)", 
                 (request.form['ad_soyad'], request.form['unvan'], request.form['birimi'], request.form['kampus'], request.form['ofis']))
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad_soyad']} Eklendi", f"Ofis: {request.form['ofis']}", "Ekleme")
    return redirect(url_for('index', tab='personel'))

@app.route('/guncelle-personel', methods=['POST'])
def guncelle_personel():
    conn = baglanti_kur()
    conn.execute("UPDATE personeller SET ad_soyad=?, unvan=?, birimi=?, kampus=?, ofis=? WHERE id=?", 
                 (request.form['ad_soyad'], request.form['unvan'], request.form['birimi'], request.form['kampus'], request.form['ofis'], request.form['id']))
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad_soyad']} Güncellendi", f"Ofis: {request.form['ofis']}", "Düzenleme")
    return redirect(url_for('index', tab='personel'))

@app.route('/tasi-personel', methods=['POST'])
def tasi_personel():
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT ad_soyad, ofis, kampus FROM personeller WHERE id=?", (request.form['personel_id'],)); kisi = cur.fetchone()
    conn.execute("UPDATE personeller SET kampus = ?, ofis = ? WHERE id = ?", (request.form['yeni_kampus'], request.form['yeni_ofis'], request.form['personel_id']))
    conn.commit(); conn.close()
    if kisi: log_kaydet(f"{kisi['ad_soyad']} Taşındı", f"{kisi['kampus']}/{kisi['ofis']} -> {request.form['yeni_kampus']}/{request.form['yeni_ofis']}", "Taşıma")
    return redirect(url_for('index', tab='personel'))

@app.route('/sil-personel/<int:id>')
def sil_personel(id):
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT ad_soyad, ofis FROM personeller WHERE id=?", (id,)); kayit = cur.fetchone()
    if kayit:
        log_kaydet(f"{kayit['ad_soyad']} Silindi", f"Eski Ofis: {kayit['ofis']}", "Silme")
        cur.execute("DELETE FROM personeller WHERE id=?", (id,)); conn.commit()
    conn.close()
    return redirect(url_for('index', tab='personel'))

@app.route('/sifirla-demirbas')
def sifirla_demirbas():
    conn = baglanti_kur(); conn.execute("DELETE FROM demirbaslar"); conn.commit(); conn.close()
    log_kaydet("Tüm Demirbaş Listesi Silindi", "Veritabanı Sıfırlama", "Sıfırlama")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/sifirla-personel')
def sifirla_personel():
    conn = baglanti_kur(); conn.execute("DELETE FROM personeller"); conn.commit(); conn.close()
    log_kaydet("Tüm Personel Listesi Silindi", "Veritabanı Sıfırlama", "Sıfırlama")
    return redirect(url_for('index', tab='personel'))

# --- DİĞER FONKSİYONLAR ---
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

@app.route('/kapi-karti/<path:konum_adi>')
def kapi_karti(konum_adi):
    hedef_url = url_for('ofis_detay', konum_adi=konum_adi, _external=True)
    qr = qrcode.QRCode(box_size=10, border=2); qr.add_data(hedef_url); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO(); img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    log_kaydet("Kapı Kartı Görüntülendi", f"Ofis: {konum_adi}", "Yazdırma")
    return render_template('kapi_karti.html', konum=konum_adi, qr_code=qr_base64)

@app.route('/indir-sablon/<tur>')
def indir_sablon(tur):
    wb = openpyxl.Workbook(); ws = wb.active; header_font = Font(bold=True)
    if tur == 'personel':
        ws.append(['Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis'])
        ws.append(['Ahmet Yılmaz', 'Memur', 'Öğrenci İşleri', 'Merkez', 'Z-10'])
        ws.title = "Personel Listesi"; filename = "sablon_personel_listesi.xlsx"
    else:
        ws.append(['Malzeme Adı', 'Cinsi', 'Adet'])
        ws.append(['Çalışma Masası', 'Ahşap', '1'])
        ws.title = "Demirbaş Listesi"; filename = "sablon_demirbas_listesi.xlsx"
    for cell in ws[1]: cell.font = header_font
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return send_file(output, download_name=filename, as_attachment=True)

@app.route('/rapor')
def rapor():
    conn = baglanti_kur()
    wb = openpyxl.Workbook(); ws1 = wb.active; ws1.title = "Demirbaşlar"
    ws1.append(['Sıra No', 'Malzeme Adı', 'Cinsi', 'Kampüs', 'Konum', 'Adet', 'Kayıt Tarihi'])
    header_font = Font(bold=True, color="FFFFFF"); header_fill = PatternFill(start_color="4F81BD", fill_type="solid")
    for cell in ws1[1]: cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal='center')
    for i, row in enumerate(conn.execute("SELECT * FROM demirbaslar").fetchall(), 1):
        ws1.append([i, row['ad'], row['cinsi'], row['kampus'], row['konum'], row['adet'], row['tarih']])
        
    ws2 = wb.create_sheet("Personeller")
    ws2.append(['Sıra No', 'Ad Soyad', 'Ünvan', 'Birimi', 'Kampüs', 'Ofis'])
    for cell in ws2[1]: cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal='center')
    for i, row in enumerate(conn.execute("SELECT * FROM personeller").fetchall(), 1):
        ws2.append([i, row['ad_soyad'], row['unvan'], row['birimi'], row['kampus'], row['ofis']])

    conn.close(); output = io.BytesIO(); wb.save(output); output.seek(0)
    log_kaydet("Excel Raporu İndirildi", "Tüm Envanter", "Rapor")
    return send_file(output, download_name=f"Envanter_Rapor_{datetime.now().strftime('%Y-%m-%d')}.xlsx", as_attachment=True)

@app.route('/rapor-analiz')
def rapor_analiz():
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    ist_malzeme = request.args.get('ist_malzeme', ''); ist_kampus = request.args.get('ist_kampus', ''); ist_konum = request.args.get('ist_konum', '')
    ist_p_ad = request.args.get('ist_p_ad', ''); ist_p_birim = request.args.get('ist_p_birim', '')
    ist_p_kampus = request.args.get('ist_p_kampus', ''); ist_p_ofis = request.args.get('ist_p_ofis', '')

    conn = baglanti_kur(); wb = openpyxl.Workbook(); ws = wb.active
    header_font = Font(bold=True, color="FFFFFF"); header_fill = PatternFill(start_color="198754", fill_type="solid")
    total_font = Font(bold=True, color="000000"); total_fill = PatternFill(start_color="FFC107", fill_type="solid")
    genel_toplam = 0

    if analiz_turu == 'personel':
        ws.title = "Personel Analiz"; ws.append(['Sıra No', 'Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis'])
        sql = "SELECT * FROM personeller WHERE 1=1"
        params = []
        if ist_p_ad: sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ?)"; params.extend([f"%{turkce_normalize(ist_p_ad)}%", f"%{turkce_normalize(ist_p_ad)}%"])
        if ist_p_birim: sql += " AND NORMALIZE(birimi) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_birim)}%")
        if ist_p_kampus and ist_p_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_p_kampus)
        if ist_p_ofis: sql += " AND NORMALIZE(ofis) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_ofis)}%")
        sql += " ORDER BY birimi ASC, ad_soyad ASC"
        for i, row in enumerate(conn.execute(sql, params).fetchall(), 1):
            ws.append([i, row['ad_soyad'], row['unvan'], row['birimi'], row['kampus'], row['ofis']]); genel_toplam += 1
        ws.append(['', '', '', '', 'GENEL TOPLAM:', genel_toplam])
    else:
        ws.title = "Demirbaş Analiz"; ws.append(['Sıra No', 'Malzeme Adı', 'Kampüs', 'Konum / Ofis', 'Adet'])
        sql = "SELECT ad, kampus, konum, SUM(adet) as toplam_adet FROM demirbaslar WHERE 1=1"
        params = []
        if ist_malzeme: sql += " AND NORMALIZE(ad) LIKE ?"; params.append(f"%{turkce_normalize(ist_malzeme)}%")
        if ist_kampus and ist_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_kampus)
        if ist_konum: sql += " AND NORMALIZE(konum) LIKE ?"; params.append(f"%{turkce_normalize(ist_konum)}%")
        sql += " GROUP BY ad, kampus, konum ORDER BY kampus ASC, konum ASC"
        for i, row in enumerate(conn.execute(sql, params).fetchall(), 1):
            ws.append([i, row['ad'], row['kampus'], row['konum'], row['toplam_adet']]); genel_toplam += row['toplam_adet']
        ws.append(['', '', '', 'GENEL TOPLAM:', genel_toplam])

    for cell in ws[1]: cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal='center')
    conn.close(); output = io.BytesIO(); wb.save(output); output.seek(0)
    return send_file(output, download_name=f"Analiz_Raporu_{analiz_turu}.xlsx", as_attachment=True)

@app.route('/rapor-grafik-ozet')
def rapor_grafik_ozet():
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    
    # Filtreleri Al
    ist_malzeme = request.args.get('ist_malzeme', '')
    ist_kampus = request.args.get('ist_kampus', '')
    ist_konum = request.args.get('ist_konum', '')
    ist_p_ad = request.args.get('ist_p_ad', '')
    ist_p_birim = request.args.get('ist_p_birim', '')
    ist_p_kampus = request.args.get('ist_p_kampus', '')
    ist_p_ofis = request.args.get('ist_p_ofis', '')

    conn = baglanti_kur()
    wb = openpyxl.Workbook()
    
    # Stil Tanımları
    baslik_font = Font(bold=True, size=12, color="000000")
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="198754", fill_type="solid") # Yeşil Başlık
    bilgi_font = Font(italic=True, color="555555")

    # --- 1. SAYFA: KAMPÜS DAĞILIMI ---
    ws1 = wb.active
    ws1.title = "Kampüs Dağılımı"

    # Arama Bilgilerini Yazdır (Raporun Tepesine)
    ws1.append(['RAPOR BİLGİLERİ'])
    ws1['A1'].font = baslik_font
    
    if analiz_turu == 'personel':
        bilgiler = [
            f"Analiz Türü: Personel",
            f"Aranan İsim/Ünvan: {ist_p_ad if ist_p_ad else 'Tümü'}",
            f"Birim: {ist_p_birim if ist_p_birim else 'Tümü'}",
            f"Kampüs: {ist_p_kampus if ist_p_kampus else 'Tümü'}",
            f"Ofis: {ist_p_ofis if ist_p_ofis else 'Tümü'}"
        ]
    else:
        bilgiler = [
            f"Analiz Türü: Demirbaş",
            f"Aranan Malzeme: {ist_malzeme if ist_malzeme else 'Tümü'}",
            f"Kampüs: {ist_kampus if ist_kampus else 'Tümü'}",
            f"Konum/Bina: {ist_konum if ist_konum else 'Tümü'}"
        ]

    for bilgi in bilgiler:
        ws1.append([bilgi])
        ws1.cell(row=ws1.max_row, column=1).font = bilgi_font

    ws1.append([]) # Boş satır
    ws1.append(['Kampüs Adı', 'Sayı (Adet/Kişi)']) # Tablo Başlığı
    
    # Başlık Stilini Uygula (Satır sayısı dinamik olduğu için hesaplıyoruz)
    tablo_baslik_satiri = len(bilgiler) + 3
    for cell in ws1[tablo_baslik_satiri]:
        cell.font = header_font
        cell.fill = header_fill

    # --- 2. SAYFA: DETAY DAĞILIMI ---
    ws2 = wb.create_sheet("Detay Dağılımı")
    
    # Arama Bilgilerini Buraya da Yazalım
    ws2.append(['RAPOR BİLGİLERİ'])
    ws2['A1'].font = baslik_font
    for bilgi in bilgiler:
        ws2.append([bilgi])
        ws2.cell(row=ws2.max_row, column=1).font = bilgi_font
        
    ws2.append([])
    ws2.append(['Tam Konum / Birim / Ünvan', 'Sayı'])
    for cell in ws2[tablo_baslik_satiri]:
        cell.font = header_font
        cell.fill = header_fill

    # --- VERİLERİ ÇEK VE İŞLE ---
    if analiz_turu == 'personel':
        sql = "SELECT * FROM personeller WHERE 1=1"
        params = []
        if ist_p_ad: sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ?)"; params.extend([f"%{turkce_normalize(ist_p_ad)}%", f"%{turkce_normalize(ist_p_ad)}%"])
        if ist_p_birim: sql += " AND NORMALIZE(birimi) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_birim)}%")
        if ist_p_kampus and ist_p_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_p_kampus)
        if ist_p_ofis: sql += " AND NORMALIZE(ofis) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_ofis)}%")
        
        rows = conn.execute(sql, params).fetchall()
        
        temp_kampus = {}
        temp_detay = {} # Ünvanları tutacak
        
        for row in rows:
            k = row['kampus'] if row['kampus'] else "Belirtilmedi"
            temp_kampus[k] = temp_kampus.get(k, 0) + 1
            
            u = row['unvan'] if row['unvan'] else "Diğer"
            temp_detay[u] = temp_detay.get(u, 0) + 1

    else: # Demirbaş
        sql = "SELECT kampus, konum, adet FROM demirbaslar WHERE 1=1"
        params = []
        if ist_malzeme: sql += " AND NORMALIZE(ad) LIKE ?"; params.append(f"%{turkce_normalize(ist_malzeme)}%")
        if ist_kampus and ist_kampus != "Tümü": sql += " AND kampus = ?"; params.append(ist_kampus)
        if ist_konum: sql += " AND NORMALIZE(konum) LIKE ?"; params.append(f"%{turkce_normalize(ist_konum)}%")
        
        rows = conn.execute(sql, params).fetchall()
        
        temp_kampus = {}
        temp_detay = {} # Tam Konumları tutacak
        
        for row in rows:
            k = row['kampus']
            adet = row['adet']
            temp_kampus[k] = temp_kampus.get(k, 0) + adet
            tam_konum = row['konum']
            temp_detay[tam_konum] = temp_detay.get(tam_konum, 0) + adet

    # Excel'e Yazdırma
    for k, v in temp_kampus.items(): ws1.append([k, v])
    
    # Detayları Alfabetik Sırayla Yazalım
    for k in sorted(temp_detay.keys()):
        ws2.append([k, temp_detay[k]])

    # Sütun Genişlikleri
    ws1.column_dimensions['A'].width = 40
    ws1.column_dimensions['B'].width = 15
    ws2.column_dimensions['A'].width = 80
    ws2.column_dimensions['B'].width = 15

    conn.close()
    output = io.BytesIO()
    wb.save(output); output.seek(0)
    
    dosya_adi = "Ozet_Rapor_Personel.xlsx" if analiz_turu == 'personel' else "Ozet_Rapor_Demirbas.xlsx"
    return send_file(output, download_name=dosya_adi, as_attachment=True)

@app.route('/toplu-tasi-demirbas', methods=['POST'])
def toplu_tasi_demirbas():
    secilenler = request.form.getlist('secilen_ids')
    yeni_kampus = request.form.get('yeni_kampus')
    yeni_konum = request.form.get('yeni_konum')
    
    if not secilenler or not yeni_konum:
        return redirect(url_for('index', tab='demirbas'))
    
    conn = baglanti_kur()
    placeholders = ', '.join('?' for _ in secilenler)
    params = [yeni_kampus, yeni_konum] + secilenler
    conn.execute(f"UPDATE demirbaslar SET kampus=?, konum=? WHERE id IN ({placeholders})", params)
    conn.commit()
    conn.close()
    
    log_kaydet(f"{len(secilenler)} Kayıt Taşındı", f"Yeni: {yeni_kampus}/{yeni_konum}", "Taşıma")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/toplu-sil-demirbas', methods=['GET', 'POST'])
def toplu_sil_demirbas():
    secilenler = []
    
    if request.method == 'POST':
        secilenler = request.form.getlist('secilen_ids')
    else:
        ids_param = request.args.get('ids', '')
        if ids_param:
            secilenler = ids_param.split(',')

    if not secilenler or secilenler == ['']:
        return redirect(url_for('index', tab='demirbas'))

    conn = baglanti_kur()
    try:
        placeholders = ', '.join('?' for _ in secilenler)
        conn.execute(f"DELETE FROM demirbaslar WHERE id IN ({placeholders})", secilenler)
        conn.commit()
        log_kaydet(f"{len(secilenler)} Kayıt Silindi", "Toplu İşlem", "Silme")
    except Exception as e:
        print(f"Silme hatası: {e}")
    finally:
        conn.close()

    return redirect(url_for('index', tab='demirbas'))

@app.route('/toplu-yazdir-demirbas', methods=['GET', 'POST'])
def toplu_yazdir_demirbas():
    if request.method == 'POST':
        secilenler = request.form.getlist('secilen_ids')
    else:
        ids_str = request.args.get('ids', '')
        secilenler = ids_str.split(',') if ids_str else []

    if not secilenler or secilenler == ['']:
        return redirect(url_for('index', tab='demirbas'))
    
    conn = baglanti_kur()
    placeholders = ', '.join('?' for _ in secilenler)
    cur = conn.execute(f"SELECT DISTINCT konum FROM demirbaslar WHERE id IN ({placeholders})", secilenler)
    konumlar = [row[0] for row in cur.fetchall()]
    conn.close()

    qr_listesi = []
    for konum in konumlar:
        hedef_url = url_for('ofis_detay', konum_adi=konum, _external=True)
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(hedef_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_listesi.append({'konum': konum, 'qr': qr_base64})
        
    return render_template('toplu_yazdir.html', qr_listesi=qr_listesi)

@app.route('/get-all-ids')
def get_all_ids():
    tab = request.args.get('tab', 'demirbas')
    q = request.args.get('q', '').strip()
    
    conn = baglanti_kur()
    if tab == 'demirbas':
        if q:
            query = "SELECT id FROM demirbaslar WHERE ad LIKE ? OR cinsi LIKE ? OR konum LIKE ?"
            params = (f'%{q}%', f'%{q}%', f'%{q}%')
            cur = conn.execute(query, params)
        else:
            cur = conn.execute("SELECT id FROM demirbaslar")
    else: 
        if q:
            query = "SELECT id FROM personeller WHERE ad_soyad LIKE ? OR unvan LIKE ? OR birimi LIKE ?"
            params = (f'%{q}%', f'%{q}%', f'%{q}%')
            cur = conn.execute(query, params)
        else:
            cur = conn.execute("SELECT id FROM personeller")
            
    ids = [str(row[0]) for row in cur.fetchall()]
    conn.close()
    return jsonify(ids)

# ---------------------------------------------------
# ARIZA / TALEP YÖNETİM ROTALARI (YENİ EKLENEN KISIM)
# ---------------------------------------------------

@app.route('/ekle-ariza', methods=['POST'])
def ekle_ariza():
    conn = baglanti_kur()
    konum = request.form.get('konum')
    baslik = request.form.get('baslik')
    aciklama = request.form.get('aciklama', '')
    bildiren = request.form.get('bildiren', '')
    oncelik = request.form.get('oncelik', 'Normal')
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    conn.execute("INSERT INTO arizalar (konum, baslik, aciklama, bildiren, oncelik, durum, tarih) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (konum, baslik, aciklama, bildiren, oncelik, 'Bekliyor', tarih))
    conn.commit()
    conn.close()
    
    log_kaydet("Arıza Bildirimi", f"{konum} - {baslik}", "Arıza")
    return redirect(request.referrer or url_for('index'))

@app.route('/guncelle-ariza-durum/<int:id>/<yeni_durum>')
def guncelle_ariza_durum(id, yeni_durum):
    conn = baglanti_kur()
    cur = conn.cursor()
    # Önce kaydı çekelim (log için)
    cur.execute("SELECT baslik, konum, durum FROM arizalar WHERE id=?", (id,))
    ariza = cur.fetchone()
    
    if ariza:
        cur.execute("UPDATE arizalar SET durum=? WHERE id=?", (yeni_durum, id))
        conn.commit()
        log_kaydet(f"Arıza Güncelleme ({yeni_durum})", f"{ariza['konum']} - {ariza['baslik']}", "Arıza")
    
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/sil-ariza/<int:id>')
def sil_ariza(id):
    conn = baglanti_kur()
    cur = conn.cursor()
    cur.execute("SELECT baslik, konum FROM arizalar WHERE id=?", (id,))
    ariza = cur.fetchone()
    
    if ariza:
        cur.execute("DELETE FROM arizalar WHERE id=?", (id,))
        conn.commit()
        log_kaydet("Arıza Silindi", f"{ariza['konum']} - {ariza['baslik']}", "Silme")
    
    conn.close()
    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)