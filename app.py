from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, session, flash
import sqlite3
from datetime import datetime
import openpyxl
import io
import qrcode
import os
import base64
import math
from io import BytesIO
from openpyxl.styles import Font, Alignment, PatternFill
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
# --- KONFİGÜRASYON ---
load_dotenv()
DB_NAME = os.getenv("DB_NAME", "demirbas.db")

app = Flask(__name__)
app.secret_key = 'universite_gizli_anahtar'

# --- LOGIN KONTROL DECORATOR (GÜVENLİK GÜNCELLEMESİ) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Oturum kontrolü
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        
        # 2. VERİTABANI KONTROLÜ (Silinmiş kullanıcıyı engellemek için)
        conn = baglanti_kur()
        user = conn.execute("SELECT id, yetki_duzeyi, rol FROM kullanicilar WHERE kullanici_adi = ?", 
                            (session.get('kullanici_adi'),)).fetchone()
        conn.close()
        
        if not user:
            # Kullanıcı veritabanından silinmişse oturumu öldür
            session.clear()
            flash("Hesabınız silinmiş veya erişiminiz kaldırılmış.", "danger")
            return redirect(url_for('login'))
            
        # (Opsiyonel) Yetki düzeyi değişmişse session'ı güncelle
        session['yetki_duzeyi'] = user['yetki_duzeyi']
        session['rol'] = user['rol']

        return f(*args, **kwargs)
    return decorated_function

# Üniversite Yerleşkeleri (RESMİ 4 YERLEŞKE)
YERLESKELER = [
    "Yalıncak Yerleşkesi",
    "Pelitli Yerleşkesi",
    "Kaşüstü (Yomra) Yerleşkesi",
    "Çimenli Yerleşkesi"
]

# Üniversite İdari Birimleri Listesi
BIRIMLER = [
    "Kurumsal İletişim ve Halkla İlişkiler Daire Başkanlığı",
    "Bilgi İşlem Daire Başkanlığı",
    "İdari ve Mali İşler Daire Başkanlığı",
    "Kütüphane ve Dökümantasyon Daire Başkanlığı",
    "Öğrenci İşleri Daire Başkanlığı",
    "Personel Daire Başkanlığı",
    "Yapı İşleri ve Teknik Daire Başkanlığı",
    "Yazı İşleri Müdürlüğü",
    "Sağlık, Kültür ve Spor Daire Başkanlığı"
]# --- BİRİM - KAMPÜS EŞLEŞMESİ (YETKİ MATRİSİ) ---
# Sol taraf: Birim Adı, Sağ Taraf: Bulunduğu Kampüs
# Üniversite Personel Ünvanları
UNVANLAR = [
    "Daire Başkanı",
    "Şube Müdürü",
    "Birim Sorumlusu",
    "Şef",
    "Memur",
    "Bilgisayar İşletmeni",
    "Tekniker",
    "Teknisyen",
    "Mühendis",
    "Sürekli İşçi",
    "Sözleşmeli Personel"
]
BIRIM_KAMPUS_MAP = {
    "Rektörlük": "Pelitli Yerleşkesi",
    "Genel Sekreterlik": "Pelitli Yerleşkesi",
    "Bilgi İşlem Daire Bşk.": "Pelitli Yerleşkesi",
    "Öğrenci İşleri Daire Bşk.": "Pelitli Yerleşkesi",
    "Personel Daire Bşk.": "Pelitli Yerleşkesi",
    "İdari ve Mali İşler": "Pelitli Yerleşkesi",
    "Kütüphane ve Dokümantasyon": "Pelitli Yerleşkesi",
    "Yapı İşleri ve Teknik": "Pelitli Yerleşkesi", # İdari olduğu için buraya aldım
    "Sağlık Kültür Spor": "Pelitli Yerleşkesi"
}
# --- KAMPÜS TESPİT SÖZLÜĞÜ (ÖNCELİK SIRALI) ---
    # Python 3.7+ sözlüklerde ekleme sırasını korur.
    # Önce ÖZEL yerleri kontrol et, en sona GENEL (Yalıncak) kalsın.
KAMPUS_MAP = {
        # 1. Pelitli (Dosya adında 'Ömer Yıldız Pelitli' geçse bile burayı yakalar)
        "pelitli": "Pelitli Yerleşkesi",

        # 2. Çimenli
        "çimenli": "Çimenli Yerleşkesi",
        "cimenli": "Çimenli Yerleşkesi",

        # 3. Kaşüstü / Yomra
        "kaşüstü": "Kaşüstü (Yomra) Yerleşkesi",
        "kasustu": "Kaşüstü (Yomra) Yerleşkesi",
        "yomra": "Kaşüstü (Yomra) Yerleşkesi",

        # 4. Yalıncak (Ve tek başına 'Ömer Yıldız' geçerse burasıdır)
        "yalıncak": "Yalıncak Yerleşkesi",
        "yalincak": "Yalıncak Yerleşkesi",
        
        # DİKKAT: Yukarıdakiler bulunamazsa ve sadece 'Ömer Yıldız' yazıyorsa Yalıncak'tır.
        "ömer yıldız": "Yalıncak Yerleşkesi",
        "omer yildiz": "Yalıncak Yerleşkesi",
        "omer yıldız": "Yalıncak Yerleşkesi"
    }

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

# --- MERKEZİ LOG SİSTEMİ (GÜNCELLENDİ: KİM YAPTI?) ---
def log_kaydet(baslik, detay, tur="İşlem"):
    try:
        conn = baglanti_kur()
        cur = conn.cursor()
        tarih_saat = datetime.now().strftime("%d-%m-%Y %H:%M")
        
        # O an kim giriş yapmışsa ismini al, yoksa 'Sistem' yaz
        kim_yapti = session.get('ad_soyad', 'Sistem Otomatiği')
        
        cur.execute("INSERT INTO yukleme_gecmisi (dosya_adi, hedef_konum, tur, tarih, islem_yapan) VALUES (?, ?, ?, ?, ?)",
                    (baslik, detay, tur, tarih_saat, kim_yapti))
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
    
    conn.execute('''CREATE TABLE IF NOT EXISTS arizalar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    konum TEXT NOT NULL,
                    baslik TEXT NOT NULL,
                    aciklama TEXT,
                    bildiren TEXT,
                    durum TEXT DEFAULT 'Bekliyor',
                    oncelik TEXT DEFAULT 'Normal',
                    tarih TEXT)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS kullanicilar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kullanici_adi TEXT NOT NULL UNIQUE,
                    sifre_hash TEXT NOT NULL,
                    rol TEXT DEFAULT 'personel',
                    ad_soyad TEXT)''')
    
    # --- MIGRATION (YENİ SÜTUNLAR) ---
    try:
        conn.execute("ALTER TABLE kullanicilar ADD COLUMN birim TEXT")
    except sqlite3.OperationalError: pass
    try:
        conn.execute("ALTER TABLE arizalar ADD COLUMN islem_yapan TEXT")
    except sqlite3.OperationalError: pass

    try:
        conn.execute("ALTER TABLE kullanicilar ADD COLUMN yetki_duzeyi INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass 
    try:
        conn.execute("ALTER TABLE arizalar ADD COLUMN iptal_nedeni TEXT")
        print(">>> SİSTEM: 'iptal_nedeni' sütunu arizalar tablosuna eklendi.")
    except sqlite3.OperationalError: pass
    try:
        conn.execute("ALTER TABLE kullanicilar ADD COLUMN tarih TEXT")
        print(">>> SİSTEM: 'tarih' sütunu kullanicilar tablosuna eklendi.")
    except sqlite3.OperationalError: pass
    try:
        conn.execute("ALTER TABLE personeller ADD COLUMN email TEXT")
        print(">>> SİSTEM: 'email' sütunu personeller tablosuna eklendi.")
    except sqlite3.OperationalError: pass

    try:
        conn.execute("ALTER TABLE personeller ADD COLUMN telefon TEXT")
        print(">>> SİSTEM: 'telefon' sütunu personeller tablosuna eklendi.")
    except sqlite3.OperationalError: pass
    try:
        conn.execute("ALTER TABLE yukleme_gecmisi ADD COLUMN islem_yapan TEXT")
        print(">>> SİSTEM: 'islem_yapan' sütunu geçmiş tablosuna eklendi.")
    except sqlite3.OperationalError: pass

    # --- VARSAYILAN ADMIN KONTROLÜ VE GÜNCELLEMESİ ---
    cur = conn.cursor()
    cur.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = 'admin'")
    if not cur.fetchone():
        # Admin yoksa oluştur (Seviye 3 - Tam Yetki)
        hashed_pw = generate_password_hash("123") 
        cur.execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad_soyad, birim, yetki_duzeyi) VALUES (?, ?, ?, ?, ?, ?)",
                    ('admin', hashed_pw, 'admin', 'Sistem Yöneticisi', 'Rektörlük', 3))
        print(">>> SİSTEM MESAJI: Varsayılan admin oluşturuldu.")
    else:
        # Admin varsa yetkilerini 3'e Yükselt (BU KISIM KRİTİK)
        conn.execute("UPDATE kullanicilar SET yetki_duzeyi = 3, rol = 'admin' WHERE kullanici_adi = 'admin'")
        print(">>> SİSTEM MESAJI: Admin yetkileri 'Seviye 3' olarak güncellendi.")
    
    conn.commit()
    conn.close()

