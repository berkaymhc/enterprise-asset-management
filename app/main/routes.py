# app/main/routes.py - TAM VE DÜZELTİLMİŞ VERSİYON

import os
import math
from flask import render_template, request, session, redirect, url_for, jsonify, send_from_directory
from sqlalchemy import func, or_, case
from app.main import bp
from app.models import Demirbas, Personel, Ariza, YuklemeGecmisi, Kullanici
from app.utils import login_required, turkce_normalize
from app import db

# Sabitler
YERLESKELER = ["Yalıncak Yerleşkesi", "Pelitli Yerleşkesi", "Kaşüstü (Yomra) Yerleşkesi", "Çimenli Yerleşkesi"]
BIRIMLER = ["Bilgi İşlem Daire Başkanlığı", "İdari ve Mali İşler", "Personel Daire Başkanlığı", "Öğrenci İşleri", "Rektörlük", "Kütüphane", "SKS"]
UNVANLAR = ["Daire Başkanı", "Şube Müdürü", "Memur", "Tekniker", "Mühendis", "Sürekli İşçi"]

@bp.route('/')
@login_required
def index():
    # 1. TEMEL DEĞİŞKENLER
    aktif_tab = request.args.get('tab', 'demirbas')
    arama_terimi = request.args.get('q', '').strip()
    
    kullanici_yetki = int(session.get('yetki_duzeyi', 0))
    kullanici_birim = session.get('birim', 'Genel')
    kullanici_rol = session.get('rol')
    mevcut_kisi = session.get('ad_soyad', '')

    # Yetkiye göre varsayılan tab
    if not request.args.get('tab'):
        if kullanici_yetki == 0 or kullanici_rol == 'teknik':
            aktif_tab = 'ariza'
    
    # Sayfalama
    limit = 20
    sayfa_d = request.args.get('sayfa_d', 1, type=int)
    sayfa_p = request.args.get('sayfa_p', 1, type=int)
    
    # ==========================================
    # 2. İSTATİSTİK VE GRAFİK VERİLERİ (ORM)
    # ==========================================
    chart_kampus_labels, chart_kampus_values = [], []
    chart_esya_labels, chart_esya_values = [], []
    chart_personel_labels, chart_personel_values = [], []
    chart_tur_labels, chart_tur_values = [], []
    
    if kullanici_yetki >= 1:
        # Kampüs Dağılımı
        res_kampus = db.session.query(Demirbas.kampus, func.sum(Demirbas.adet)).group_by(Demirbas.kampus).all()
        chart_kampus_labels = [r[0] for r in res_kampus if r[0]]
        chart_kampus_values = [r[1] for r in res_kampus if r[0]]
        
        # En Çok Olan 5 Eşya
        res_esya = db.session.query(Demirbas.ad, func.sum(Demirbas.adet)).group_by(Demirbas.ad).order_by(func.sum(Demirbas.adet).desc()).limit(5).all()
        chart_esya_labels = [r[0] for r in res_esya]
        chart_esya_values = [r[1] for r in res_esya]

        # Personel Dağılımı
        res_per = db.session.query(Personel.birimi, func.count(Personel.id)).group_by(Personel.birimi).limit(8).all()
        chart_personel_labels = [r[0] for r in res_per if r[0]]
        chart_personel_values = [r[1] for r in res_per if r[0]]
        
        # Tür Dağılımı
        res_tur = db.session.query(Demirbas.cinsi, func.sum(Demirbas.adet)).filter(Demirbas.cinsi != "").group_by(Demirbas.cinsi).all()
        chart_tur_labels = [r[0] for r in res_tur]
        chart_tur_values = [r[1] for r in res_tur]

    # ==========================================
    # 3. DEMİRBAŞ SORGUSU
    # ==========================================
    query_d = Demirbas.query
    
    # Arama Filtresi
    if arama_terimi and aktif_tab == 'demirbas':
        t = f"%{turkce_normalize(arama_terimi)}%"
        query_d = query_d.filter(
            or_(
                func.NORMALIZE(Demirbas.ad).like(t),
                func.NORMALIZE(Demirbas.konum).like(t),
                func.NORMALIZE(Demirbas.kampus).like(t)
            )
        )
    
    total_d = query_d.count()
    toplam_sayfa_demirbas = math.ceil(total_d / limit)
    demirbaslar = query_d.order_by(Demirbas.id.desc()).paginate(page=sayfa_d, per_page=limit, error_out=False).items

    # ==========================================
    # 4. PERSONEL SORGUSU
    # ==========================================
    query_p = Personel.query
    
    if arama_terimi and aktif_tab == 'personel':
        t = f"%{turkce_normalize(arama_terimi)}%"
        query_p = query_p.filter(
            or_(
                func.NORMALIZE(Personel.ad_soyad).like(t),
                func.NORMALIZE(Personel.ofis).like(t)
            )
        )
        
    total_p = query_p.count()
    toplam_sayfa_personel = math.ceil(total_p / limit)
    personeller = query_p.order_by(Personel.ofis.asc()).paginate(page=sayfa_p, per_page=limit, error_out=False).items

    # ==========================================
    # 5. ARIZA SORGUSU
    # ==========================================
    query_a = Ariza.query
    
    # Normal kullanıcı sadece kendi bildirdiklerini görür
    if kullanici_rol not in ['admin', 'teknik'] and kullanici_yetki < 3:
        query_a = query_a.filter(Ariza.bildiren == mevcut_kisi)
        
    if arama_terimi and aktif_tab == 'ariza':
        t = f"%{turkce_normalize(arama_terimi)}%"
        query_a = query_a.filter(
            or_(
                func.NORMALIZE(Ariza.baslik).like(t),
                func.NORMALIZE(Ariza.konum).like(t)
            )
        )

    # Bildirim Rozeti
    if kullanici_rol in ['admin', 'teknik']:
        bildirim_sayisi = Ariza.query.filter_by(durum='Bekliyor').count()
    else:
        bildirim_sayisi = Ariza.query.filter_by(durum='Bekliyor', bildiren=mevcut_kisi).count()
        
    # Sıralama
    ozel_siralama = case(
        (Ariza.durum == 'Bekliyor', 1),
        (Ariza.durum == 'İşlemde', 2),
        else_=3
    )
    
    sayfa_a = request.args.get('sayfa_a', 1, type=int)
    limit_ariza = 5
    total_ariza = query_a.count()
    toplam_sayfa_ariza = math.ceil(total_ariza / limit_ariza)
    
    arizalar = query_a.order_by(ozel_siralama, Ariza.id.desc()).paginate(page=sayfa_a, per_page=limit_ariza, error_out=False).items

    # ==========================================
    # 6. DİĞER VERİLER
    # ==========================================
    son_yukleme = YuklemeGecmisi.query.filter_by(tur='Yükleme').order_by(YuklemeGecmisi.id.desc()).first()
    tum_gecmis = YuklemeGecmisi.query.order_by(YuklemeGecmisi.id.desc()).limit(100).all()
    
    kullanicilar_listesi = []
    if session.get('rol') == 'admin':
        kullanicilar_listesi = Kullanici.query.order_by(Kullanici.id.asc()).all()

    aktif_kullanici_ofis = ""
    
    # ==========================================
    # 7. İSTATİSTİK ANALİZ MANTIĞI (GÜNCELLENDİ)
    # ==========================================
    analiz_sonuclari = []
    analiz_toplam = 0
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    
    # Yeni Eklenen Kontrol: Butona basıldı mı?
    islem_turu = request.args.get('islem') 

    # Filtre Parametreleri
    ist_malzeme = request.args.get('ist_malzeme', '').strip()
    ist_kampus = request.args.get('ist_kampus', '')
    ist_konum = request.args.get('ist_konum', '').strip()
    ist_p_ad = request.args.get('ist_p_ad', '').strip()
    ist_p_birim = request.args.get('ist_p_birim', '').strip()
    ist_p_kampus = request.args.get('ist_p_kampus', '')
    ist_p_ofis = request.args.get('ist_p_ofis', '').strip()

    f_labels_1, f_values_1 = [], []
    f_labels_2, f_values_2 = [], []

    # SADECE "islem" parametresi "analiz" ise çalışsın
    if aktif_tab == 'istatistik' and islem_turu == 'analiz':
        
        if analiz_turu == 'personel':
            q = Personel.query
            if ist_p_ad:
                t = f"%{turkce_normalize(ist_p_ad)}%"
                q = q.filter(or_(func.NORMALIZE(Personel.ad_soyad).like(t), func.NORMALIZE(Personel.unvan).like(t)))
            if ist_p_birim:
                q = q.filter(func.NORMALIZE(Personel.birimi).like(f"%{turkce_normalize(ist_p_birim)}%"))
            if ist_p_kampus and ist_p_kampus != "Tümü":
                q = q.filter(Personel.kampus == ist_p_kampus)
            if ist_p_ofis:
                q = q.filter(func.NORMALIZE(Personel.ofis).like(f"%{turkce_normalize(ist_p_ofis)}%"))
                
            analiz_sonuclari = q.order_by(Personel.birimi.asc(), Personel.ad_soyad.asc()).all()
            analiz_toplam = len(analiz_sonuclari)
            
            # Personel Grafik Verisi (Birim Dağılımı)
            temp_birim = {}
            for p in analiz_sonuclari:
                b = p.birimi if p.birimi else "Belirtilmedi"
                temp_birim[b] = temp_birim.get(b, 0) + 1
            f_labels_1 = list(temp_birim.keys())
            f_values_1 = list(temp_birim.values())

        else: # Demirbaş Analizi
            q = db.session.query(
                Demirbas.ad, 
                Demirbas.kampus, 
                Demirbas.konum, 
                func.sum(Demirbas.adet).label('toplam_adet')
            )
            
            if ist_malzeme:
                q = q.filter(func.NORMALIZE(Demirbas.ad).like(f"%{turkce_normalize(ist_malzeme)}%"))
            if ist_kampus and ist_kampus != "Tümü":
                q = q.filter(Demirbas.kampus == ist_kampus)
            if ist_konum:
                q = q.filter(func.NORMALIZE(Demirbas.konum).like(f"%{turkce_normalize(ist_konum)}%"))
                
            analiz_sonuclari = q.group_by(Demirbas.ad, Demirbas.kampus, Demirbas.konum)\
                                .order_by(Demirbas.kampus.asc(), Demirbas.konum.asc()).all()
            
            analiz_toplam = sum(item.toplam_adet for item in analiz_sonuclari)
            
            # Demirbaş Grafik Verileri
            temp_kampus = {}
            temp_konum = {}
            for item in analiz_sonuclari:
                k = item.kampus
                adet = item.toplam_adet
                temp_kampus[k] = temp_kampus.get(k, 0) + adet
                
                k_ozet = item.konum.split('/')[0].strip()
                temp_konum[k_ozet] = temp_konum.get(k_ozet, 0) + adet
                
            f_labels_1 = list(temp_kampus.keys())
            f_values_1 = list(temp_kampus.values())
            f_labels_2 = list(temp_konum.keys())
            f_values_2 = list(temp_konum.values())

    # ==========================================
    # 8. RENDER TEMPLATE (SONUÇ)
    # ==========================================
    return render_template('index.html',
                           aktif_tab=aktif_tab,
                           arama_terimi=arama_terimi,
                           demirbaslar=demirbaslar,
                           personeller=personeller,
                           arizalar=arizalar,
                           bildirim_sayisi=bildirim_sayisi,
                           
                           sayfa_d=sayfa_d, toplam_sayfa_demirbas=toplam_sayfa_demirbas,
                           sayfa_p=sayfa_p, toplam_sayfa_personel=toplam_sayfa_personel,
                           sayfa_a=sayfa_a, toplam_sayfa_ariza=toplam_sayfa_ariza,

                           chart_kampus_labels=chart_kampus_labels, chart_kampus_values=chart_kampus_values,
                           chart_esya_labels=chart_esya_labels, chart_esya_values=chart_esya_values,
                           chart_personel_labels=chart_personel_labels, chart_personel_values=chart_personel_values,
                           chart_tur_labels=chart_tur_labels, chart_tur_values=chart_tur_values,
                           
                           yerleskeler=YERLESKELER, birimler=BIRIMLER, unvanlar=UNVANLAR,
                           son_yukleme=son_yukleme, tum_gecmis=tum_gecmis,
                           kullanicilar_listesi=kullanicilar_listesi, aktif_kullanici_ofis=aktif_kullanici_ofis,

                           analiz_sonuclari=analiz_sonuclari,
                           analiz_turu=analiz_turu,
                           analiz_toplam=analiz_toplam,
                           ist_malzeme=ist_malzeme, ist_kampus=ist_kampus, ist_konum=ist_konum,
                           ist_p_ad=ist_p_ad, ist_p_birim=ist_p_birim, ist_p_kampus=ist_p_kampus, ist_p_ofis=ist_p_ofis,
                           f_labels_1=f_labels_1, f_values_1=f_values_1,
                           f_labels_2=f_labels_2, f_values_2=f_values_2
                           )

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(bp.root_path, '../../static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@bp.route('/get-all-ids')
@login_required
def get_all_ids():
    tab = request.args.get('tab', 'demirbas')
    q = request.args.get('q', '').strip()
    
    yetki = int(session.get('yetki_duzeyi', 0))
    rol = session.get('rol')

    ids = []

    if tab == 'demirbas':
        query = Demirbas.query
        if yetki == 0 and rol != 'teknik':
            return jsonify([])
            
        if q:
            t = f"%{turkce_normalize(q)}%"
            query = query.filter(
                or_(
                    func.NORMALIZE(Demirbas.ad).like(t),
                    func.NORMALIZE(Demirbas.konum).like(t)
                )
            )
        ids = [str(item.id) for item in query.all()]

    elif tab == 'personel':
        query = Personel.query
        if yetki == 0 and rol != 'teknik':
            return jsonify([])

        if q:
            t = f"%{turkce_normalize(q)}%"
            query = query.filter(
                or_(
                    func.NORMALIZE(Personel.ad_soyad).like(t),
                    func.NORMALIZE(Personel.ofis).like(t)
                )
            )
        ids = [str(item.id) for item in query.all()]

    elif tab == 'ariza':
        query = Ariza.query
        if rol not in ['admin', 'teknik'] and yetki < 3:
            mevcut_kisi = session.get('ad_soyad', '')
            query = query.filter(Ariza.bildiren == mevcut_kisi)
        
        if q:
            t = f"%{turkce_normalize(q)}%"
            query = query.filter(
                or_(
                    func.NORMALIZE(Ariza.baslik).like(t),
                    func.NORMALIZE(Ariza.konum).like(t)
                )
            )
        ids = [str(item.id) for item in query.all()]

    return jsonify(ids)