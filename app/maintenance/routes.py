from flask import redirect, url_for, request, session, flash, jsonify
from app.maintenance import bp
from app import db
from app.models import MaintenanceLog, Asset, UploadHistory
from flask_login import login_required, current_user
from app.utils import normalize_text, save_log
from datetime import datetime


# --- MAINTENANCE OPERATIONS ---

@bp.route('/add-maintenance', methods=['POST'])
@login_required
def add_maintenance():
    try:
        location = request.form.get('location')
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority')
        d_id = request.form.get('asset_id') 
        
        if not d_id or not d_id.isdigit():
            flash("Invalid Asset ID! Please select from the list or enter a correct ID.", "danger")
            return redirect(url_for('main.index', tab='maintenance'))

        new_maintenance = MaintenanceLog(
            location=location,
            title=title,
            description=description,
            status="Pending",
            priority=priority,
            asset_id=int(d_id),
            user_id=current_user.id,
            date_reported=datetime.now()
        )

        db.session.add(new_maintenance)
        db.session.commit()
        
        save_log(f"New Maintenance: {title}", f"Location: {location}", "Maintenance")
        flash("Maintenance request successfully created.", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: {e}")
        flash(f"Error occurred during registration: {str(e)}", "danger")

    return redirect(url_for('main.index', tab='maintenance'))

@bp.route('/update-maintenance-status', methods=['POST'])
@login_required
def update_maintenance_status():
    if not current_user.role in ['technician', 'admin']:
        return "Unauthorized action", 403

    try:
        maintenance_id = request.form.get('id')
        new_status = request.form.get('status')
        description_note = request.form.get('description')
        
        maintenance = MaintenanceLog.query.get(maintenance_id)
        if maintenance:
            old_status = maintenance.status
            if old_status == new_status:
                return jsonify({'status': 'success', 'msg': 'No changes'}), 200

            maintenance.status = new_status
            
            if description_note:
                time_str = datetime.now().strftime("%d-%m %H:%M")
                user_name = current_user.full_name if current_user.is_authenticated else "System"
                new_note = f"\n[{time_str} - {user_name} - {new_status}]: {description_note}"
                maintenance.description = (maintenance.description or "") + new_note

            db.session.commit()
            
            log_msg = f"Status: {old_status} -> {new_status}"
            if description_note: log_msg += f" ({description_note})"
                
            save_log(log_msg, f"Maintenance ID: {maintenance_id}", "Maintenance")
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'msg': 'Maintenance not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@bp.route('/delete-maintenance/<int:id>')
@login_required
def delete_maintenance(id):
    if current_user.role != 'admin':
        flash("You do not have permission for this action. Only an admin can delete.", "danger")
        return redirect(url_for('main.index', tab='maintenance'))
        
    maintenance = MaintenanceLog.query.get(id)
    if maintenance:
        title_backup = maintenance.title
        db.session.delete(maintenance)
        db.session.commit()
        save_log(f"Maintenance Deleted: {title_backup}", f"ID: {id}", "Maintenance")
        flash("Maintenance deleted.", "warning")
        
    return redirect(url_for('main.index', tab='maintenance'))

@bp.route('/bulk-delete-maintenance', methods=['POST'])
@login_required
def bulk_delete_maintenance():
    if current_user.role != 'technician' and current_user.role != 'admin':
        return redirect(url_for('main.index', tab='maintenance'))
        
    ids = request.form.getlist('selected_ids')
    if ids:
        count = len(ids)
        MaintenanceLog.query.filter(MaintenanceLog.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        
        save_log(f"Bulk Maintenance Deletion ({count} Records)", f"Deleted IDs: {', '.join(ids)}", "Maintenance")
        
        flash(f"{count} maintenance records successfully deleted.", "success")
        
    return redirect(url_for('main.index', tab='maintenance'))