# Fonksiyonu çağırmayı unutma (app.py açılınca çalışır)
tablolari_olustur()

# --- LOGIN / LOGOUT ROTALARI ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        kadi = request.form.get('kullanici_adi')
        sifre = request.form.get('sifre')
        
        conn = baglanti_kur()
        cur = conn.cursor()
        cur.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (kadi,))
        user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user['sifre_hash'], sifre):
            session['logged_in'] = True
            session['kullanici_adi'] = user['kullanici_adi']
            session['rol'] = user['rol']
            session['ad_soyad'] = user['ad_soyad']
            session['birim'] = user['birim'] 
            session['yetki_duzeyi'] = user['yetki_duzeyi'] if user['yetki_duzeyi'] is not None else 0
            
            # --- ÖZELLEŞTİRİLMİŞ YÖNLENDİRME (GÜNCELLENDİ) ---
            # Teknik Servis VEYA Standart Personel (Seviye 0) ise -> ARIZA Sekmesine git
            if session['rol'] == 'teknik' or int(session.get('yetki_duzeyi', 0)) == 0:
                return redirect(url_for('index', tab='ariza'))
            else:
                # Yöneticiler ve Birim Sorumluları -> Ana Sayfaya (Demirbaş) gitsin
                return redirect(url_for('index'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ANA SAYFA (TEK VE DOĞRU VERSİYON) ---
@app.route('/')
@login_required
def index():
    aktif_tab = request.args.get('tab', 'demirbas')
    arama_terimi = request.args.get('q', '') 
    
    # --- YETKİ VE FİLTRELEME MANTIĞI ---
    kullanici_yetki = int(session.get('yetki_duzeyi', 0))
    kullanici_birim = session.get('birim', 'Genel')
    kullanici_rol = session.get('rol')
    # Birim haritasından kampüsü çek
    izinli_kampus = BIRIM_KAMPUS_MAP.get(kullanici_birim, None)
    
    # Otomatik Sekme Yönlendirmesi
    if not aktif_tab:
        if kullanici_yetki == 0 or kullanici_rol == 'teknik':
            aktif_tab = 'ariza'
        else:
            aktif_tab = 'demirbas'

    # İstatistik Filtreleri (Hata almamak için varsayılanlar)
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
    
    # ==========================================
    # 1. DEMİRBAŞ ve PERSONEL SORGULARI (HİYERARŞİK)
    # ==========================================
    d_sql = "SELECT * FROM demirbaslar WHERE 1=1"
    d_params = []  # İsim düzeltildi (eskiden d_p idi)
    
    p_sql = "SELECT * FROM personeller WHERE 1=1"
    p_params = []  # İsim düzeltildi (eskiden p_p idi)

    # --- HİYERARŞİ MANTIĞI ---
    
    # SEVİYE 3 (Admin / Bilgi İşlem): Her şeyi görür (Filtre Yok)
    if kullanici_yetki >= 3:
        pass 

    # SEVİYE 2 (Genel Sekreterlik): Her şeyi görür (Filtre Yok)
    elif kullanici_yetki == 2:
        pass
        
    # SEVİYE 1 (Birim Sorumlusu): SADECE KENDİ BİRİMİNİ GÖRÜR
    elif kullanici_yetki == 1:
        # Personel Listesi Sadece Kendi Birimi
        p_sql += " AND birimi = ?"
        p_params.append(kullanici_birim)
        
        # Demirbaşlar: Şimdilik Kampüs bazlı filtreleme
        if izinli_kampus:
            d_sql += " AND kampus = ?"
            d_params.append(izinli_kampus)
            
    # SEVİYE 0 (Standart Personel): HİÇBİR LİSTEYİ GÖREMEZ
    else:
        p_sql += " AND 1=0" 
        d_sql += " AND 1=0"

    # --- ARAMA FİLTRESİ (HERKES İÇİN GEÇERLİ) ---
    if arama_terimi:
        t = f"%{turkce_normalize(arama_terimi)}%"
        
        if aktif_tab == 'demirbas':
            # Demirbaş araması
            d_sql += " AND (NORMALIZE(ad) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(kampus) LIKE ?)"
            d_params.extend([t, t, t])
                
        elif aktif_tab == 'personel':
            # Personel araması (Genişletilmiş)
            p_sql += """ AND (
                            NORMALIZE(ad_soyad) LIKE ? OR 
                            NORMALIZE(unvan) LIKE ? OR 
                            NORMALIZE(birimi) LIKE ? OR 
                            NORMALIZE(kampus) LIKE ? OR 
                            NORMALIZE(ofis) LIKE ?
                        )"""
            p_params.extend([t, t, t, t, t])
    
    # --- VERİTABANI İŞLEMLERİ (SAYFALAMA ve ÇEKME) ---
    
    # 1. Demirbaşları Çek (d_params kullanarak)
    cur.execute(d_sql.replace("SELECT *", "SELECT COUNT(*)"), d_params)
    total_d = cur.fetchone()[0]
    toplam_sayfa_demirbas = math.ceil(total_d / limit) if total_d > 0 else 1
    
    cur.execute(d_sql + " ORDER BY id DESC LIMIT ? OFFSET ?", d_params + [limit, offset_d])
    demirbaslar = cur.fetchall()
    
    # 2. Personelleri Çek (p_params kullanarak)
    cur.execute(p_sql.replace("SELECT *", "SELECT COUNT(*)"), p_params)
    total_p = cur.fetchone()[0]
    toplam_sayfa_personel = math.ceil(total_p / limit) if total_p > 0 else 1
    
    cur.execute(p_sql + " ORDER BY ofis ASC LIMIT ? OFFSET ?", p_params + [limit, offset_p])
    personeller = cur.fetchall()

    # --- DİĞER VERİLER (ARIZA, İSTATİSTİK VB.) ---
    
    # Arızalar
    a_sql = "SELECT * FROM arizalar"
    a_params = []
    mevcut_kisi = session.get('ad_soyad', '')

    if kullanici_rol not in ['admin', 'teknik']:
        a_sql += " WHERE bildiren = ?"
        a_params.append(mevcut_kisi)
    
    a_sql += " ORDER BY id DESC"
    cur.execute(a_sql, a_params)
    arizalar = cur.fetchall()
    
    # Bildirim Sayısı
    bildirim_sayisi = 0
    if kullanici_rol in ['admin', 'teknik']:
        cur.execute("SELECT COUNT(*) FROM arizalar WHERE durum='Bekliyor'")
        bildirim_sayisi = cur.fetchone()[0]
    else:
        # Personel kendi bekleyenlerini görsün
        cur.execute("SELECT COUNT(*) FROM arizalar WHERE bildiren=? AND durum='Bekliyor'", (mevcut_kisi,))
        bildirim_sayisi = cur.fetchone()[0]

    # Geçmiş ve Yüklemeler
    cur.execute("SELECT * FROM yukleme_gecmisi WHERE tur = 'Yükleme' ORDER BY id DESC LIMIT 1")
    son_yukleme = cur.fetchone()
    
    cur.execute("SELECT * FROM yukleme_gecmisi ORDER BY id DESC LIMIT 100")
    tum_gecmis = cur.fetchall()
    
    # Grafikler (Sadece Admin ve Seviye 2+)
    chart_kampus_labels=[]; chart_kampus_values=[]; chart_esya_labels=[]; chart_esya_values=[]
    chart_personel_labels=[]; chart_personel_values=[]; chart_tur_labels=[]; chart_tur_values=[]
    
    if kullanici_yetki >= 2:
        # Kampüs Dağılımı
        cur.execute("SELECT kampus, SUM(adet) FROM demirbaslar GROUP BY kampus")
        k_v = cur.fetchall()
        chart_kampus_labels = [r[0] for r in k_v]
        chart_kampus_values = [r[1] for r in k_v]
        
        # Diğer grafik verileri (Örnek olarak boş bırakıldı, ihtiyaca göre doldurulabilir)

    # Kullanıcı Listesi (Sadece Admin için)
    kullanicilar_listesi = []
    if session.get('rol') == 'admin':
        cur.execute("SELECT * FROM kullanicilar ORDER BY id ASC")
        kullanicilar_listesi = cur.fetchall()

    # İstatistik değişkenleri (Boş tanımlar)
    analiz_sonuclari=[]; analiz_toplam=0; f_labels_1=[]; f_values_1=[]; f_labels_2=[]; f_values_2=[]
    
    # --- 6. AKTİF KULLANICININ OFİS BİLGİSİNİ BUL ---
    aktif_kullanici_ofis = ""
    
    # Sadece Personel rolündeyse bu sorguyu yap (Admin veya Teknik için gerek yok)
    if kullanici_rol == 'personel':
        # Kullanıcının tam adını (ad_soyad) kullanarak personel listesinde ara
        cur.execute("SELECT kampus, ofis FROM personeller WHERE ad_soyad = ?", (session.get('ad_soyad'),))
        personel_kaydi = cur.fetchone()
        
        if personel_kaydi:
            # Bulursa formatla: "Kampüs Adı / Ofis No"
            aktif_kullanici_ofis = f"{personel_kaydi['kampus']} / {personel_kaydi['ofis']}"

    conn.close()

    return render_template('index.html', 
                           aktif_tab=aktif_tab,
                           demirbaslar=demirbaslar,
                           personeller=personeller,
                           arizalar=arizalar,
                           bildirim_sayisi=bildirim_sayisi,
                           yerleskeler=YERLESKELER,
                           sayfa_d=sayfa_d,
                           sayfa_p=sayfa_p,
                           toplam_sayfa_demirbas=toplam_sayfa_demirbas,
                           toplam_sayfa_personel=toplam_sayfa_personel,
                           arama_terimi=arama_terimi,
                           analiz_sonuclari=analiz_sonuclari,
                           analiz_turu=analiz_turu,
                           chart_kampus_labels=chart_kampus_labels, chart_kampus_values=chart_kampus_values,
                           chart_esya_labels=chart_esya_labels, chart_esya_values=chart_esya_values,
                           chart_personel_labels=chart_personel_labels, chart_personel_values=chart_personel_values,
                           chart_tur_labels=chart_tur_labels, chart_tur_values=chart_tur_values,
                           f_labels_1=f_labels_1, f_values_1=f_values_1,
                           f_labels_2=f_labels_2, f_values_2=f_values_2,
                           ist_malzeme=ist_malzeme, ist_kampus=ist_kampus, ist_konum=ist_konum,
                           ist_p_ad=ist_p_ad, ist_p_birim=ist_p_birim, ist_p_kampus=ist_p_kampus, ist_p_ofis=ist_p_ofis,
                           analiz_toplam=analiz_toplam,
                           son_yukleme=son_yukleme,
                           tum_gecmis=tum_gecmis,
                           kullanicilar_listesi=kullanicilar_listesi,
                           birimler=BIRIMLER,
                           unvanlar=UNVANLAR,
                           aktif_kullanici_ofis=aktif_kullanici_ofis
                           )
# --- YÜKLEME VE İŞLEM FONKSİYONLARI ---
@app.route('/yukle-demirbas', methods=['POST'])
@login_required
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

@app.route('/yukle-klasor', methods=['POST'])
@login_required
def yukle_klasor():
    if 'dosya' not in request.files: return redirect(url_for('index'))
    dosyalar = request.files.getlist('dosya')
    
    # Formdan gelen varsayılan (Eğer dosya isminde hiçbir şey bulamazsa bunu kullanır)
    varsayilan_kampus = request.form.get('hedef_kampus', 'Merkez (Kanuni) Kampüsü')
    
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

    # --- 1. KAMPÜS TESPİT SÖZLÜĞÜ (ÖNCELİK SIRALI) ---
    # Bu kelimeleri görünce KAMPÜS sütununu otomatik dolduracak.
    KAMPUS_MAP = {
        "pelitli": "Pelitli Yerleşkesi",
        "çimenli": "Çimenli Yerleşkesi",
        "cimenli": "Çimenli Yerleşkesi",
        "kaşüstü": "Kaşüstü (Yomra) Yerleşkesi",
        "kasustu": "Kaşüstü (Yomra) Yerleşkesi",
        "yomra": "Kaşüstü (Yomra) Yerleşkesi",
        "yalıncak": "Yalıncak Yerleşkesi",
        "yalincak": "Yalıncak Yerleşkesi",
        "ömer yıldız": "Yalıncak Yerleşkesi", # Ömer Yıldız görürse Yalıncak yazar
        "omer yildiz": "Yalıncak Yerleşkesi"
    }

    # --- 2. KONUMDAN SİLİNECEK KELİMELER (GÜNCELLENDİ) ---
    # Bu kelimeler KONUM (Ofis) bilgisinden silinecek.
    # Böylece "TelefonElektronikYalıncak..." -> "TelefonElektronik" olacak.
    SILINECEK_KELIMELER = [
        # Dosya uzantıları ve gereksizler
        "LİSTESİ", "LISTESI", "LİSTE", "LISTE", "DEMİRBAŞLARI", "DEMİRBAŞ", "DEMIRBAS", 
        "ENVANTER", "SAYIM", "SİSTEMİ", "SISTEMI", "YAPILDI", "YAPILAN", "YENİ", "ESKİ", 
        "COPY", "KOPYA", "YEDEK", "REVİZE", "REVIZE", "DÜZENLEME", "DÜZENLENEN", 
        "KONTROL", "TASLAK", "SON", "FİNAL", "FINAL", "MASAÜSTÜ", "DOWNLOADS", 
        "BELGELERİM", "TABLO", "TÜMÜ", "TUMU", "XLSX", "XLS",

        # YERLEŞKE İSİMLERİ (Bunları Konumdan SİLİYORUZ, çünkü zaten Kampüs sütununda var)
        "YALINCAK", "YALINCAK", "PELİTLİ", "PELITLI", 
        "ÇİMENLİ", "CIMENLI", "KAŞÜSTÜ", "KASUSTU", "YOMRA",
        "KANUNİ", "MERKEZ", "KAMPÜSÜ", "KAMPUSU", 
        "YERLEŞKESİ", "YERLESKESI", "YERLESKESİ",
        
        # ÖZEL İSİMLER (Bunları da siliyoruz)
        "ÖMER YILDIZ", "OMER YILDIZ", "OMER YILDIZ", "ÖMER", "YILDIZ"
    ]

    ONEMLI_KELIMELER = [
        "BLOK", "KAT", "ODA", "BİNA", "BINA", "YURT", "OFİS", "OFFICE", 
        "HALL", "SALON", "LAB", "DEPO", "ZEMİN", "GİRİŞ", "SİSTEM", "KAZAN",
        "RESTORAN", "YEMEKHANE", "KANTİN", "LOBİ", "MESCİT", "GUVENLIK", "GÜVENLİK",
        "AMBAR", "ATÖLYE", "ARŞİV", "LİSE", "FAKÜLTE", "MYO", "MEMUR", "PERSONEL",
        "PATOLOJİ", "KLİNİK", "POLİKLİNİK", "SERVİS", "BÖLÜM", "BOLUM", "BİRİM", "LABORATUVAR"
    ]

    for dosya in dosyalar:
        if not dosya.filename.endswith('.xlsx') and not dosya.filename.endswith('.xls'):
            continue
        if '~$' in dosya.filename: continue
            
        try:
            full_path = dosya.filename.replace('\\', '/')
            path_lower = full_path.lower()
            
            # A) Kampüsü Tespit Et
            aktif_kampus = varsayilan_kampus
            for anahtar, gercek_ad in KAMPUS_MAP.items():
                if anahtar in path_lower:
                    aktif_kampus = gercek_ad
                    break 
            
            # B) Konum İsmini Temizle (Dosya yolundan)
            path_parts = full_path.split('/')
            dosya_adi_ham = path_parts[-1].rsplit('.', 1)[0]
            tum_parcalar = path_parts[:-1] + [dosya_adi_ham]
            
            anlamli_yol_parcalari = []

            for parca in tum_parcalar:
                temiz_parca = tr_upper(parca) # Önce BÜYÜK HARF yap
                
                # SİLME İŞLEMİ BURADA YAPILIYOR
                for yasakli in SILINECEK_KELIMELER:
                    # Kelime içinde geçiyorsa boşlukla değiştir veya sil
                    if yasakli in temiz_parca:
                        temiz_parca = temiz_parca.replace(yasakli, "")
                
                # Temizlik sonrası kalan karakterleri düzelt
                temiz_parca = temiz_parca.replace("_", " ").replace("-", " ").strip()
                
                # Eğer çok kısa kaldıysa (Örn: Sadece sayı kaldıysa veya boşsa)
                if len(temiz_parca) < 2 and not any(c.isdigit() for c in temiz_parca):
                    continue

                is_onemli = any(k in temiz_parca for k in ONEMLI_KELIMELER)
                is_blok_kodu = (len(temiz_parca) > 0 and len(temiz_parca) < 6 and any(c.isdigit() for c in temiz_parca))
                
                # Eğer anlamlı bir şeyler kaldıysa yola ekle
                if (is_onemli or is_blok_kodu or len(temiz_parca) > 2):
                    temiz_parca_title = tr_title(temiz_parca)
                    # Mükerrer eklemeyi önle (Örn: Depo / Depo olmasın)
                    if anlamli_yol_parcalari:
                        son_eklenen = anlamli_yol_parcalari[-1]
                        if temiz_parca_title in son_eklenen or son_eklenen in temiz_parca_title:
                            if len(temiz_parca_title) > len(son_eklenen):
                                anlamli_yol_parcalari[-1] = temiz_parca_title
                            continue 
                    
                    anlamli_yol_parcalari.append(temiz_parca_title)

            temiz_yol_str = " / ".join(anlamli_yol_parcalari)

            # C) Excel İçini Oku ve Kaydet
            wb = openpyxl.load_workbook(dosya)
            
            for ws in wb.worksheets:
                sheet_adi = ws.title.strip()
                # Sayfa isminde de temizlik yapalım mı? İstersen buraya da eklenebilir.
                # Şimdilik sadece dosya yolundan temizledik.
                
                if "Sheet" in sheet_adi or "Sayfa" in sheet_adi:
                    tam_konum = temiz_yol_str if temiz_yol_str else "Genel Depo"
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
                    
                    # Aynı malzeme, aynı konumda var mı kontrolü
                    cur.execute("SELECT id FROM demirbaslar WHERE ad=? AND konum=?", (ad, tam_konum))
                    if not cur.fetchone():
                        cur.execute("INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) VALUES (?, ?, ?, ?, ?, ?)", 
                                    (ad, cinsi, aktif_kampus, tam_konum, adet, datetime.now().strftime("%Y-%m-%d")))
            
            islem_sayisi += 1

        except Exception as e:
            print(f"Hata ({dosya.filename}): {e}")

    conn.commit() 
    
    if islem_sayisi > 0:
        aciklama = f"Akıllı Yükleme ({islem_sayisi} dosya)"
        ornek_konum = list(kaydedilen_yerler)[0] if len(kaydedilen_yerler) > 0 else ""
        log_kaydet(aciklama, f"Örn: {ornek_konum}", "Yükleme")

    conn.close() 
    return redirect(url_for('index', tab='demirbas'))

@app.route('/yukle-personel', methods=['POST'])
@login_required
def yukle_personel():
    if 'dosya' not in request.files: return redirect(url_for('index'))
    dosya = request.files['dosya']
    
    if dosya and dosya.filename != '':
        try:
            conn = baglanti_kur()
            cur = conn.cursor()
            wb = openpyxl.load_workbook(dosya)
            ws = wb.active
            
            eklenen_sayisi = 0
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                # Boş satır kontrolü
                if not row or row[0] is None: continue
                
                # Verileri Excel'den Al (Hata önleyici kontrollerle)
                ad_soyad = row[0]
                unvan = row[1] if len(row) > 1 and row[1] else ""
                birim = row[2] if len(row) > 2 and row[2] else ""
                kampus = row[3] if len(row) > 3 and row[3] else "Merkez"
                ofis = row[4] if len(row) > 4 and row[4] else ""
                
                # YENİ EKLENEN SÜTUNLAR
                email = row[5] if len(row) > 5 and row[5] else ""
                telefon = str(row[6]) if len(row) > 6 and row[6] else "" # Telefonu string yap
                
                # Aynı kişi aynı ofiste var mı kontrol et
                cur.execute("SELECT id FROM personeller WHERE ad_soyad=? AND ofis=?", (ad_soyad, ofis))
                if not cur.fetchone():
                    # Yoksa EKLE
                    cur.execute("""INSERT INTO personeller 
                                   (ad_soyad, unvan, birimi, kampus, ofis, email, telefon) 
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                                (ad_soyad, unvan, birim, kampus, ofis, email, telefon))
                    eklenen_sayisi += 1
            
            conn.commit()
            conn.close()
            
            if eklenen_sayisi > 0:
                log_kaydet(f"Personel Listesi Yüklendi", f"{eklenen_sayisi} Kişi Eklendi", "Yükleme")
            else:
                flash("Yüklenecek yeni personel bulunamadı veya hepsi zaten kayıtlı.", "warning")
                
        except Exception as e:
            print(f"Hata: {e}")
            flash(f"Dosya yüklenirken hata oluştu: {e}", "danger")
            
    return redirect(url_for('index', tab='personel'))

# --- CRUD İŞLEMLERİ ---
@app.route('/ekle-demirbas', methods=['POST'])
@login_required
def ekle_demirbas():
    # SADECE TEKNİK SERVİSİ ENGELLEMEK İÇİN
    if session.get('rol') == 'teknik':
        return redirect(url_for('index', tab='ariza'))
    conn = baglanti_kur()
    conn.execute("INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) VALUES (?, ?, ?, ?, ?, ?)", 
                 (request.form['ad'], request.form['cinsi'], request.form['kampus'], request.form['konum'], request.form['adet'], datetime.now().strftime("%Y-%m-%d")))
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad']} Eklendi", f"Konum: {request.form['konum']}", "Ekleme")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/guncelle-demirbas', methods=['POST'])
@login_required
def guncelle_demirbas():
    conn = baglanti_kur()
    conn.execute("UPDATE demirbaslar SET ad=?, cinsi=?, kampus=?, konum=?, adet=? WHERE id=?", 
                 (request.form['ad'], request.form['cinsi'], request.form['kampus'], request.form['konum'], request.form['adet'], request.form['id']))
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad']} Güncellendi", f"Yeni Konum: {request.form['konum']}", "Düzenleme")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/tasi-demirbas', methods=['POST'])
@login_required
def tasi_demirbas():
    # Yetki kontrolü: Seviye 0 (Sadece İzleme) ise işlem yapamaz
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index', tab='demirbas'))

    d_id = request.form.get('id')
    yeni_kampus = request.form.get('kampus')
    yeni_konum = request.form.get('konum')
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT ad, kampus, konum FROM demirbaslar WHERE id=?", (d_id,))
    eski = cur.fetchone()
    if eski:
        cur.execute("UPDATE demirbaslar SET kampus=?, konum=? WHERE id=?", (yeni_kampus, yeni_konum, d_id))
        conn.commit()
        log_kaydet(f"{eski['ad']} Taşındı", f"{eski['kampus']}/{eski['konum']} -> {yeni_kampus}/{yeni_konum}", "Taşıma")
    conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/sil-demirbas/<int:id>')
@login_required
def sil_demirbas(id):
    # SADECE TEKNİK SERVİSİ ENGELLEMEK İÇİN
    if session.get('rol') == 'teknik':
        return redirect(url_for('index', tab='ariza'))
    # SİLME SADECE ADMİN (SEVİYE 2)
    if int(session.get('yetki_duzeyi', 0)) < 3: return redirect(url_for('index', tab='demirbas'))
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT ad, konum FROM demirbaslar WHERE id=?", (id,)); kayit = cur.fetchone()
    if kayit:
        log_kaydet(f"{kayit['ad']} Silindi", f"Eski Konum: {kayit['konum']}", "Silme")
        cur.execute("DELETE FROM demirbaslar WHERE id=?", (id,)); conn.commit()
    conn.close()
    return redirect(url_for('index', tab='demirbas'))

@app.route('/ekle-personel', methods=['POST'])
@login_required
def ekle_personel():
    # GÜVENLİK: Teknik servis ekleme yapamaz
    if session.get('rol') == 'teknik': return redirect(url_for('index', tab='ariza'))

    conn = baglanti_kur()
    
    # E-POSTA BİRLEŞTİRME (AKILLI GİRİŞ)
    raw_email = request.form.get('email_prefix', '').strip()
    if raw_email:
        # Eğer kullanıcı yanlışlıkla @ koyduysa temizle, sadece kullanıcı adını al
        if '@' in raw_email:
            raw_email = raw_email.split('@')[0]
        full_email = f"{raw_email}@avrasya.edu.tr"
    else:
        full_email = ""

    # --- TELEFON DÜZENLEME (BURASI DEĞİŞTİ) ---
    raw_telefon = request.form.get('telefon', '').strip()
    # Boşlukları sil (Veritabanına 5341234567 olarak girer)
    telefon = raw_telefon.replace(" ", "")
    
    # Veritabanına Kaydet
    conn.execute("""INSERT INTO personeller 
                    (ad_soyad, unvan, birimi, kampus, ofis, email, telefon) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                 (request.form['ad_soyad'], request.form['unvan'], request.form['birimi'], 
                  request.form['kampus'], request.form['ofis'], full_email, telefon))
    
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad_soyad']} Eklendi", f"Ofis: {request.form['ofis']}", "Ekleme")
    return redirect(url_for('index', tab='personel'))

@app.route('/guncelle-personel', methods=['POST'])
@login_required
def guncelle_personel():
    conn = baglanti_kur()
    email = request.form.get('email', '')
    telefon = request.form.get('telefon', '')
    
    conn.execute("""UPDATE personeller 
                    SET ad_soyad=?, unvan=?, birimi=?, kampus=?, ofis=?, email=?, telefon=? 
                    WHERE id=?""", 
                 (request.form['ad_soyad'], request.form['unvan'], request.form['birimi'], 
                  request.form['kampus'], request.form['ofis'], email, telefon, request.form['id']))
    
    conn.commit(); conn.close()
    log_kaydet(f"{request.form['ad_soyad']} Güncellendi", f"Ofis: {request.form['ofis']}", "Düzenleme")
    return redirect(url_for('index', tab='personel'))

@app.route('/tasi-personel', methods=['POST'])
@login_required
def tasi_personel():
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT ad_soyad, ofis, kampus FROM personeller WHERE id=?", (request.form['personel_id'],)); kisi = cur.fetchone()
    conn.execute("UPDATE personeller SET kampus = ?, ofis = ? WHERE id = ?", (request.form['yeni_kampus'], request.form['yeni_ofis'], request.form['personel_id']))
    conn.commit(); conn.close()
    if kisi: log_kaydet(f"{kisi['ad_soyad']} Taşındı", f"{kisi['kampus']}/{kisi['ofis']} -> {request.form['yeni_kampus']}/{request.form['yeni_ofis']}", "Taşıma")
    return redirect(url_for('index', tab='personel'))

@app.route('/sil-personel/<int:id>')
@login_required
def sil_personel(id):
    if int(session.get('yetki_duzeyi', 0)) < 3: return redirect(url_for('index', tab='personel'))
    conn = baglanti_kur(); cur = conn.cursor()
    cur.execute("SELECT ad_soyad, ofis FROM personeller WHERE id=?", (id,)); kayit = cur.fetchone()
    if kayit:
        log_kaydet(f"{kayit['ad_soyad']} Silindi", f"Eski Ofis: {kayit['ofis']}", "Silme")
        cur.execute("DELETE FROM personeller WHERE id=?", (id,)); conn.commit()
    conn.close()
    return redirect(url_for('index', tab='personel'))

@app.route('/sifirla-demirbas')
@login_required
def sifirla_demirbas():
    # SADECE TEKNİK SERVİSİ ENGELLEMEK İÇİN
    if session.get('rol') == 'teknik':
        return redirect(url_for('index', tab='ariza'))
    # GÜVENLİK KİLİDİ: Sadece Admin yapabilir!
    if int(session.get('yetki_duzeyi', 0)) < 3: # Sadece Seviye 3 Sıfırlayabilir
        return redirect(url_for('index'))
        
    conn = baglanti_kur()
    conn.execute("DELETE FROM demirbaslar")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='demirbaslar'") # ID sayacını da sıfırla
    conn.commit()
    conn.close()
    
    log_kaydet("Tüm Demirbaş Listesi Silindi", "Veritabanı Sıfırlama", "Sıfırlama")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/sifirla-personel')
@login_required
def sifirla_personel():
    # GÜVENLİK KİLİDİ: Sadece Admin yapabilir!
    if int(session.get('yetki_duzeyi', 0)) < 3: # Sadece Seviye 3 Sıfırlayabilir
        return redirect(url_for('index'))
        
    conn = baglanti_kur()
    conn.execute("DELETE FROM personeller")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='personeller'") # ID sayacını da sıfırla
    conn.commit()
    conn.close()
    
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
@login_required
def indir_sablon(tur):
    wb = openpyxl.Workbook()
    ws = wb.active
    header_font = Font(bold=True)
    
    if tur == 'personel':
        # BAŞLIKLARI GÜNCELLEDİK: E-Posta ve Telefon eklendi
        ws.append(['Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis', 'E-Posta', 'Telefon'])
        # ÖRNEK VERİYİ GÜNCELLEDİK
        ws.append(['Ahmet Yılmaz', 'Memur', 'Öğrenci İşleri', 'Merkez', 'Z-10', 'ahmet@univ.edu.tr', '05551234567'])
        ws.title = "Personel Listesi"
        filename = "sablon_personel_listesi.xlsx"
        
        # Sütun Genişliklerini Ayarla
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 25
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 25
        ws.column_dimensions['G'].width = 15

    else:
        # Demirbaş şablonu aynı kalıyor
        ws.append(['Malzeme Adı', 'Cinsi', 'Adet'])
        ws.append(['Çalışma Masası', 'Ahşap', '1'])
        ws.title = "Demirbaş Listesi"
        filename = "sablon_demirbas_listesi.xlsx"
    
    for cell in ws[1]: 
        cell.font = header_font
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, download_name=filename, as_attachment=True)

@app.route('/rapor')
@login_required
def rapor():
    # GÜVENLİK KİLİDİ: Seviye 0 ise ana sayfaya at
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index'))
        
    conn = baglanti_kur()
    wb = openpyxl.Workbook()
    
    # --- YARDIMCI FONKSİYON: SÜTUNLARI OTOMATİK GENİŞLET ---
    def sutunlari_ayarla(worksheet):
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter # Sütun harfini al (A, B, C...)
            for cell in col:
                try:
                    if cell.value:
                        uzunluk = len(str(cell.value))
                        if uzunluk > max_length:
                            max_length = uzunluk
                except:
                    pass
            # Genişliği ayarlarken biraz boşluk bırak (+2)
            adjusted_width = (max_length + 2)
            # Çok aşırı genişlemeyi önlemek istersen buraya sınır koyabilirsin (örn: min 50)
            worksheet.column_dimensions[column].width = adjusted_width

    # -------------------------------------------------------
    # 1. SAYFA: DEMİRBAŞLAR
    # -------------------------------------------------------
    ws1 = wb.active
    ws1.title = "Demirbaşlar"
    ws1.append(['Sıra No', 'Malzeme Adı', 'Cinsi', 'Kampüs', 'Konum', 'Adet', 'Kayıt Tarihi'])
    
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", fill_type="solid")
    
    # Başlıkları formatla
    for cell in ws1[1]: 
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    # Verileri doldur
    for i, row in enumerate(conn.execute("SELECT * FROM demirbaslar").fetchall(), 1):
        ws1.append([i, row['ad'], row['cinsi'], row['kampus'], row['konum'], row['adet'], row['tarih']])
    
    # Sütunları Ayarla
    sutunlari_ayarla(ws1)

    # -------------------------------------------------------
    # 2. SAYFA: PERSONELLER
    # -------------------------------------------------------
    ws2 = wb.create_sheet("Personeller")
    ws2.append(['Sıra No', 'Ad Soyad', 'Ünvan', 'Birimi', 'Kampüs', 'Ofis'])
    
    # Başlıkları formatla
    for cell in ws2[1]: 
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        
    # Verileri doldur
    for i, row in enumerate(conn.execute("SELECT * FROM personeller").fetchall(), 1):
        ws2.append([i, row['ad_soyad'], row['unvan'], row['birimi'], row['kampus'], row['ofis']])

    # Sütunları Ayarla
    sutunlari_ayarla(ws2)

    conn.close()
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    log_kaydet("Excel Raporu İndirildi", "Tüm Envanter", "Rapor")
    return send_file(output, download_name=f"Envanter_Rapor_{datetime.now().strftime('%d-%m-%Y')}.xlsx", as_attachment=True)

@app.route('/rapor-analiz')
@login_required
def rapor_analiz():
    if session.get('rol') == 'teknik' or int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index'))
    # GÜVENLİK KİLİDİ
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index'))
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    ist_malzeme = request.args.get('ist_malzeme', ''); ist_kampus = request.args.get('ist_kampus', ''); ist_konum = request.args.get('ist_konum', '')
    ist_p_ad = request.args.get('ist_p_ad', ''); ist_p_birim = request.args.get('ist_p_birim', '')
    ist_p_kampus = request.args.get('ist_p_kampus', ''); ist_p_ofis = request.args.get('ist_p_ofis', '')

    conn = baglanti_kur(); wb = openpyxl.Workbook(); ws = wb.active
    header_font = Font(bold=True, color="FFFFFF"); header_fill = PatternFill(start_color="198754", fill_type="solid")
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
@login_required
def rapor_grafik_ozet():
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    ist_malzeme = request.args.get('ist_malzeme', '')
    ist_kampus = request.args.get('ist_kampus', '')
    ist_konum = request.args.get('ist_konum', '')
    ist_p_ad = request.args.get('ist_p_ad', '')
    ist_p_birim = request.args.get('ist_p_birim', '')
    ist_p_kampus = request.args.get('ist_p_kampus', '')
    ist_p_ofis = request.args.get('ist_p_ofis', '')

    conn = baglanti_kur()
    wb = openpyxl.Workbook()
    baslik_font = Font(bold=True, size=12, color="000000")
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="198754", fill_type="solid")
    bilgi_font = Font(italic=True, color="555555")

    ws1 = wb.active; ws1.title = "Kampüs Dağılımı"
    ws1.append(['RAPOR BİLGİLERİ']); ws1['A1'].font = baslik_font
    
    bilgiler = []
    if analiz_turu == 'personel':
        bilgiler = [f"Analiz Türü: Personel", f"Birim: {ist_p_birim if ist_p_birim else 'Tümü'}"]
    else:
        bilgiler = [f"Analiz Türü: Demirbaş", f"Aranan Malzeme: {ist_malzeme if ist_malzeme else 'Tümü'}"]

    for bilgi in bilgiler: ws1.append([bilgi])
    ws1.append([]); ws1.append(['Kampüs Adı', 'Sayı (Adet/Kişi)'])
    
    tablo_baslik_satiri = len(bilgiler) + 3
    for cell in ws1[tablo_baslik_satiri]: cell.font = header_font; cell.fill = header_fill

    ws2 = wb.create_sheet("Detay Dağılımı")
    ws2.append(['RAPOR BİLGİLERİ']); ws2['A1'].font = baslik_font
    for bilgi in bilgiler: ws2.append([bilgi])
    ws2.append([]); ws2.append(['Tam Konum / Birim / Ünvan', 'Sayı'])
    for cell in ws2[tablo_baslik_satiri]: cell.font = header_font; cell.fill = header_fill

    if analiz_turu == 'personel':
        sql = "SELECT * FROM personeller WHERE 1=1"
        params = []
        if ist_p_ad: sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ?)"; params.extend([f"%{turkce_normalize(ist_p_ad)}%", f"%{turkce_normalize(ist_p_ad)}%"])
        if ist_p_birim: sql += " AND NORMALIZE(birimi) LIKE ?"; params.append(f"%{turkce_normalize(ist_p_birim)}%")
        rows = conn.execute(sql, params).fetchall()
        temp_kampus = {}; temp_detay = {}
        for row in rows:
            k = row['kampus'] if row['kampus'] else "Belirtilmedi"
            temp_kampus[k] = temp_kampus.get(k, 0) + 1
            u = row['unvan'] if row['unvan'] else "Diğer"
            temp_detay[u] = temp_detay.get(u, 0) + 1
    else:
        sql = "SELECT kampus, konum, adet FROM demirbaslar WHERE 1=1"
        params = []
        if ist_malzeme: sql += " AND NORMALIZE(ad) LIKE ?"; params.append(f"%{turkce_normalize(ist_malzeme)}%")
        rows = conn.execute(sql, params).fetchall()
        temp_kampus = {}; temp_detay = {}
        for row in rows:
            k = row['kampus']; adet = row['adet']
            temp_kampus[k] = temp_kampus.get(k, 0) + adet
            tam_konum = row['konum']
            temp_detay[tam_konum] = temp_detay.get(tam_konum, 0) + adet

    for k, v in temp_kampus.items(): ws1.append([k, v])
    for k in sorted(temp_detay.keys()): ws2.append([k, temp_detay[k]])

    ws1.column_dimensions['A'].width = 40; ws2.column_dimensions['A'].width = 80
    conn.close(); output = io.BytesIO(); wb.save(output); output.seek(0)
    return send_file(output, download_name="Ozet_Rapor.xlsx", as_attachment=True)

