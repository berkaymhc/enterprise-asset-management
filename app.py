from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, session, flash
import sqlite3
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
import math # Eğer yoksa bunu da ekle (sayfalama için kullanılıyor)
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
# --- TELEFON FORMATLAMA YARDIMCISI ---
def format_telefon(tel):
    if not tel:
        return ""
    # Sadece rakamları al (boşluk, parantez vb. temizle)
    temiz = ''.join(filter(str.isdigit, str(tel)))
    
    # En az 10 hane varsa son 10 haneyi al (başındaki 0 veya 90'ı atmak için)
    if len(temiz) >= 10:
        temiz = temiz[-10:]
        # Formatla: +90 5XX XXX XX XX
        return f"+90 {temiz[:3]} {temiz[3:6]} {temiz[6:8]} {temiz[8:]}"
    
    return tel # Eğer numara çok kısaysa veya bozuksa olduğu gibi döndür

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
    izinli_kampus = BIRIM_KAMPUS_MAP.get(kullanici_birim, None)
    
    # Otomatik Sekme Yönlendirmesi
    if not aktif_tab:
        if kullanici_yetki == 0 or kullanici_rol == 'teknik':
            aktif_tab = 'ariza'
        else:
            aktif_tab = 'demirbas'

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

    # ==========================================
    # 0. ÖNCE İSTATİSTİK VERİLERİNİ HAZIRLA (SIRALAMA DÜZELTİLDİ)
    # ==========================================
    # Bu blok grafiklerden ÖNCE gelmeli ki 'analiz_sonuclari' tanımlansın.
    
    analiz_sonuclari = []
    analiz_toplam = 0
    
    # Eğer aktif sekme istatistik ise ve bir filtreleme yapılmışsa
    if aktif_tab == 'istatistik':
        if analiz_turu == 'personel':
            p_analiz_sql = "SELECT * FROM personeller WHERE 1=1"
            p_analiz_params = []
            
            if ist_p_ad: 
                p_analiz_sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ?)"
                p_analiz_params.extend([f"%{turkce_normalize(ist_p_ad)}%", f"%{turkce_normalize(ist_p_ad)}%"])
            if ist_p_birim: 
                p_analiz_sql += " AND NORMALIZE(birimi) LIKE ?"
                p_analiz_params.append(f"%{turkce_normalize(ist_p_birim)}%")
            if ist_p_kampus and ist_p_kampus != "Tümü": 
                p_analiz_sql += " AND kampus = ?"
                p_analiz_params.append(ist_p_kampus)
            if ist_p_ofis: 
                p_analiz_sql += " AND NORMALIZE(ofis) LIKE ?"
                p_analiz_params.append(f"%{turkce_normalize(ist_p_ofis)}%")
            
            p_analiz_sql += " ORDER BY birimi ASC, ad_soyad ASC"
            cur.execute(p_analiz_sql, p_analiz_params)
            analiz_sonuclari = cur.fetchall()
            analiz_toplam = len(analiz_sonuclari)

        else: # Demirbaş Analizi
            d_analiz_sql = "SELECT ad, kampus, konum, SUM(adet) as toplam_adet FROM demirbaslar WHERE 1=1"
            d_analiz_params = []
            
            if ist_malzeme: 
                d_analiz_sql += " AND NORMALIZE(ad) LIKE ?"
                d_analiz_params.append(f"%{turkce_normalize(ist_malzeme)}%")
            if ist_kampus and ist_kampus != "Tümü": 
                d_analiz_sql += " AND kampus = ?"
                d_analiz_params.append(ist_kampus)
            if ist_konum: 
                d_analiz_sql += " AND NORMALIZE(konum) LIKE ?"
                d_analiz_params.append(f"%{turkce_normalize(ist_konum)}%")
            
            d_analiz_sql += " GROUP BY ad, kampus, konum ORDER BY kampus ASC, konum ASC"
            
            if request.args.get('analiz_turu'):
                cur.execute(d_analiz_sql, d_analiz_params)
                analiz_sonuclari = cur.fetchall()
                analiz_toplam = sum(row['toplam_adet'] for row in analiz_sonuclari)
    
    # ==========================================
    # 1. GRAFİK VERİLERİ (ARTIK analiz_sonuclari TANIMLI)
    # ==========================================
    
    chart_kampus_labels=[]; chart_kampus_values=[]
    chart_esya_labels=[]; chart_esya_values=[]
    chart_personel_labels=[]; chart_personel_values=[]
    chart_tur_labels=[]; chart_tur_values=[]
    
    f_labels_1=[]; f_values_1=[]; f_labels_2=[]; f_values_2=[]

    if kullanici_yetki >= 1:
        # A) GENEL DASHBOARD
        cur.execute("SELECT kampus, SUM(adet) FROM demirbaslar GROUP BY kampus")
        veriler = cur.fetchall()
        chart_kampus_labels = [row[0] for row in veriler]
        chart_kampus_values = [row[1] for row in veriler]

        cur.execute("SELECT cinsi, SUM(adet) FROM demirbaslar WHERE cinsi IS NOT NULL AND cinsi != '' GROUP BY cinsi")
        veriler = cur.fetchall()
        chart_tur_labels = [row[0] for row in veriler]
        chart_tur_values = [row[1] for row in veriler]

        cur.execute("SELECT ad, SUM(adet) as top FROM demirbaslar GROUP BY ad ORDER BY top DESC LIMIT 5")
        veriler = cur.fetchall()
        chart_esya_labels = [row[0] for row in veriler]
        chart_esya_values = [row[1] for row in veriler]

        cur.execute("SELECT birimi, COUNT(*) FROM personeller GROUP BY birimi ORDER BY COUNT(*) DESC LIMIT 8")
        veriler = cur.fetchall()
        chart_personel_labels = [row[0] for row in veriler]
        chart_personel_values = [row[1] for row in veriler]

        # B) FİLTRELİ SONUÇ GRAFİKLERİ
        # (Burada hata alıyordun, artık almayacaksın çünkü analiz_sonuclari yukarıda tanımlandı)
        if analiz_sonuclari:
            temp_1 = {}
            temp_2 = {}
            
            if analiz_turu == 'personel':
                for row in analiz_sonuclari:
                    k = row['kampus'] if row['kampus'] else "Belirtilmedi"
                    u = row['unvan'] if row['unvan'] else "Diğer"
                    temp_1[k] = temp_1.get(k, 0) + 1
                    temp_2[u] = temp_2.get(u, 0) + 1
            else:
                for row in analiz_sonuclari:
                    k = row['kampus']
                    if 'toplam_adet' in row.keys(): 
                        adet = row['toplam_adet']
                    else: 
                        adet = row['adet']
                    
                    temp_1[k] = temp_1.get(k, 0) + adet
                    konum_ozet = row['konum'].split('/')[0].strip()
                    temp_2[konum_ozet] = temp_2.get(konum_ozet, 0) + adet

            f_labels_1 = list(temp_1.keys())
            f_values_1 = list(temp_1.values())
            f_labels_2 = list(temp_2.keys())
            f_values_2 = list(temp_2.values())

    # ==========================================
    # 2. DEMİRBAŞ ve PERSONEL LİSTE SORGULARI
    # ==========================================
    d_sql = "SELECT * FROM demirbaslar WHERE 1=1"
    d_params = []
    
    p_sql = "SELECT * FROM personeller WHERE 1=1"
    p_params = []

    # Yetki Seviyeleri
    if kullanici_yetki >= 3:
        pass 
    elif kullanici_yetki == 2:
        pass
    elif kullanici_yetki == 1:
        p_sql += " AND birimi = ?"
        p_params.append(kullanici_birim)
        if izinli_kampus:
            d_sql += " AND kampus = ?"
            d_params.append(izinli_kampus)
    else:
        p_sql += " AND 1=0" 
        d_sql += " AND 1=0"

    # Arama Filtresi
    if arama_terimi:
        t = f"%{turkce_normalize(arama_terimi)}%"
        if aktif_tab == 'demirbas':
            d_sql += " AND (NORMALIZE(ad) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(kampus) LIKE ?)"
            d_params.extend([t, t, t])
        elif aktif_tab == 'personel':
            p_sql += """ AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(unvan) LIKE ? OR NORMALIZE(birimi) LIKE ? OR NORMALIZE(kampus) LIKE ? OR NORMALIZE(ofis) LIKE ?)"""
            p_params.extend([t, t, t, t, t])
    
    # Demirbaşları Çek
    cur.execute(d_sql.replace("SELECT *", "SELECT COUNT(*)"), d_params)
    total_d = cur.fetchone()[0]
    toplam_sayfa_demirbas = math.ceil(total_d / limit) if total_d > 0 else 1
    
    cur.execute(d_sql + " ORDER BY id DESC LIMIT ? OFFSET ?", d_params + [limit, offset_d])
    demirbaslar = cur.fetchall()
    
    # Personelleri Çek
    cur.execute(p_sql.replace("SELECT *", "SELECT COUNT(*)"), p_params)
    total_p = cur.fetchone()[0]
    toplam_sayfa_personel = math.ceil(total_p / limit) if total_p > 0 else 1
    
    cur.execute(p_sql + " ORDER BY ofis ASC LIMIT ? OFFSET ?", p_params + [limit, offset_p])
    personeller = cur.fetchall()

    # ==========================================
    # --- ARIZA SORGUSU (GÜNCELLENDİ: SAYFALAMA EKLENDİ) ---
    # ==========================================
    
    # 1. Sayfalama Ayarları
    sayfa_a = request.args.get('sayfa_a', 1, type=int)
    limit_ariza = 5  # İsteğin üzerine sayfada 5 arıza
    offset_a = (sayfa_a - 1) * limit_ariza

    a_sql = "SELECT * FROM arizalar WHERE 1=1"
    a_params = []
    mevcut_kisi = session.get('ad_soyad', '')

    # 2. Yetki Filtresi (Normal personel sadece kendi bildirdiklerini görür)
    if kullanici_rol not in ['admin', 'teknik']:
        a_sql += " AND bildiren = ?"
        a_params.append(mevcut_kisi)
    
    # 3. Arama Filtresi (Eğer arama yapılıyorsa Arızalarda da ara)
    if arama_terimi and aktif_tab == 'ariza':
        t = f"%{turkce_normalize(arama_terimi)}%"
        a_sql += " AND (NORMALIZE(baslik) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(aciklama) LIKE ?)"
        a_params.extend([t, t, t])

    # 4. Toplam Arıza Sayısını Bul (Sayfalama butonları için)
    count_sql = a_sql.replace("SELECT *", "SELECT COUNT(*)")
    cur.execute(count_sql, a_params)
    total_ariza = cur.fetchone()[0]
    toplam_sayfa_ariza = math.ceil(total_ariza / limit_ariza) if total_ariza > 0 else 1

    # 5. Verileri Çek (LIMIT ve OFFSET ile + Akıllı Sıralama)
    # Sıralama: Önce 'Bekliyor', Sonra 'İşlemde', En son 'Tamamlandı/İptal'
    a_sql += """ ORDER BY 
                 CASE durum 
                    WHEN 'Bekliyor' THEN 1 
                    WHEN 'İşlemde' THEN 2 
                    ELSE 3 
                 END, id DESC 
                 LIMIT ? OFFSET ?"""
    
    a_params.extend([limit_ariza, offset_a])
    
    cur.execute(a_sql, a_params)
    arizalar = cur.fetchall()
    
    # 6. Bildirim Rozeti İçin Sayı (Sayfalamadan bağımsız toplam bekleyen sayısı)
    bildirim_sayisi = 0
    if kullanici_rol in ['admin', 'teknik']:
        cur.execute("SELECT COUNT(*) FROM arizalar WHERE durum='Bekliyor'")
        bildirim_sayisi = cur.fetchone()[0]
    else:
        # Personel sadece kendi bekleyenlerini görsün (opsiyonel)
        cur.execute("SELECT COUNT(*) FROM arizalar WHERE bildiren=? AND durum='Bekliyor'", (mevcut_kisi,))
        bildirim_sayisi = cur.fetchone()[0]

    # --- GEÇMİŞ VERİLERİ (Aynı kalıyor) ---
    cur.execute("SELECT * FROM yukleme_gecmisi WHERE tur = 'Yükleme' ORDER BY id DESC LIMIT 1")
    son_yukleme = cur.fetchone()
    
    cur.execute("SELECT * FROM yukleme_gecmisi ORDER BY id DESC LIMIT 100")
    tum_gecmis = cur.fetchall()

    # --- KULLANICI LİSTESİ (Aynı kalıyor) ---
    kullanicilar_listesi = []
    if session.get('rol') == 'admin':
        cur.execute("SELECT * FROM kullanicilar ORDER BY id ASC")
        kullanicilar_listesi = cur.fetchall()
    
    aktif_kullanici_ofis = ""
    if kullanici_rol == 'personel':
        cur.execute("SELECT kampus, ofis FROM personeller WHERE ad_soyad = ?", (session.get('ad_soyad'),))
        personel_kaydi = cur.fetchone()
        if personel_kaydi:
            aktif_kullanici_ofis = f"{personel_kaydi['kampus']} / {personel_kaydi['ofis']}"

    conn.close()

    return render_template('index.html', 
                           aktif_tab=aktif_tab,
                           demirbaslar=demirbaslar,
                           personeller=personeller,
                           arizalar=arizalar,
                           bildirim_sayisi=bildirim_sayisi,
                           sayfa_a=sayfa_a,
                           toplam_sayfa_ariza=toplam_sayfa_ariza,
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
    if 'dosya' not in request.files: 
        return redirect(url_for('index'))
        
    dosyalar = request.files.getlist('dosya')
    hedef_kampus = request.form.get('hedef_kampus', 'Merkez')
    bina_kat = request.form.get('bina_kat', '')
    
    conn = baglanti_kur()
    cur = conn.cursor()
    islem_yapildi = False
    toplam_eklenen = 0

    for dosya in dosyalar:
        if dosya.filename == '': continue
        try:
            # Dosya adından konum türetme mantığın (Korundu)
            dosya_adi_temiz = dosya.filename.rsplit('.', 1)[0].replace('_', ' ').title()
            
            wb = openpyxl.load_workbook(dosya)
            for ws in wb.worksheets:
                # Konum birleştirme
                tam_konum = " / ".join([p for p in [bina_kat, dosya_adi_temiz, ws.title] if p])
                
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or row[0] is None: continue
                    
                    ad = row[0]
                    cinsi = row[1] if len(row) > 1 else ""
                    
                    # Adet sayısını güvenli alma
                    try: 
                        adet = int(row[2]) if len(row) > 2 and row[2] else 1
                    except: 
                        adet = 1
                    
                    # Aynı demirbaş aynı konumda var mı?
                    cur.execute("SELECT id FROM demirbaslar WHERE ad=? AND konum=?", (ad, tam_konum))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO demirbaslar (ad, cinsi, kampus, konum, adet, tarih) 
                            VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
                        """, (ad, cinsi, hedef_kampus, tam_konum, adet))
                        toplam_eklenen += 1
                        islem_yapildi = True

        except Exception as e:
            print(f"Hata ({dosya.filename}): {e}")
            continue

    conn.commit()
    conn.close()

    if islem_yapildi:
        try: log_kaydet(f"{len(dosyalar)} Dosya Yüklendi", f"{bina_kat} - {toplam_eklenen} Eşya", "Yükleme")
        except: pass
        flash(f"{toplam_eklenen} adet demirbaş başarıyla sisteme eklendi.", "success")
    else:
        flash("Yeni demirbaş eklenmedi. Dosyaları kontrol edin.", "warning")

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
    if 'dosya' not in request.files: 
        return redirect(url_for('index'))
    
    dosya = request.files['dosya']
    
    if dosya and dosya.filename != '':
        try:
            conn = baglanti_kur()
            cur = conn.cursor()
            wb = openpyxl.load_workbook(dosya)
            ws = wb.active
            
            eklenen_sayisi = 0
            
            # Excel'i satır satır oku (Başlık hariç)
            for row in ws.iter_rows(min_row=2, values_only=True):
                # Satır boşsa atla
                if not row or row[0] is None: continue
                
                # --- VERİLERİ OKU ---
                # Şablon Sırası: 0:Ad, 1:Ünvan, 2:Birim, 3:Kampüs, 4:Ofis, 5:Telefon, 6:E-Posta
                ad_soyad = row[0]
                unvan = row[1] if len(row) > 1 and row[1] else ""
                birim = row[2] if len(row) > 2 and row[2] else ""
                kampus = row[3] if len(row) > 3 and row[3] else "Merkez"
                ofis = row[4] if len(row) > 4 and row[4] else ""
                
                # ÖNCEKİ KODDA TERS OLAN KISIM DÜZELTİLDİ:
                # row[5] -> Telefon (Şablonda 6. sütun)
                telefon = str(row[5]) if len(row) > 5 and row[5] else ""
                
                # row[6] -> E-Posta (Şablonda 7. sütun)
                email = row[6] if len(row) > 6 and row[6] else ""
                
                # Mükerrer Kayıt Kontrolü (Ad Soyad ve Ofis aynıysa ekleme)
                cur.execute("SELECT id FROM personeller WHERE ad_soyad=? AND ofis=?", (ad_soyad, ofis))
                if not cur.fetchone():
                    # Yoksa EKLE (Tarih eklendi)
                    cur.execute("""
                        INSERT INTO personeller (ad_soyad, unvan, birimi, kampus, ofis, telefon, email, tarih) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                    """, (ad_soyad, unvan, birim, kampus, ofis, telefon, email))
                    eklenen_sayisi += 1
            
            conn.commit()
            conn.close()
            
            if eklenen_sayisi > 0:
                # log_kaydet fonksiyonun varsa kullan, yoksa flash mesajı yeterli
                try: log_kaydet(f"Personel Listesi Yüklendi", f"{eklenen_sayisi} Kişi Eklendi", "Yükleme")
                except: pass
                
                flash(f"{eklenen_sayisi} yeni personel başarıyla yüklendi.", "success")
            else:
                flash("Yüklenecek yeni personel bulunamadı veya hepsi zaten kayıtlı.", "warning")
                
        except Exception as e:
            flash(f"Dosya yüklenirken hata oluştu: {str(e)}", "danger")
            
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

# --- EXCEL ŞABLONU İNDİRME (GÜNCELLENDİ) ---
@app.route('/indir-sablon/<tur>')
@login_required
def indir_sablon(tur):
    wb = Workbook()
    ws = wb.active
    ws.title = "Örnek Şablon"
    
    # Başlık Stili
    bold_font = Font(bold=True)
    
    if tur == 'personel':
        # Personel Sütunları (Telefon ve Mail Eklendi)
        headers = ['Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis', 'Telefon', 'E-Posta']
        ws.append(headers)
        
        # Örnek Veri (Kullanıcı ne yazacağını anlasın diye)
        ws.append(['Ali Yılmaz', 'Memur', 'Bilgi İşlem', 'Yalıncak Yerleşkesi', 'Z-23', '5551234567', 'ali@ornek.com'])
        
        # Sütun Genişlikleri
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 20
        ws.column_dimensions['G'].width = 25

    else:
        # Demirbaş Sütunları
        headers = ['Malzeme Adı', 'Cinsi', 'Kampüs', 'Konum', 'Adet']
        ws.append(headers)
        
        # Örnek Veri
        ws.append(['Çalışma Masası', 'Mobilya', 'Yalıncak Yerleşkesi', 'B-Blok 105', 1])
        
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 20

    # Başlıkları Kalın Yap
    for cell in ws[1]:
        cell.font = bold_font
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    dosya_adi = f"Ornek_{tur.capitalize()}_Sablonu.xlsx"
    return send_file(output, as_attachment=True, download_name=dosya_adi, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/rapor')
@login_required
def rapor():
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index'))

    conn = baglanti_kur()
    cur = conn.cursor()
    
    # DÜZELTME: openpyxl.Workbook() olarak tam adıyla çağırıyoruz
    wb = openpyxl.Workbook()
    
    # ---------------------------------------------------------
    # 1. SAYFA: DEMİRBAŞ LİSTESİ
    # ---------------------------------------------------------
    ws1 = wb.active
    ws1.title = "Demirbaş Listesi"
    ws1.append(['ID', 'Malzeme Adı', 'Cinsi', 'Kampüs', 'Konum', 'Adet', 'Eklenme Tarihi'])
    
    bold_font = Font(bold=True)
    for cell in ws1[1]: cell.font = bold_font
    
    d_sql = "SELECT * FROM demirbaslar"
    d_params = []
    
    if int(session.get('yetki_duzeyi')) == 1:
        k_birim = session.get('birim')
        izinli_yer = BIRIM_KAMPUS_MAP.get(k_birim)
        if izinli_yer:
            d_sql += " WHERE kampus = ?"
            d_params.append(izinli_yer)
            
    cur.execute(d_sql, d_params)
    for d in cur.fetchall():
        # Demirbaşlarda tarih sütunu kesin var mı kontrolü (Garanti olsun)
        d_tarih = d['tarih'] if 'tarih' in d.keys() else ""
        ws1.append([d['id'], d['ad'], d['cinsi'], d['kampus'], d['konum'], d['adet'], d_tarih])

    # ---------------------------------------------------------
    # 2. SAYFA: PERSONEL LİSTESİ (HATA BURADAYDI, DÜZELTİLDİ)
    # ---------------------------------------------------------
    ws2 = wb.create_sheet(title="Personel Listesi")
    ws2.append(['ID', 'Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis', 'Telefon', 'E-Posta', 'Kayıt Tarihi'])
    for cell in ws2[1]: cell.font = bold_font
    
    p_sql = "SELECT * FROM personeller"
    p_params = []
    
    if int(session.get('yetki_duzeyi')) == 1:
        p_sql += " WHERE birimi = ?"
        p_params.append(session.get('birim'))
        
    cur.execute(p_sql, p_params)
    for p in cur.fetchall():
        # --- HATA ÇÖZÜMÜ ---
        # Veritabanında 'tarih' sütunu olmayabilir. Kontrollü alıyoruz.
        # sqlite3.Row objesi olduğu için keys() ile kontrol edebiliriz.
        p_tarih = p['tarih'] if 'tarih' in p.keys() else "-"
        
        # Telefon formatlama (Fonksiyon yukarıda tanımlı varsayıyoruz)
        tel_formati = format_telefon(p['telefon']) if 'telefon' in p.keys() else ""
        
        ws2.append([
            p['id'], 
            p['ad_soyad'], 
            p['unvan'], 
            p['birimi'], 
            p['kampus'], 
            p['ofis'],
            tel_formati,
            p['email'] if 'email' in p.keys() and p['email'] else "",
            p_tarih  # Artık hata vermeyecek, yoksa "-" yazacak
        ])

    # ---------------------------------------------------------
    # 3. SAYFA: ARIZA KAYITLARI
    # ---------------------------------------------------------
    ws3 = wb.create_sheet(title="Arıza Kayıtları")
    ws3.append(['ID', 'Konum', 'Başlık', 'Açıklama', 'Öncelik', 'Durum', 'Bildiren', 'İşlem Yapan', 'Tarih', 'İptal Nedeni'])
    for cell in ws3[1]: cell.font = bold_font
    
    cur.execute("SELECT * FROM arizalar")
    for a in cur.fetchall():
        ws3.append([
            a['id'], a['konum'], a['baslik'], a['aciklama'], 
            a['oncelik'], a['durum'], a['bildiren'], a['islem_yapan'], 
            a['tarih'], a['iptal_nedeni']
        ])

    # Sütun Genişliklerini Ayarla
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
                except: pass
            adjusted_width = (max_length + 2)
            sheet.column_dimensions[column].width = adjusted_width

    conn.close()
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    dosya_adi = f"Genel_Rapor_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return send_file(output, as_attachment=True, download_name=dosya_adi, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/rapor-analiz')
@login_required
def rapor_analiz():
    if session.get('rol') == 'teknik' or int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('index'))

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
    ws = wb.active
    
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="198754", fill_type="solid")
    genel_toplam = 0

    if analiz_turu == 'personel':
        ws.title = "Personel Analiz"
        ws.append(['Sıra No', 'Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis', 'Telefon', 'E-Posta'])
        
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
        
        for i, row in enumerate(conn.execute(sql, params).fetchall(), 1):
            # FORMATLAMA BURADA YAPILIYOR
            tel_formati = format_telefon(row['telefon'])
            
            ws.append([
                i, 
                row['ad_soyad'], 
                row['unvan'], 
                row['birimi'], 
                row['kampus'], 
                row['ofis'],
                tel_formati,                        # Formatlı Telefon
                row['email'] if row['email'] else ""
            ])
            genel_toplam += 1
            
        ws.append(['', '', '', '', '', '', 'GENEL TOPLAM:', genel_toplam])

    else:
        # Demirbaş kısmı aynı kalıyor
        ws.title = "Demirbaş Analiz"
        ws.append(['Sıra No', 'Malzeme Adı', 'Kampüs', 'Konum / Ofis', 'Adet'])
        
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
        
        for i, row in enumerate(conn.execute(sql, params).fetchall(), 1):
            ws.append([i, row['ad'], row['kampus'], row['konum'], row['toplam_adet']])
            genel_toplam += row['toplam_adet']
            
        ws.append(['', '', '', 'GENEL TOPLAM:', genel_toplam])

    # Tasarım ve Genişlik Ayarları
    for cell in ws[1]: 
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
            except: pass
        ws.column_dimensions[column].width = (max_length + 2)

    conn.close()
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    dosya_adi = f"Analiz_Raporu_{analiz_turu}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(output, download_name=dosya_adi, as_attachment=True)

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
    # Güvenlik Kontrolü
    if session.get('yetki_duzeyi') < 1 and session.get('rol') != 'teknik':
        return jsonify({'status': 'error', 'msg': 'Yetkisiz işlem!'})

    secilen_ids = request.form.getlist('secilen_ids')
    yeni_kampus = request.form.get('yeni_kampus')
    yeni_konum = request.form.get('yeni_konum')

    if not secilen_ids:
        flash("Hiçbir demirbaş seçilmedi!", "warning")
        return redirect(url_for('index', tab='demirbas'))

    conn = baglanti_kur()
    cur = conn.cursor()

    try:
        # MANTIK DÜZELTİLDİ:
        
        # DURUM 1: Eğer yeni bir kampüs SEÇİLMİŞSE (Boş değilse)
        if yeni_kampus and yeni_kampus.strip() != "":
            # Hem Kampüsü Hem Konumu Güncelle
            for d_id in secilen_ids:
                cur.execute("UPDATE demirbaslar SET kampus = ?, konum = ? WHERE id = ?", (yeni_kampus, yeni_konum, d_id))
        
        # DURUM 2: Eğer kampüs SEÇİLMEMİŞSE ("Değişiklik Yapma" seçiliyse)
        else:
            # SADECE Konumu Güncelle (Kampüs sütununa dokunma, eskisi kalsın)
            for d_id in secilen_ids:
                cur.execute("UPDATE demirbaslar SET konum = ? WHERE id = ?", (yeni_konum, d_id))

        conn.commit()
        flash(f"{len(secilen_ids)} adet demirbaş başarıyla taşındı.", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"Hata oluştu: {str(e)}", "danger")
    finally:
        conn.close()

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

# --- 1. QR KODLARI TOPLU YAZDIRMA (TEK VE DOĞRU VERSİYON) ---
@app.route('/toplu-yazdir-demirbas', methods=['GET', 'POST'])
@login_required
def toplu_yazdir_demirbas():
    # 1. Seçilen ID'leri Al
    if request.method == 'POST': 
        secilenler = request.form.getlist('secilen_ids')
    else: 
        secilenler = request.args.get('ids', '').split(',')
    
    # Boş seçim kontrolü
    if not secilenler or secilenler == ['']: 
        return redirect(url_for('index', tab='demirbas'))
    
    conn = baglanti_kur()
    conn.row_factory = sqlite3.Row  # Sütun isimleriyle erişmek için
    
    # 2. Seçilen Eşyaların TÜM Bilgilerini Çek
    placeholders = ', '.join('?' for _ in secilenler)
    cur = conn.execute(f"SELECT * FROM demirbaslar WHERE id IN ({placeholders})", secilenler)
    demirbaslar = cur.fetchall()
    conn.close()

    qr_listesi = []
    
    for item in demirbaslar:
        # --- DEĞİŞİKLİK BURADA BAŞLIYOR (STATİK QR) ---
        
        # URL yerine doğrudan METİN oluşturuyoruz
        # Ters taksim n (\n) alt satıra geçmek içindir.
        qr_icerik = f"""DEMİRBAŞ BİLGİSİ
ID: {item['id']}
Ürün: {item['ad']}
Konum: {item['konum']}
Cinsi: {item['cinsi']}
Kayıt: {item['tarih']}"""
        
        # QR Oluşturma
        qr = qrcode.QRCode(box_size=10, border=2)
        
        # Link yerine hazırladığımız metni ekliyoruz
        qr.add_data(qr_icerik) 
        
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # Listeye Ekle (Burası Aynı)
        qr_listesi.append({
            'ad': item['ad'],
            'id': item['id'],
            'konum': item['konum'],
            'cinsi': item['cinsi'],
            'qr': qr_base64
        })
        # --- DEĞİŞİKLİK BİTTİ ---

    return render_template('toplu_yazdir.html', qr_listesi=qr_listesi)

# --- 2. QR OKUTMA / DETAY GÖRME (GÜNCELLENDİ: NOKTA ATIŞI KONTROL) ---
@app.route('/demirbas-detay/<int:id>')
def demirbas_detay(id):
    conn = baglanti_kur()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM demirbaslar WHERE id = ?", (id,))
    demirbas = cur.fetchone()
    
    if not demirbas:
        return "Demirbaş bulunamadı.", 404

    # ARTIK KONUMA GÖRE DEĞİL, ID'YE GÖRE ARIZA ARIYORUZ
    # durum != 'Tamamlandı' ve != 'İptal Edildi' ise arıza var demektir.
    cur.execute("""
        SELECT * FROM arizalar 
        WHERE demirbas_id = ? 
        AND durum NOT IN ('Tamamlandı', 'İptal Edildi')
        ORDER BY id DESC LIMIT 1
    """, (id,))
    
    aktif_ariza = cur.fetchone()
    conn.close()
    
    return render_template('detay.html', item=demirbas, ariza=aktif_ariza)

@app.route('/get-all-ids')
@login_required
def get_all_ids():
    tab = request.args.get('tab', 'demirbas')
    q = request.args.get('q', '').strip()
    
    # Yetki Bilgileri
    yetki = int(session.get('yetki_duzeyi', 0))
    rol = session.get('rol')
    birim = session.get('birim', 'Genel')
    izinli_kampus = BIRIM_KAMPUS_MAP.get(birim, None)

    conn = baglanti_kur()
    cursor = conn.cursor()
    ids = []

    if tab == 'demirbas':
        sql = "SELECT id FROM demirbaslar WHERE 1=1"
        params = []
        if yetki == 1 and izinli_kampus:
            sql += " AND kampus = ?"
            params.append(izinli_kampus)
        elif yetki == 0 and rol != 'teknik': # Teknik değilse ve yetki 0 ise görmesin
             sql += " AND 1=0"

        if q:
            t = f"%{turkce_normalize(q)}%"
            sql += " AND (NORMALIZE(ad) LIKE ? OR NORMALIZE(konum) LIKE ?)"
            params.extend([t, t])
        
        cursor.execute(sql, params)
        ids = [str(r[0]) for r in cursor.fetchall()]

    elif tab == 'personel':
        sql = "SELECT id FROM personeller WHERE 1=1"
        params = []
        if yetki == 1:
            sql += " AND birimi = ?"
            params.append(birim)
        elif yetki == 0 and rol != 'teknik':
            sql += " AND 1=0"

        if q:
            t = f"%{turkce_normalize(q)}%"
            sql += " AND (NORMALIZE(ad_soyad) LIKE ? OR NORMALIZE(ofis) LIKE ?)"
            params.extend([t, t])
            
        cursor.execute(sql, params)
        ids = [str(r[0]) for r in cursor.fetchall()]

    # --- BURAYI EKLEDİK (ARIZA İÇİN) ---
    elif tab == 'ariza':
        sql = "SELECT id FROM arizalar WHERE 1=1"
        params = []
        
        # Eğer Admin veya Teknik değilse SADECE kendi bildirdiklerini seçebilir
        if rol not in ['admin', 'teknik'] and yetki < 3:
            mevcut_kisi = session.get('ad_soyad', '')
            sql += " AND bildiren = ?"
            params.append(mevcut_kisi)
        
        # Arama filtresi varsa
        if q:
            t = f"%{turkce_normalize(q)}%"
            sql += " AND (NORMALIZE(baslik) LIKE ? OR NORMALIZE(konum) LIKE ? OR NORMALIZE(aciklama) LIKE ?)"
            params.extend([t, t, t])

        cursor.execute(sql, params)
        ids = [str(r[0]) for r in cursor.fetchall()]
    # -----------------------------------

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

# --- 1. ARIZA EKLEME (GÜNCELLENDİ: ID DESTEKLİ) ---
@app.route('/ekle-ariza', methods=['POST'])
@login_required
def ekle_ariza():
    conn = baglanti_kur()
    cur = conn.cursor()
    
    # 1. ID KONTROLÜ (Zorunlu)
    raw_id = request.form.get('demirbas_id')
    
    if not raw_id or raw_id.strip() == "":
        flash("HATA: Demirbaş ID girilmesi zorunludur!", "danger")
        return redirect(url_for('index', tab='ariza'))
        
    try:
        demirbas_id = int(raw_id)
    except ValueError:
        flash("HATA: Geçersiz ID formatı!", "danger")
        return redirect(url_for('index', tab='ariza'))

    # 2. KONUM KONTROLÜ (Otomatik Bulma)
    konum = request.form.get('konum')
    
    # Eğer konum boşsa, ID'den konumu bulmaya çalış
    if not konum or konum.strip() == "":
        cur.execute("SELECT konum FROM demirbaslar WHERE id = ?", (demirbas_id,))
        bulunan = cur.fetchone()
        if bulunan:
            konum = bulunan['konum']
        else:
            konum = "Konum Bulunamadı" # ID veritabanında yoksa

    baslik = request.form.get('baslik')
    aciklama = request.form.get('aciklama')
    oncelik = request.form.get('oncelik')
    bildiren = session.get('ad_soyad') or session.get('kullanici_adi')
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        cur.execute("""
            INSERT INTO arizalar (konum, baslik, aciklama, bildiren, oncelik, durum, tarih, demirbas_id) 
            VALUES (?, ?, ?, ?, ?, 'Bekliyor', ?, ?)
        """, (konum, baslik, aciklama, bildiren, oncelik, tarih, demirbas_id))
        conn.commit()
        
        log_msg = f"Arıza: {baslik} (ID: {demirbas_id})"
        try: log_kaydet("Arıza Bildirimi", log_msg, "Arıza")
        except: pass
        
        flash("Arıza kaydı oluşturuldu ve malzeme durumu güncellendi.", "success")
    except Exception as e:
        flash(f"Hata: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(request.referrer or url_for('index', tab='ariza'))


# --- ARIZA DURUM GÜNCELLEME (HATA DÜZELTİLDİ) ---
@app.route('/guncelle-ariza-durum/<int:id>/<durum_kodu>')
@login_required
def guncelle_ariza_durum(id, durum_kodu):
    # Yetki Kontrolü: Sadece Teknik VE Admin yapabilir
    if session.get('rol') not in ['teknik', 'admin']:
        return redirect(url_for('index', tab='ariza'))

    # Kodları Türkçeye Çevir
    yeni_durum = ""
    if durum_kodu == 'islem':
        yeni_durum = "İşlemde"
    elif durum_kodu == 'tamam':
        yeni_durum = "Tamamlandı"
    else:
        return redirect(url_for('index', tab='ariza'))

    # İşlemi yapanın adını al
    islem_yapan = session.get('ad_soyad', 'Yetkili Personel')
    
    conn = baglanti_kur()
    # islem_yapan sütununu da güncelliyoruz
    conn.execute("UPDATE arizalar SET durum=?, islem_yapan=? WHERE id=?", (yeni_durum, islem_yapan, id))
    conn.commit()
    conn.close()
    
    try: log_kaydet(f"Arıza Durumu: {yeni_durum}", f"ID: {id} - Yapan: {islem_yapan}", "Arıza")
    except: pass
    
    return redirect(request.referrer or url_for('index', tab='ariza'))

# --- ARIZA TOPLU SİLME ---
@app.route('/toplu-sil-ariza', methods=['POST'])
@login_required
def toplu_sil_ariza():
    # Sadece Admin ve Teknik Servis silebilir
    yetki = int(session.get('yetki_duzeyi', 0))
    rol = session.get('rol')
    
    if yetki < 3 and rol != 'teknik':
        flash("Bu işlem için yetkiniz yok!", "danger")
        return redirect(url_for('index', tab='ariza'))

    secilenler = request.form.getlist('secilen_ids')
    if not secilenler:
        return redirect(url_for('index', tab='ariza'))
    
    conn = baglanti_kur()
    try:
        placeholders = ','.join('?' for _ in secilenler)
        conn.execute(f"DELETE FROM arizalar WHERE id IN ({placeholders})", secilenler)
        conn.commit()
        
        log_kaydet(f"Toplu Arıza Silme", f"{len(secilenler)} adet kayıt silindi.", "Silme")
        flash(f"{len(secilenler)} adet arıza kaydı başarıyla silindi.", "success")
        
    except Exception as e:
        flash(f"Hata oluştu: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('index', tab='ariza'))

# --- ARIZA SİLME ---
@app.route('/sil-ariza/<int:id>')
@login_required
def sil_ariza(id):
    # Sadece Admin veya Teknik Silebilir
    if session.get('rol') != 'teknik' and int(session.get('yetki_duzeyi', 0)) < 3:
         flash("Silme yetkiniz yok.", "danger")
         return redirect(url_for('index', tab='ariza'))

    conn = baglanti_kur()
    conn.execute("DELETE FROM arizalar WHERE id=?", (id,))
    conn.commit()
    conn.close()
    
    flash("Arıza kaydı silindi.", "warning")
    return redirect(request.referrer or url_for('index', tab='ariza'))


# --- ARIZA İPTAL ETME ---
@app.route('/iptal-et-ariza', methods=['POST'])
@login_required
def iptal_et_ariza():
    # Yetki Kontrolü: Sadece Teknik VE Admin
    if session.get('rol') not in ['teknik', 'admin']:
        return redirect(url_for('index', tab='ariza'))
        
    a_id = request.form.get('ariza_id')
    neden = request.form.get('iptal_nedeni')
    islem_yapan = session.get('ad_soyad')
    
    conn = baglanti_kur()
    conn.execute("UPDATE arizalar SET durum='İptal Edildi', iptal_nedeni=?, islem_yapan=? WHERE id=?", (neden, islem_yapan, a_id))
    conn.commit()
    conn.close()
    
    try: log_kaydet(f"Arıza İptal Edildi", f"ID: {a_id} - Neden: {neden}", "Arıza")
    except: pass
    
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
    
    # --- GEÇİCİ GÜNCELLEME ROTASI (ÇALIŞTIRDIKTAN SONRA SİL) ---
@app.route('/db-guncelle')
def db_guncelle():
    conn = baglanti_kur()
    try:
        conn.execute("ALTER TABLE arizalar ADD COLUMN demirbas_id INTEGER")
        conn.commit()
        return "demirbas_id sütunu başarıyla eklendi!"
    except Exception as e:
        return f"Zaten ekli veya hata: {e}"
    finally:
        conn.close()
# Not: Toplu yazdırma için mevcut yazdırma sayfasını güncelleyeceğiz.

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=5000, debug=True) Sunucuyu dışarıya kapatmak
    app.run(debug=True)