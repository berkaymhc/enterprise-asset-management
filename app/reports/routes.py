# app/reports/routes.py - DÜZELTİLMİŞ VERSİYON

from flask import render_template, request, session, redirect, url_for, send_file, flash
from flask_login import login_required, current_user # <--- 1. DÜZELTME: Flask-Login eklendi
from app.reports import bp
from app import db
from app.models import Demirbas, Personel, Ariza, YuklemeGecmisi
# login_required BURADAN SİLİNDİ 👇
from app.utils import tr_upper, format_telefon, turkce_normalize 
from datetime import datetime
import io
import qrcode
import base64
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from sqlalchemy import func, or_

# --- 1. EXCEL ŞABLON İNDİRME ---
@bp.route('/indir-sablon/<tur>')
@login_required
def indir_sablon(tur):
    wb = Workbook()
    ws = wb.active
    ws.title = "Örnek Şablon"
    bold_font = Font(bold=True)
    
    if tur == 'personel':
        ws.append(['Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis', 'Telefon', 'E-Posta'])
        ws.append(['Ali Yılmaz', 'Memur', 'Bilgi İşlem', 'Yalıncak Yerleşkesi', 'Z-23', '5551234567', 'ali@ornek.com'])
        ws.column_dimensions['A'].width = 25
    else:
        # Demirbaş Şablonu
        ws.append(['Malzeme Adı', 'Cinsi', 'Marka', 'Model', 'Seri No', 'Kampüs', 'Konum', 'Adet', 'Zimmetli Kişi', 'Açıklama'])
        ws.append(['Çalışma Masası', 'Mobilya', '', '', '', 'Yalıncak Yerleşkesi', 'B-Blok 105', 1, '', ''])
        ws.column_dimensions['A'].width = 25

    for cell in ws[1]: cell.font = bold_font
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"Ornek_{tur.capitalize()}_Sablonu.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# --- 2. GENEL RAPOR (Tüm Veritabanını İndir) ---
@bp.route('/rapor')
@login_required
def rapor():
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('main.index'))

    wb = Workbook()
    
    # SAYFA 1: DEMİRBAŞLAR
    ws1 = wb.active
    ws1.title = "Demirbaş Listesi"
    ws1.append(['ID', 'Malzeme Adı', 'Cinsi', 'Kampüs', 'Konum', 'Adet', 'Alım Tarihi'])
    
    query_d = Demirbas.query.all()
    
    for d in query_d:
        # 2. DÜZELTME: d.tarih -> d.alim_tarihi yapıldı
        ws1.append([d.id, d.ad, d.cinsi, d.kampus, d.konum, d.adet, d.alim_tarihi])

    # SAYFA 2: PERSONELLER
    ws2 = wb.create_sheet("Personel Listesi")
    ws2.append(['ID', 'Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis', 'Telefon', 'E-Posta'])
    
    for p in Personel.query.all():
        ws2.append([p.id, p.ad_soyad, p.unvan, p.birimi, p.kampus, p.ofis, p.telefon, p.email])

    # SAYFA 3: ARIZALAR
    ws3 = wb.create_sheet("Arıza Kayıtları")
    ws3.append(['ID', 'Konum', 'Başlık', 'Durum', 'Bildiren', 'Tarih'])
    
    for a in Ariza.query.all():
        ws3.append([a.id, a.konum, a.baslik, a.durum, a.bildiren, a.tarih])

    # Stil Ayarları
    bold = Font(bold=True)
    for sheet in wb.worksheets:
        for cell in sheet[1]: cell.font = bold
        sheet.column_dimensions['A'].width = 10
        sheet.column_dimensions['B'].width = 25

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"Genel_Rapor_{datetime.now().strftime('%Y-%m-%d')}.xlsx")

# --- 3. TOPLU QR KOD YAZDIRMA ---
@bp.route('/toplu-yazdir-demirbas', methods=['GET', 'POST'])
@login_required
def toplu_yazdir_demirbas():
    if request.method == 'POST': 
        secilenler = request.form.getlist('secilen_ids')
    else: 
        secilenler = request.args.get('ids', '').split(',')
    
    if not secilenler or secilenler == ['']: 
        return redirect(url_for('main.index', tab='demirbas'))
    
    # ORM ile seçilenleri çek
    demirbaslar = Demirbas.query.filter(Demirbas.id.in_(secilenler)).all()
    qr_listesi = []
    
    for item in demirbaslar:
        # 3. DÜZELTME: item.tarih -> item.alim_tarihi
        tarih_bilgisi = item.alim_tarihi if item.alim_tarihi else "Belirtilmedi"
        qr_icerik = f"DEMİRBAŞ BİLGİSİ\nID: {item.id}\nÜrün: {item.ad}\nKonum: {item.konum}\nCinsi: {item.cinsi}\nKayıt: {tarih_bilgisi}"
        
        # QR Oluştur
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(qr_icerik)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        qr_listesi.append({
            'ad': item.ad, 'id': item.id, 'konum': item.konum,
            'cinsi': item.cinsi, 'qr': qr_base64
        })

    return render_template('toplu_yazdir.html', qr_listesi=qr_listesi)