@app.route('/toplu-tasi-demirbas', methods=['POST'])
@login_required
def toplu_tasi_demirbas():
    # Sadece Yetkili (Seviye 1 ve üstü) taşıma yapabilir
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index', tab='demirbas'))

    secilenler = request.form.getlist('secilen_ids')
    yeni_kampus = request.form.get('yeni_kampus')
    yeni_konum = request.form.get('yeni_konum')
    
    if not secilenler or not yeni_konum: return redirect(url_for('index', tab='demirbas'))
    
    conn = baglanti_kur()
    placeholders = ', '.join('?' for _ in secilenler)
    # Parametreleri düzgün sırayla verelim
    params = [yeni_kampus, yeni_konum] + secilenler 
    conn.execute(f"UPDATE demirbaslar SET kampus=?, konum=? WHERE id IN ({placeholders})", params)
    conn.commit(); conn.close()
    
    log_kaydet(f"{len(secilenler)} Kayıt Taşındı", f"Yeni: {yeni_kampus}/{yeni_konum}", "Taşıma")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/toplu-sil-demirbas', methods=['POST'])
@login_required
def toplu_sil_demirbas():
    # Sadece Admin (Seviye 2) silme yapabilir
    if int(session.get('yetki_duzeyi', 0)) < 3:
        return redirect(url_for('index', tab='demirbas'))

    secilenler = request.form.getlist('secilen_ids')
    if not secilenler: return redirect(url_for('index', tab='demirbas'))
    
    conn = baglanti_kur()
    placeholders = ', '.join('?' for _ in secilenler)
    conn.execute(f"DELETE FROM demirbaslar WHERE id IN ({placeholders})", secilenler)
    conn.commit(); conn.close()
    
    log_kaydet(f"{len(secilenler)} Kayıt Silindi", "Toplu İşlem", "Silme")
    return redirect(url_for('index', tab='demirbas'))

