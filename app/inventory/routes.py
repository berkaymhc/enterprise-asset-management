from flask import redirect, url_for, request, session, flash, jsonify, render_template
from app.inventory import bp
from app import db
from app.models import Demirbas, YuklemeGecmisi
from datetime import datetime  # <--- BU SATIRI EKLE
from flask_login import login_required, current_user
from app.utils import turkce_normalize, tr_upper, tr_title # Kendi utils fonksiyonun burada kalsınfrom datetime import datetime
from app.models import Ariza, Demirbas # Demirbas zaten vardır, Ariza'yı yanına ekle
import openpyxl
import os

# --- YARDIMCI LOG FONKSİYONU ---
def log_kaydet(dosya_adi, hedef_konum, tur):
    try:
        yeni_log = YuklemeGecmisi(
            dosya_adi=dosya_adi,
            hedef_konum=hedef_konum,
            tur=tur,
            tarih=datetime.now().strftime("%d-%m-%Y %H:%M"),
            islem_yapan=session.get('ad_soyad', 'Sistem')
        )
        db.session.add(yeni_log)
        db.session.commit()
    except:
        pass # Log hatası sistemi durdurmasın

# --- CRUD İŞLEMLERİ ---

@bp.route('/ekle-demirbas', methods=['POST'])
@login_required
def ekle_demirbas():
    # Yetki Kontrolü: Teknik servis ekleme yapamaz
    if session.get('rol') == 'teknik':
        return redirect(url_for('main.index', tab='ariza'))
    
    # Form verilerini al
    ad = request.form.get('ad')
    cinsi = request.form.get('cinsi')
    kampus = request.form.get('kampus')
    konum = request.form.get('konum')
    adet = request.form.get('adet')
    
    # Yeni Kayıt (ORM)
    yeni_demirbas = Demirbas(
        ad=ad,
        cinsi=cinsi,
        kampus=kampus,
        konum=konum,
        adet=adet,
        alim_tarihi=datetime.now().strftime("%Y-%m-%d") # DOĞRU SÜTUN İSMİ
    )
    
    db.session.add(yeni_demirbas)
    db.session.commit()
    
    log_kaydet(f"{ad} Eklendi", f"Konum: {konum}", "Ekleme")
    flash(f"{ad} başarıyla eklendi.", "success")
    return redirect(url_for('main.index', tab='demirbas'))

@bp.route('/guncelle-demirbas', methods=['POST'])
@login_required
def guncelle_demirbas():
    d_id = request.form.get('id')
    
    # Güncellenecek kaydı bul
    demirbas = Demirbas.query.get(d_id)
    
    if demirbas:
        demirbas.ad = request.form.get('ad')
        demirbas.cinsi = request.form.get('cinsi')
        demirbas.kampus = request.form.get('kampus')
        demirbas.konum = request.form.get('konum')
        demirbas.adet = request.form.get('adet')
        
        db.session.commit()
        log_kaydet(f"{demirbas.ad} Güncellendi", f"Yeni Konum: {demirbas.konum}", "Düzenleme")
        flash("Kayıt güncellendi.", "success")
        
    return redirect(url_for('main.index', tab='demirbas'))

@bp.route('/tasi-demirbas', methods=['POST'])
@login_required
def tasi_demirbas():
    # Yetki: Seviye 0 taşıma yapamaz
    if int(session.get('yetki_duzeyi', 0)) < 1:
        flash("Yetkisiz işlem.", "danger")
        return redirect(url_for('main.index', tab='demirbas'))

    d_id = request.form.get('id')
    yeni_kampus = request.form.get('kampus')
    yeni_konum = request.form.get('konum')
    
    demirbas = Demirbas.query.get(d_id)
    
    if demirbas:
        eski_konum = f"{demirbas.kampus}/{demirbas.konum}"
        demirbas.kampus = yeni_kampus
        demirbas.konum = yeni_konum
        
        db.session.commit()
        log_kaydet(f"{demirbas.ad} Taşındı", f"{eski_konum} -> {yeni_kampus}/{yeni_konum}", "Taşıma")
        flash("Demirbaş başarıyla taşındı.", "success")
        
    return redirect(url_for('main.index', tab='demirbas'))

