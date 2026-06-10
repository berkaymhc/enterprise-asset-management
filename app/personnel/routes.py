# app/personnel/routes.py

import openpyxl
from flask import redirect, url_for, request, session, flash, render_template, current_app
from app.personnel import bp
from app import db
from app.models import Personnel, UploadHistory, Asset
from flask_login import login_required
from app.utils import format_phone, normalize_text, save_log
from datetime import datetime
from sqlalchemy import func


# --- EXCEL UPLOAD ---
@bp.route('/upload-personnel', methods=['POST'])
@login_required
def upload_personnel():
    if 'file' not in request.files: return redirect(url_for('main.index'))
    file = request.files['file']
    
    if file and file.filename != '':
        try:
            wb = openpyxl.load_workbook(file)
            ws = wb.active
            added_count = 0
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or row[0] is None: continue
                
                # Excel Columns: 0:Name, 1:Title, 2:Department, 3:Campus, 4:Office, 5:Phone, 6:Email
                full_name = row[0]
                title = row[1] if len(row) > 1 else ""
                department = row[2] if len(row) > 2 else ""
                campus = row[3] if len(row) > 3 and row[3] else "Main Campus"
                office = row[4] if len(row) > 4 else ""
                
                # Phone and Email
                raw_phone = str(row[5]) if len(row) > 5 and row[5] else ""
                phone = format_phone(raw_phone)
                
                email = row[6] if len(row) > 6 and row[6] else ""
                
                # Duplicate Check
                existing = Personnel.query.filter_by(full_name=full_name, office=office).first()
                
                if not existing:
                    new_p = Personnel(
                        full_name=full_name, title=title, department=department,
                        campus=campus, office=office, phone=phone, email=email
                    )
                    db.session.add(new_p)
                    added_count += 1
            
            if added_count > 0:
                db.session.commit()
                save_log("Personnel List Uploaded", f"{added_count} People Added", "Upload")
                flash(f"{added_count} personnel successfully uploaded.", "success")
            else:
                flash("No new personnel found.", "warning")
                
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            
    return redirect(url_for('main.index', tab='personnel'))

# --- CRUD OPERATIONS ---

@bp.route('/add-personnel', methods=['POST'])
@login_required
def add_personnel():
    full_name = request.form.get('full_name')
    title = request.form.get('title')
    department = request.form.get('department')
    campus = request.form.get('campus')
    office = request.form.get('office')
    phone = request.form.get('phone')
    
    # Email generation
    email_prefix = request.form.get('email_prefix')
    domain = current_app.config.get('MAIL_DOMAIN', 'avrasya.edu.tr')
    email = f"{email_prefix}@{domain}" if email_prefix else ""

    new_p = Personnel(
        full_name=full_name,
        title=title,
        department=department,
        campus=campus,
        office=office,
        email=email,
        phone=phone
    )
    
    db.session.add(new_p)
    db.session.commit()
    
    flash("Personnel added.", "success")
    return redirect(url_for('main.index', tab='personnel'))

@bp.route('/update-personnel', methods=['POST'])
@login_required
def update_personnel():
    p_id = request.form.get('id')
    personnel = Personnel.query.get(p_id)
    
    if personnel:
        personnel.full_name = request.form.get('full_name')
        personnel.title = request.form.get('title')
        personnel.department = request.form.get('department')
        personnel.campus = request.form.get('campus')
        personnel.office = request.form.get('office')
        personnel.email = request.form.get('email')
        personnel.phone = format_phone(request.form.get('phone'))
        
        db.session.commit()
        save_log(f"{personnel.full_name} Updated", f"Office: {personnel.office}", "Edit")
        flash("Personnel updated.", "success")
        
    return redirect(url_for('main.index', tab='personnel'))

@bp.route('/delete-personnel/<int:id>')
@login_required
def delete_personnel(id):
    if int(session.get('auth_level', 0)) < 3: return redirect(url_for('main.index', tab='personnel'))
    
    personnel = Personnel.query.get(id)
    if personnel:
        save_log(f"{personnel.full_name} Deleted", f"Office: {personnel.office}", "Delete")
        db.session.delete(personnel)
        db.session.commit()
        flash("Personnel deleted.", "warning")
        
    return redirect(url_for('main.index', tab='personnel'))

@bp.route('/reset-personnel')
@login_required
def reset_personnel():
    if int(session.get('auth_level', 0)) < 3: return redirect(url_for('main.index'))
    
    try:
        db.session.query(Personnel).delete()
        db.session.commit()
        save_log("All Personnel List Deleted", "Database Reset", "Reset")
        flash("Personnel list reset.", "danger")
    except:
        db.session.rollback()
        
    return redirect(url_for('main.index', tab='personnel'))

# --- BULK OPERATIONS ---

@bp.route('/bulk-delete-personnel', methods=['POST'])
@login_required
def bulk_delete_personnel():
    if session.get('role') != 'admin': return redirect(url_for('main.index', tab='personnel'))
    
    ids = request.form.getlist('selected_ids')
    if ids:
        Personnel.query.filter(Personnel.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        flash(f"{len(ids)} personnel deleted.", "success")
        
    return redirect(url_for('main.index', tab='personnel'))

@bp.route('/bulk-move-personnel', methods=['POST'])
@login_required
def bulk_move_personnel():
    if int(session.get('auth_level', 0)) < 1: return redirect(url_for('main.index', tab='personnel'))
    
    ids = request.form.getlist('selected_ids')
    new_department = request.form.get('new_department')
    new_campus = request.form.get('new_campus')
    new_office = request.form.get('new_office')
    
    if ids:
        query = Personnel.query.filter(Personnel.id.in_(ids))
        for p in query.all():
            p.office = new_office
            if new_department: p.department = new_department
            if new_campus: p.campus = new_campus
            
        db.session.commit()
        flash(f"{len(ids)} personnel moved.", "success")
        
    return redirect(url_for('main.index', tab='personnel'))

# --- PERSONNEL DETAILS AND ASSIGNMENTS ---
@bp.route('/personnel-details/<int:id>')
@login_required
def personnel_details(id):
    person = Personnel.query.get_or_404(id)
    
    # Friends in the same office
    friends = Personnel.query.filter(Personnel.office == person.office, Personnel.id != id).all()
    
    # Assigned Assets
    assets = []
    if person.office:
        searched_office = normalize_text(person.office)
        
        assets = Asset.query.filter(
            func.NORMALIZE(Asset.location).like(f"%{searched_office}%")
        ).all()
    
    return render_template('personnel_det.html', person=person, friends=friends, assets=assets)

@bp.route('/move-personnel', methods=['POST'])
@login_required
def move_personnel():
    p_id = request.form.get('personnel_id')
    new_campus = request.form.get('new_campus')
    new_office = request.form.get('new_office')
    
    personnel = Personnel.query.get(p_id)
    
    if personnel:
        old_location = f"{personnel.campus}/{personnel.office}"
        
        personnel.campus = new_campus
        personnel.office = new_office
        
        db.session.commit()
        
        save_log(f"{personnel.full_name} Moved", f"{old_location} -> {new_campus}/{new_office}", "Move")
        flash("Personnel successfully moved.", "success")
        
    return redirect(url_for('main.index', tab='personnel'))