@app.route('/toplu-yazdir-demirbas', methods=['GET', 'POST'])
@login_required
def toplu_yazdir_demirbas():
    if request.method == 'POST': secilenler = request.form.getlist('secilen_ids')
    else: secilenler = request.args.get('ids', '').split(',')
    if not secilenler or secilenler == ['']: return redirect(url_for('index', tab='demirbas'))
    
    conn = baglanti_kur()
    placeholders = ', '.join('?' for _ in secilenler)
    cur = conn.execute(f"SELECT DISTINCT konum FROM demirbaslar WHERE id IN ({placeholders})", secilenler)
    konumlar = [row[0] for row in cur.fetchall()]
    conn.close()

    qr_listesi = []
    for konum in konumlar:
        hedef_url = url_for('ofis_detay', konum_adi=konum, _external=True)
        qr = qrcode.QRCode(box_size=10, border=2); qr.add_data(hedef_url); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO(); img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_listesi.append({'konum': konum, 'qr': qr_base64})
    return render_template('toplu_yazdir.html', qr_listesi=qr_listesi)

@app.route('/get-all-ids')
@login_required
def get_all_ids():
    tab = request.args.get('tab', 'demirbas')
    q = request.args.get('q', '').strip()
    
    # Yetki kontrollerini burada da yapmalıyız (Güvenlik)
    kullanici_yetki = int(session.get('yetki_duzeyi', 0))
    kullanici_birim = session.get('birim', 'Genel')
    izinli_kampus = BIRIM_KAMPUS_MAP.get(kullanici_birim, None)

    conn = baglanti_kur()
    cursor = conn.cursor()
    ids = []

    if tab == 'demirbas':
        sql = "SELECT id FROM demirbaslar WHERE 1=1"
        params = []

        # 1. YETKİ FİLTRESİ
        if kullanici_yetki == 1: # Birim Sorumlusu
             if izinli_kampus:
                sql += " AND kampus = ?"
                params.append(izinli_kampus)
        elif kullanici_yetki == 0: # Standart Personel
             # Hiçbir şey göremez
             sql += " AND 1=0"

        # 2. ARAMA FİLTRESİ
        if q:
            t = f"%{turkce_normalize(q)}%"
            sql += " AND (NORMALIZE(ad) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(kampus) LIKE ? OR NORMALIZE(cinsi) LIKE ?)"
            params.extend([t, t, t, t])
        
        cursor.execute(sql, params)
        ids = [str(r[0]) for r in cursor.fetchall()]

    elif tab == 'personel':
        sql = "SELECT id FROM personeller WHERE 1=1"
        params = []

        # 1. YETKİ FİLTRESİ
        if kullanici_yetki == 1:
            sql += " AND birimi = ?"
            params.append(kullanici_birim)
        elif kullanici_yetki == 0:
            sql += " AND 1=0"

        # 2. ARAMA FİLTRESİ
        if q:
            t = f"%{turkce_normalize(q)}%"
            sql += """ AND (
                        NORMALIZE(ad_soyad) LIKE ? OR 
                        NORMALIZE(unvan) LIKE ? OR 
                        NORMALIZE(birimi) LIKE ? OR 
                        NORMALIZE(kampus) LIKE ? OR 
                        NORMALIZE(ofis) LIKE ?
                    )"""
            params.extend([t, t, t, t, t])

        cursor.execute(sql, params)
        ids = [str(r[0]) for r in cursor.fetchall()]

    conn.close()
    return jsonify(ids)