@bp.route('/sil-demirbas/<int:id>')
@login_required
def sil_demirbas(id):
    # Yetki: Sadece Admin (Seviye 3)
    if int(session.get('yetki_duzeyi', 0)) < 3:
        flash("Silme yetkiniz yok.", "danger")
        return redirect(url_for('main.index', tab='demirbas'))
        
    demirbas = Demirbas.query.get(id)
    if demirbas:
        log_kaydet(f"{demirbas.ad} Silindi", f"Eski Konum: {demirbas.konum}", "Silme")
        db.session.delete(demirbas)
        db.session.commit()
        flash("Demirbaş silindi.", "warning")
        
    return redirect(url_for('main.index', tab='demirbas'))

@bp.route('/sifirla-demirbas')
@login_required
def sifirla_demirbas():
    # Sadece Admin
    if int(session.get('yetki_duzeyi', 0)) < 3:
        return redirect(url_for('main.index'))
        
    try:
        # Tüm tabloyu sil (ORM Yöntemi)
        db.session.query(Demirbas).delete()
        db.session.commit()
        
        # SQLite Sequence sıfırlama (ID'yi 1'e çekmek için)
        if db.engine.name == 'sqlite':
            from sqlalchemy import text
            try:
                # sqlite_sequence tablosunun varlığını kontrol etmeye gerek yok
                # Eğer AUTOINCREMENT kullanılmıyorsa bu işlem hata verebilir, yutuyoruz.
                db.session.execute(text("DELETE FROM sqlite_sequence WHERE name='demirbas'"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        
        log_kaydet("Tüm Liste Silindi", "Veritabanı Sıfırlama", "Sıfırlama")
        flash("Tüm demirbaş listesi temizlendi.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Hata: {str(e)}", "danger")
        
    return redirect(url_for('main.index', tab='demirbas'))

# --- TOPLU İŞLEMLER ---

@bp.route('/toplu-tasi-demirbas', methods=['POST'])
@login_required
def toplu_tasi_demirbas():
    if session.get('yetki_duzeyi', 0) < 1 and session.get('rol') != 'teknik':
        return jsonify({'status': 'error', 'msg': 'Yetkisiz işlem!'})

    secilen_ids = request.form.getlist('secilen_ids')
    yeni_kampus = request.form.get('yeni_kampus')
    yeni_konum = request.form.get('yeni_konum')

    if not secilen_ids:
        flash("Seçim yapılmadı.", "warning")
        return redirect(url_for('main.index', tab='demirbas'))

    # SQLAlchemy ile toplu güncelleme
    # Demirbas.id IN (1, 2, 3) olanları filtrele
    query = Demirbas.query.filter(Demirbas.id.in_(secilen_ids))
    
    count = 0
    for item in query.all():
        if yeni_kampus: item.kampus = yeni_kampus
        if yeni_konum: item.konum = yeni_konum
        count += 1
        
    db.session.commit()
    flash(f"{count} adet demirbaş taşındı.", "success")
    return redirect(url_for('main.index', tab='demirbas'))

@bp.route('/toplu-sil-demirbas', methods=['POST'])
@login_required
def toplu_sil_demirbas():
    if int(session.get('yetki_duzeyi', 0)) < 3:
        return redirect(url_for('main.index', tab='demirbas'))

    secilen_ids = request.form.getlist('secilen_ids')
    if not secilen_ids: return redirect(url_for('main.index', tab='demirbas'))
    
    # Toplu Silme (ORM)
    silinen_sayisi = Demirbas.query.filter(Demirbas.id.in_(secilen_ids)).delete(synchronize_session=False)
    db.session.commit()
    
    log_kaydet(f"{silinen_sayisi} Kayıt Silindi", "Toplu İşlem", "Silme")
    flash(f"{silinen_sayisi} kayıt silindi.", "success")
    
    return redirect(url_for('main.index', tab='demirbas'))

@bp.route('/yukle-demirbas', methods=['POST'])
@login_required
def yukle_demirbas():
    if 'dosya' not in request.files: 
        return redirect(url_for('main.index'))
        
    dosyalar = request.files.getlist('dosya')
    hedef_kampus = request.form.get('hedef_kampus', 'Merkez')
    bina_kat = request.form.get('bina_kat', '')
    
    toplam_eklenen = 0
    islem_yapildi = False

    for dosya in dosyalar:
        if dosya.filename == '': continue
        try:
            # Dosya adından konum türetme (Örn: Zemin_Kat.xlsx -> Zemin Kat)
            dosya_adi_temiz = dosya.filename.rsplit('.', 1)[0].replace('_', ' ').title()
            
            wb = openpyxl.load_workbook(dosya)
            for ws in wb.worksheets:
                # Konum birleştirme: Bina/Kat + Dosya Adı + Sayfa Adı
                # List comprehension ile boş olanları filtreliyoruz
                tam_konum = " / ".join([p for p in [bina_kat, dosya_adi_temiz, ws.title] if p])
                
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or row[0] is None: continue
                    
                    ad = row[0]
                    cinsi = row[1] if len(row) > 1 else ""
                    
                    try: 
                        adet = int(row[2]) if len(row) > 2 and row[2] else 1
                    except: 
                        adet = 1
                    
                    # Mükerrer Kontrol (ORM)
                    mevcut = Demirbas.query.filter_by(ad=ad, konum=tam_konum).first()
                    
                    if not mevcut:
                        yeni = Demirbas(
                            ad=ad,
                            cinsi=cinsi,
                            kampus=hedef_kampus,
                            konum=tam_konum,
                            adet=adet,
alim_tarihi=datetime.now().strftime("%Y-%m-%d")                        )
                        db.session.add(yeni)
                        toplam_eklenen += 1
                        islem_yapildi = True

        except Exception as e:
            flash(f"Hata ({dosya.filename}): {str(e)}", "danger")
            continue

    if islem_yapildi:
        db.session.commit()
        log_kaydet(f"{len(dosyalar)} Dosya Yüklendi", f"{bina_kat} - {toplam_eklenen} Eşya", "Yükleme")
        flash(f"{toplam_eklenen} adet demirbaş sisteme eklendi.", "success")
    else:
        flash("Yeni demirbaş eklenmedi veya hepsi zaten kayıtlı.", "warning")

    return redirect(url_for('main.index', tab='demirbas'))


@bp.route('/yukle-klasor', methods=['POST'])
@login_required
def yukle_klasor():
    # --- DEBUG İÇİN EKLE ---
    print(">>> Klasör Yükleme Rotasına Girildi!")
    if 'dosya' not in request.files: return redirect(url_for('main.index'))
    dosyalar = request.files.getlist('dosya')
    
    varsayilan_kampus = request.form.get('hedef_kampus', 'Merkez (Kanuni) Kampüsü')
    
    islem_sayisi = 0
    kaydedilen_yerler = set()

    # --- 1. KAMPÜS TESPİT SÖZLÜĞÜ ---
    KAMPUS_MAP = {
        "pelitli": "Pelitli Yerleşkesi",
        "çimenli": "Çimenli Yerleşkesi",
        "cimenli": "Çimenli Yerleşkesi",
        "kaşüstü": "Kaşüstü (Yomra) Yerleşkesi",
        "kasustu": "Kaşüstü (Yomra) Yerleşkesi",
        "yomra": "Kaşüstü (Yomra) Yerleşkesi",
        "yalıncak": "Yalıncak Yerleşkesi",
        "yalincak": "Yalıncak Yerleşkesi",
        "ömer yıldız": "Yalıncak Yerleşkesi",
        "omer yildiz": "Yalıncak Yerleşkesi"
    }

    # --- 2. KONUMDAN SİLİNECEK KELİMELER ---
    SILINECEK_KELIMELER = [
        "LİSTESİ", "LISTESI", "LİSTE", "LISTE", "DEMİRBAŞLARI", "DEMİRBAŞ", "DEMIRBAS", 
        "ENVANTER", "SAYIM", "SİSTEMİ", "SISTEMI", "YAPILDI", "YAPILAN", "YENİ", "ESKİ", 
        "COPY", "KOPYA", "YEDEK", "REVİZE", "REVIZE", "DÜZENLEME", "DÜZENLENEN", 
        "KONTROL", "TASLAK", "SON", "FİNAL", "FINAL", "MASAÜSTÜ", "DOWNLOADS", 
        "BELGELERİM", "TABLO", "TÜMÜ", "TUMU", "XLSX", "XLS",
        "YALINCAK", "PELİTLİ", "PELITLI", "ÇİMENLİ", "CIMENLI", "KAŞÜSTÜ", "KASUSTU", "YOMRA",
        "KANUNİ", "MERKEZ", "KAMPÜSÜ", "KAMPUSU", "YERLEŞKESİ", "YERLESKESI",
        "ÖMER YILDIZ", "OMER YILDIZ", "ÖMER", "YILDIZ"
    ]

    ONEMLI_KELIMELER = [
        "BLOK", "KAT", "ODA", "BİNA", "BINA", "YURT", "OFİS", "OFFICE", 
        "HALL", "SALON", "LAB", "DEPO", "ZEMİN", "GİRİŞ", "SİSTEM", "KAZAN",
        "RESTORAN", "YEMEKHANE", "KANTİN", "LOBİ", "MESCİT", "GUVENLIK", "GÜVENLİK",
        "AMBAR", "ATÖLYE", "ARŞİV", "LİSE", "FAKÜLTE", "MYO", "MEMUR", "PERSONEL",
        "PATOLOJİ", "KLİNİK", "POLİKLİNİK", "SERVİS", "BÖLÜM", "BOLUM", "BİRİM", "LABORATUVAR"
    ]

    for dosya in dosyalar:
        if not (dosya.filename.endswith('.xlsx') or dosya.filename.endswith('.xls')):
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
                temiz_parca = tr_upper(parca) # utils'den gelen fonksiyon
                
                # SİLME İŞLEMİ
                for yasakli in SILINECEK_KELIMELER:
                    if yasakli in temiz_parca:
                        temiz_parca = temiz_parca.replace(yasakli, "")
                
                temiz_parca = temiz_parca.replace("_", " ").replace("-", " ").strip()
                
                if len(temiz_parca) < 2 and not any(c.isdigit() for c in temiz_parca):
                    continue

                is_onemli = any(k in temiz_parca for k in ONEMLI_KELIMELER)
                is_blok_kodu = (len(temiz_parca) > 0 and len(temiz_parca) < 6 and any(c.isdigit() for c in temiz_parca))
                
                if (is_onemli or is_blok_kodu or len(temiz_parca) > 2):
                    temiz_parca_title = tr_title(temiz_parca) # utils'den gelen fonksiyon
                    # Mükerrer klasör ismi önleme
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
                
                # Konum Belirleme Mantığı
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
                    ad = row[0]
                    cinsi = row[1] if len(row)>1 else ""
                    try: adet = int(row[2]) if len(row)>2 else 1
                    except: adet = 1
                    
                    # Mükerrer Kontrol (ORM)
                    mevcut = Demirbas.query.filter_by(ad=ad, konum=tam_konum).first()
                    
                    if not mevcut:
                        yeni = Demirbas(
                            ad=ad, 
                            cinsi=cinsi, 
                            kampus=aktif_kampus, 
                            konum=tam_konum, 
                            adet=adet, 
                            alim_tarihi=datetime.now().strftime("%Y-%m-%d")
                        )
                        db.session.add(yeni)
            
            islem_sayisi += 1

        except Exception as e:
            print(f"Hata ({dosya.filename}): {e}")

    # Döngü bitince toplu kaydet
    db.session.commit() 
    
    if islem_sayisi > 0:
        ornek_konum = list(kaydedilen_yerler)[0] if len(kaydedilen_yerler) > 0 else ""
        log_kaydet(f"Akıllı Yükleme ({islem_sayisi} dosya)", f"Örn: {ornek_konum}", "Yükleme")
        flash(f"{islem_sayisi} adet dosya başarıyla işlendi.", "success")
    else:
        flash("İşlenecek dosya bulunamadı.", "warning")

    return redirect(url_for('main.index', tab='demirbas'))

@bp.route('/demirbas-detay/<int:id>')
def demirbas_detay(id):
    # 1. Demirbaşı Bul
    demirbas = Demirbas.query.get_or_404(id)
    
    # 2. Aktif Arıza Var mı? (SQLAlchemy Sorgusu)
    # Durumu 'Tamamlandı' veya 'İptal Edildi' OLMAYAN bir kayıt arıyoruz
    aktif_ariza = Ariza.query.filter(
        Ariza.demirbas_id == id,
        ~Ariza.durum.in_(['Tamamlandı', 'İptal Edildi']) # ~ işareti 'NOT IN' demektir
    ).order_by(Ariza.id.desc()).first()
    
    return render_template('detay.html', item=demirbas, ariza=aktif_ariza)