# --- 4. KAPI KARTI VE TEKLİ QR ---
@bp.route('/kapi-karti/<path:konum_adi>')
def kapi_karti(konum_adi):
    # Kapı kartı için QR (Odanın linkini içerir)
    hedef_url = url_for('reports.ofis_detay', konum_adi=konum_adi, _external=True)
    
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(hedef_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return render_template('kapi_karti.html', konum=konum_adi, qr_code=qr_base64)

@bp.route('/ofis/<path:konum_adi>')
def ofis_detay(konum_adi):
    # Ofis detay sayfası (Kapı kartındaki QR okutulunca açılır)
    t = f"%{turkce_normalize(konum_adi)}%"
    
    esyalar = Demirbas.query.filter(func.NORMALIZE(Demirbas.konum).like(t)).all()
    personeller = Personel.query.filter(func.NORMALIZE(Personel.ofis).like(t)).all()
    
    return render_template('oda_detay.html', konum=konum_adi, esyalar=esyalar, personeller=personeller)

@bp.route('/rapor-analiz')
@login_required
def rapor_analiz():
    if int(session.get('yetki_duzeyi', 0)) < 1:
        return redirect(url_for('main.index'))

    # Parametreleri al
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    
    ist_malzeme = request.args.get('ist_malzeme', '').strip()
    ist_kampus = request.args.get('ist_kampus', '')
    ist_konum = request.args.get('ist_konum', '').strip()
    
    ist_p_ad = request.args.get('ist_p_ad', '').strip()
    ist_p_birim = request.args.get('ist_p_birim', '').strip()
    ist_p_kampus = request.args.get('ist_p_kampus', '')
    ist_p_ofis = request.args.get('ist_p_ofis', '').strip()

    wb = Workbook()
    ws = wb.active
    
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="198754", fill_type="solid")
    genel_toplam = 0

    if analiz_turu == 'personel':
        ws.title = "Personel Analiz"
        ws.append(['Sıra No', 'Ad Soyad', 'Ünvan', 'Birim', 'Kampüs', 'Ofis', 'Telefon', 'E-Posta'])
        
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
            
        sonuclar = q.order_by(Personel.birimi.asc(), Personel.ad_soyad.asc()).all()
        
        for i, p in enumerate(sonuclar, 1):
            tel_formati = format_telefon(p.telefon)
            ws.append([i, p.ad_soyad, p.unvan, p.birimi, p.kampus, p.ofis, tel_formati, p.email])
            genel_toplam += 1
            
        ws.append(['', '', '', '', '', '', 'GENEL TOPLAM:', genel_toplam])

    else:
        ws.title = "Demirbaş Analiz"
        ws.append(['Sıra No', 'Malzeme Adı', 'Kampüs', 'Konum / Ofis', 'Adet'])
        
        q = db.session.query(Demirbas.ad, Demirbas.kampus, Demirbas.konum, func.sum(Demirbas.adet).label('toplam_adet'))
        
        if ist_malzeme:
            q = q.filter(func.NORMALIZE(Demirbas.ad).like(f"%{turkce_normalize(ist_malzeme)}%"))
        if ist_kampus and ist_kampus != "Tümü":
            q = q.filter(Demirbas.kampus == ist_kampus)
        if ist_konum:
            q = q.filter(func.NORMALIZE(Demirbas.konum).like(f"%{turkce_normalize(ist_konum)}%"))
            
        sonuclar = q.group_by(Demirbas.ad, Demirbas.kampus, Demirbas.konum)\
                    .order_by(Demirbas.kampus.asc(), Demirbas.konum.asc()).all()
                    
        for i, item in enumerate(sonuclar, 1):
            ws.append([i, item.ad, item.kampus, item.konum, item.toplam_adet])
            genel_toplam += item.toplam_adet
            
        ws.append(['', '', '', 'GENEL TOPLAM:', genel_toplam])

    # Stil Ayarları
    for cell in ws[1]: 
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 30

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    dosya_adi = f"Analiz_Raporu_{analiz_turu}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(output, download_name=dosya_adi, as_attachment=True)

@bp.route('/rapor-grafik-ozet')
@login_required
def rapor_grafik_ozet():
    # Parametreleri al
    analiz_turu = request.args.get('analiz_turu', 'demirbas')
    
    ist_malzeme = request.args.get('ist_malzeme', '').strip()
    ist_kampus = request.args.get('ist_kampus', '')
    ist_p_birim = request.args.get('ist_p_birim', '').strip()

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Kampüs Dağılımı"
    
    ws1.append(['Kampüs Adı', 'Sayı'])
    
    temp_kampus = {}
    
    if analiz_turu == 'personel':
        q = Personel.query
        if ist_p_birim:
            q = q.filter(func.NORMALIZE(Personel.birimi).like(f"%{turkce_normalize(ist_p_birim)}%"))
        
        for p in q.all():
            k = p.kampus if p.kampus else "Belirtilmedi"
            temp_kampus[k] = temp_kampus.get(k, 0) + 1
    else:
        q = Demirbas.query
        if ist_malzeme:
            q = q.filter(func.NORMALIZE(Demirbas.ad).like(f"%{turkce_normalize(ist_malzeme)}%"))
        if ist_kampus and ist_kampus != "Tümü":
            q = q.filter(Demirbas.kampus == ist_kampus)
            
        for d in q.all():
            temp_kampus[d.kampus] = temp_kampus.get(d.kampus, 0) + d.adet

    for k, v in temp_kampus.items():
        ws1.append([k, v])
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(output, download_name="Grafik_Ozet_Verisi.xlsx", as_attachment=True)