@app.route('/sil-kullanici/<int:id>')
@login_required
def sil_kullanici(id):
    if session.get('rol') != 'admin': return redirect(url_for('index'))
    conn = baglanti_kur()
    conn.execute("DELETE FROM kullanicilar WHERE id=?", (id,))
    conn.commit(); conn.close()
    # DEĞİŞTİ: Silince tekrar listeyi aç
    return redirect(url_for('index', open_modal='userModal'))

@app.route('/ekle-ariza', methods=['POST'])
@login_required
def ekle_ariza():
    conn = baglanti_kur()
    
    konum = request.form.get('konum')
    baslik = request.form.get('baslik')
    aciklama = request.form.get('aciklama')
    oncelik = request.form.get('oncelik')
    
    # DÜZELTME: İsmi formdan değil, doğrudan oturumdan alıyoruz.
    # Böylece personel listesinde kendi kaydını %100 görür.
    bildiren = session.get('ad_soyad', 'Bilinmeyen Kullanıcı') 
    
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
    
    conn.execute("INSERT INTO arizalar (konum, baslik, aciklama, bildiren, oncelik, durum, tarih) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (konum, baslik, aciklama, bildiren, oncelik, 'Bekliyor', tarih))
    conn.commit()
    conn.close()
    
    log_kaydet("Arıza Bildirimi", f"{konum} - {baslik}", "Arıza")
    return redirect(request.referrer or url_for('index'))

@app.route('/guncelle-ariza-durum/<int:id>/<durum_kodu>')
@login_required
def guncelle_ariza_durum(id, durum_kodu):
    # Yetki Kontrolü
    if session.get('rol') != 'teknik' and session.get('rol') != 'admin':
        return redirect(url_for('index', tab='ariza'))

    # Kodları Türkçeye Çevir (URL'de Türkçe karakter sorunu olmasın diye)
    yeni_durum = ""
    if durum_kodu == 'islem':
        yeni_durum = "İşlemde"
    elif durum_kodu == 'tamam':
        yeni_durum = "Tamamlandı"
    else:
        # Tanımsız bir kod geldiyse işlem yapma
        return redirect(url_for('index', tab='ariza'))

    islem_yapan = session.get('ad_soyad', 'Teknik Servis')
    conn = baglanti_kur()
    conn.execute("UPDATE arizalar SET durum=? WHERE id=?", (yeni_durum, id))
    conn.commit()
    conn.close()
    
    # Loglama yaparken Türkçe halini kullan
    log_kaydet(f"Arıza Durumu Değişti: {yeni_durum}", f"ID: {id}", "Arıza")
    
    return redirect(request.referrer or url_for('index'))

@app.route('/sil-ariza/<int:id>')
@login_required
def sil_ariza(id):
    conn = baglanti_kur(); conn.execute("DELETE FROM arizalar WHERE id=?", (id,)); conn.commit(); conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/iptal-et-ariza', methods=['POST'])
@login_required
def iptal_et_ariza():
    # Sadece Teknik Servis İptal Edebilir
    if session.get('rol') != 'teknik':
        return redirect(url_for('index', tab='ariza'))
        
    a_id = request.form.get('ariza_id')
    neden = request.form.get('iptal_nedeni')
    
    conn = baglanti_kur()
    conn.execute("UPDATE arizalar SET durum='İptal Edildi', iptal_nedeni=? WHERE id=?", (neden, a_id))
    conn.commit()
    conn.close()
    
    log_kaydet(f"Arıza İptal Edildi", f"ID: {a_id} - Neden: {neden}", "Arıza")
    return redirect(url_for('index', tab='ariza'))

@app.route('/ekle-kullanici', methods=['POST'])
@login_required
def ekle_kullanici():
    # Sadece Admin işlem yapabilir
    if session.get('rol') != 'admin': 
        return redirect(url_for('index'))
        
    kadi = request.form.get('kullanici_adi')
    sifre = request.form.get('sifre')
    ad_soyad = request.form.get('ad_soyad')
    rol = request.form.get('rol')
    birim = request.form.get('birim')
    
    # Formdan gelen yetki düzeyi (String olduğu için int'e çeviriyoruz)
    try:
        yetki_duzeyi = int(request.form.get('yetki_duzeyi', 0))
    except:
        yetki_duzeyi = 0

    # --- GÜVENLİK DUVARI: ADMİN OLUŞTURMAYI ENGELLE ---
    if rol == 'admin' or yetki_duzeyi >= 3:
        # Biri sistemi kandırmaya çalışıyor!
        flash("Güvenlik Uyarısı: Panelden yönetici oluşturulamaz!", "error")
        return redirect(url_for('index', open_modal='userModal'))
    # --------------------------------------------------

    # TARİH BİLGİSİ
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M") 
    sifre_hash = generate_password_hash(sifre)
    
    conn = baglanti_kur()
    try:
        conn.execute("""INSERT INTO kullanicilar 
                        (kullanici_adi, sifre_hash, ad_soyad, rol, birim, yetki_duzeyi, tarih) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (kadi, sifre_hash, ad_soyad, rol, birim, yetki_duzeyi, tarih))
        conn.commit()
        log_kaydet("Kullanıcı Eklendi", f"{kadi} ({birim})", "Ekleme")
    except sqlite3.IntegrityError: 
        flash("Bu kullanıcı adı zaten kullanılıyor!", "warning")
    finally: 
        conn.close()
    
    return redirect(url_for('index', open_modal='userModal'))

@app.route('/guncelle-kullanici', methods=['POST'])
@login_required
def guncelle_kullanici():
    # ... fonksiyonun başı ...
    rol = request.form.get('rol')
    try:
        yetki_duzeyi = int(request.form.get('yetki_duzeyi', 0))
    except:
        yetki_duzeyi = 0

    # GÜVENLİK DUVARI
    if rol == 'admin' or yetki_duzeyi >= 3:
        return redirect(url_for('index'))
    # ... devamı ...
    # Güvenlik: Sadece admin yapabilir
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))

    # Formdan gelen veriler
    user_id = request.form.get('user_id')
    ad_soyad = request.form.get('ad_soyad')
    kadi = request.form.get('kullanici_adi')
    rol = request.form.get('rol')
    birim = request.form.get('birim')
    yetki_duzeyi = request.form.get('yetki_duzeyi')
    sifre = request.form.get('sifre') # Boş gelebilir

    conn = baglanti_kur()
    
    if sifre and sifre.strip() != "":
        # Şifre girilmişse onu da güncelle (Hashleyerek)
        sifre_hash = generate_password_hash(sifre)
        conn.execute("""UPDATE kullanicilar 
                        SET ad_soyad=?, kullanici_adi=?, rol=?, birim=?, yetki_duzeyi=?, sifre_hash=? 
                        WHERE id=?""", 
                     (ad_soyad, kadi, rol, birim, yetki_duzeyi, sifre_hash, user_id))
        log_kaydet("Kullanıcı Güncellendi (Şifre Dahil)", f"{kadi}", "Düzenleme")
    else:
        # Şifre boşsa sadece bilgileri güncelle
        conn.execute("""UPDATE kullanicilar 
                        SET ad_soyad=?, kullanici_adi=?, rol=?, birim=?, yetki_duzeyi=? 
                        WHERE id=?""", 
                     (ad_soyad, kadi, rol, birim, yetki_duzeyi, user_id))
        log_kaydet("Kullanıcı Bilgileri Güncellendi", f"{kadi}", "Düzenleme")

    conn.commit()
    conn.close()
    # DEĞİŞTİ: Güncelleyince tekrar listeyi aç
    return redirect(url_for('index', open_modal='userModal'))
@app.route('/yerleske-duzelt')
@login_required
def yerleske_duzelt():
    if session.get('rol') != 'admin': return redirect(url_for('index'))
    
    conn = baglanti_kur()
    try:
        # 1. 'Ömer Yıldız Yerleşkesi' yazanları -> 'Yalıncak Yerleşkesi' yap
        conn.execute("UPDATE demirbaslar SET kampus='Yalıncak Yerleşkesi' WHERE kampus LIKE '%Ömer Yıldız%'")
        
        # 2. Sadece 'Yomra Yerleşkesi' yazanları -> 'Kaşüstü (Yomra) Yerleşkesi' yap
        conn.execute("UPDATE demirbaslar SET kampus='Kaşüstü (Yomra) Yerleşkesi' WHERE kampus='Yomra Yerleşkesi'")
        
        conn.commit()
        log_kaydet("Sistem Bakımı", "Yerleşke isimleri standartlaştırıldı.", "Düzeltme")
    except Exception as e:
        print(f"Hata: {e}")
    finally:
        conn.close()
        
    return redirect(url_for('index'))

# --- PERSONEL TOPLU İŞLEMLERİ ---

@app.route('/toplu-sil-personel', methods=['POST'])
@login_required
def toplu_sil_personel():
    # Sadece Admin Silebilir
    if session.get('rol') != 'admin':
        return redirect(url_for('index', tab='personel'))
        
    ids = request.form.getlist('secilen_ids') # Checkboxlardan gelen ID listesi
    
    if not ids:
        flash("Silinecek personel seçilmedi.", "warning")
        return redirect(url_for('index', tab='personel'))
        
    conn = baglanti_kur()
    try:
        # ID listesini virgüllü stringe çevir (1,2,5 gibi) güvenli parametre için
        placeholders = ','.join('?' for _ in ids)
        conn.execute(f"DELETE FROM personeller WHERE id IN ({placeholders})", ids)
        conn.commit()
        log_kaydet("Toplu Personel Silme", f"{len(ids)} adet personel silindi.", "Silme")
        flash(f"{len(ids)} personel başarıyla silindi.", "success")
    except Exception as e:
        flash(f"Hata oluştu: {e}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('index', tab='personel'))

@app.route('/toplu-tasi-personel', methods=['POST'])
@login_required
def toplu_tasi_personel():
    # Yetki Kontrolü
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index', tab='personel'))

    ids = request.form.getlist('secilen_ids')
    yeni_birim = request.form.get('yeni_birim')
    yeni_kampus = request.form.get('yeni_kampus')
    yeni_ofis = request.form.get('yeni_ofis')
    
    if not ids:
        flash("Taşınacak personel seçilmedi.", "warning")
        return redirect(url_for('index', tab='personel'))
        
    conn = baglanti_kur()
    try:
        placeholders = ','.join('?' for _ in ids)
        # Güncelleme Sorgusu
        sql = f"UPDATE personeller SET ofis = ?"
        params = [yeni_ofis]
        
        # Eğer birim ve kampüs seçildiyse onları da güncelle
        if yeni_birim:
            sql += ", birimi = ?"
            params.append(yeni_birim)
        if yeni_kampus:
            sql += ", kampus = ?"
            params.append(yeni_kampus)
            
        sql += f" WHERE id IN ({placeholders})"
        params.extend(ids)
        
        conn.execute(sql, params)
        conn.commit()
        log_kaydet("Toplu Personel Taşıma", f"{len(ids)} kişi yeni ofise ({yeni_ofis}) taşındı.", "Düzenleme")
        flash(f"{len(ids)} personel başarıyla taşındı.", "success")
    except Exception as e:
        flash(f"Hata oluştu: {e}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('index', tab='personel'))
    
# Not: Toplu yazdırma için mevcut yazdırma sayfasını güncelleyeceğiz.

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)