import os
from datetime import datetime
from flask import render_template, request, session, redirect, url_for, jsonify, send_from_directory, flash, send_file
from sqlalchemy import func, or_
from flask_login import login_required, current_user
from app.main import bp
from app.models import Asset, Personnel, MaintenanceLog, UploadHistory, User
from app.utils import normalize_text
from app import db

# Constants
CAMPUSES = ["Main Campus", "North Campus", "South Campus", "East Campus", "West Campus"]
DEPARTMENTS = ["IT Department", "Administrative & Financial Affairs", "Human Resources", "Student Affairs", "Rectorate", "Library", "Health & Sports"]
TITLES = ["Head of Department", "Branch Manager", "Officer", "Technician", "Engineer", "Worker"]

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    active_tab = request.args.get('tab', 'assets')
    search_term = request.args.get('q', '').strip()
    
    auth_level = int(session.get('auth_level', 0))
    user_role = session.get('role')

    if not request.args.get('tab'):
        if auth_level == 0 or user_role == 'technician':
            active_tab = 'maintenance'
    
    limit = 20
    page_a = request.args.get('page_a', 1, type=int)
    page_p = request.args.get('page_p', 1, type=int)
    
    # 2. STATS AND CHART DATA (ORM)
    chart_campus_labels, chart_campus_values = [], []
    chart_asset_labels, chart_asset_values = [], []
    chart_personnel_labels, chart_personnel_values = [], []
    chart_type_labels, chart_type_values = [], []
    
    if auth_level >= 1:
        res_campus = db.session.query(Asset.campus, func.sum(Asset.quantity)).group_by(Asset.campus).all()
        chart_campus_labels = [r[0] for r in res_campus if r[0]]
        chart_campus_values = [r[1] for r in res_campus if r[0]]
        
        res_asset = db.session.query(Asset.name, func.sum(Asset.quantity)).group_by(Asset.name).order_by(func.sum(Asset.quantity).desc()).limit(5).all()
        chart_asset_labels = [r[0] for r in res_asset]
        chart_asset_values = [r[1] for r in res_asset]

        res_per = db.session.query(Personnel.department, func.count(Personnel.id)).group_by(Personnel.department).limit(8).all()
        chart_personnel_labels = [r[0] for r in res_per if r[0]]
        chart_personnel_values = [r[1] for r in res_per if r[0]]
        
        res_type = db.session.query(Asset.type, func.sum(Asset.quantity)).filter(Asset.type != "").group_by(Asset.type).all()
        chart_type_labels = [r[0] for r in res_type]
        chart_type_values = [r[1] for r in res_type]

    # 3. ASSET QUERY
    query_a = Asset.query
    
    if search_term and active_tab == 'assets':
        t = f"%{normalize_text(search_term)}%"
        query_a = query_a.filter(
            or_(
                func.NORMALIZE(Asset.name).like(t),
                func.NORMALIZE(Asset.location).like(t),
                func.NORMALIZE(Asset.campus).like(t),
                func.NORMALIZE(Asset.type).like(t),
                func.NORMALIZE(Asset.brand).like(t),
                func.NORMALIZE(Asset.model).like(t),
                func.NORMALIZE(Asset.serial_number).like(t),
                func.NORMALIZE(Asset.asset_tag).like(t)
            )
        )
    
    pagination_a = query_a.order_by(Asset.id.desc()).paginate(page=page_a, per_page=limit, error_out=False)
    
    assets = pagination_a.items
    total_a = pagination_a.total
    total_pages_asset = pagination_a.pages

    # 4. PERSONNEL QUERY
    query_p = Personnel.query
    
    if search_term and active_tab == 'personnel':
        t = f"%{normalize_text(search_term)}%"
        query_p = query_p.filter(
            or_(
                func.NORMALIZE(Personnel.full_name).like(t),
                func.NORMALIZE(Personnel.title).like(t),
                func.NORMALIZE(Personnel.department).like(t),
                func.NORMALIZE(Personnel.office).like(t),
                func.NORMALIZE(Personnel.campus).like(t),
                func.NORMALIZE(Personnel.email).like(t),
                func.NORMALIZE(Personnel.phone).like(t)
            )
        )
        
    pagination_p = query_p.order_by(Personnel.office.asc()).paginate(page=page_p, per_page=limit, error_out=False)
    
    personnel = pagination_p.items
    total_p = pagination_p.total
    total_pages_personnel = pagination_p.pages

    # 5. MAINTENANCE QUERY
    active_statuses = ['Pending', 'In Progress', 'Waiting for Parts']
    past_statuses = ['Completed', 'Cancelled']

    q_active = MaintenanceLog.query.filter(MaintenanceLog.status.in_(active_statuses))
    q_past = MaintenanceLog.query.filter(MaintenanceLog.status.in_(past_statuses))
    
    if user_role not in ['admin', 'technician'] and auth_level < 3:
        q_active = q_active.filter(MaintenanceLog.user_id == current_user.id)
        q_past = q_past.filter(MaintenanceLog.user_id == current_user.id)
        
    if search_term and active_tab == 'maintenance':
        t = f"%{normalize_text(search_term)}%"
        f_filter = or_(
            func.NORMALIZE(MaintenanceLog.title).like(t),
            func.NORMALIZE(MaintenanceLog.location).like(t)
        )
        q_active = q_active.filter(f_filter)
        q_past = q_past.filter(f_filter)

    if user_role in ['admin', 'technician']:
        notification_count = MaintenanceLog.query.filter(MaintenanceLog.status.in_(active_statuses)).count()
    else:
        notification_count = MaintenanceLog.query.filter(MaintenanceLog.status.in_(active_statuses), MaintenanceLog.user_id == current_user.id).count()

    active_maintenance = q_active.order_by(MaintenanceLog.date_reported.desc()).all()
    past_maintenance = q_past.order_by(MaintenanceLog.date_reported.desc()).all()

    # 6. OTHER DATA
    last_upload = UploadHistory.query.filter_by(type='Upload').order_by(UploadHistory.id.desc()).first()
    all_history = UploadHistory.query.order_by(UploadHistory.id.desc()).limit(100).all()
    
    users_list = []
    if session.get('role') == 'admin':
        users_list = User.query.order_by(User.id.asc()).all()

    active_user_office = ""
    
    # 7. STATISTICS ANALYSIS
    analysis_results = []
    analysis_total = 0
    analysis_type = request.args.get('analysis_type', 'assets')
    operation_type = request.args.get('operation') 

    stat_material = request.args.get('stat_material', '').strip()
    stat_campus = request.args.get('stat_campus', '')
    stat_location = request.args.get('stat_location', '').strip()
    stat_p_name = request.args.get('stat_p_name', '').strip()
    stat_p_dept = request.args.get('stat_p_dept', '').strip()
    stat_p_campus = request.args.get('stat_p_campus', '')
    stat_p_office = request.args.get('stat_p_office', '').strip()

    f_labels_1, f_values_1 = [], []
    f_labels_2, f_values_2 = [], []

    if active_tab == 'statistics' and operation_type == 'analyze':
        if analysis_type == 'personnel':
            q = Personnel.query
            if stat_p_name:
                t = f"%{normalize_text(stat_p_name)}%"
                q = q.filter(or_(func.NORMALIZE(Personnel.full_name).like(t), func.NORMALIZE(Personnel.title).like(t)))
            if stat_p_dept:
                q = q.filter(func.NORMALIZE(Personnel.department).like(f"%{normalize_text(stat_p_dept)}%"))
            if stat_p_campus and stat_p_campus != "All":
                q = q.filter(Personnel.campus == stat_p_campus)
            if stat_p_office:
                q = q.filter(func.NORMALIZE(Personnel.office).like(f"%{normalize_text(stat_p_office)}%"))
                
            analysis_results = q.order_by(Personnel.department.asc(), Personnel.full_name.asc()).all()
            analysis_total = len(analysis_results)
            
            temp_dept = {}
            temp_title = {}
            for p in analysis_results:
                b = p.department if p.department else "Not Specified"
                u = p.title if p.title else "Not Specified"
                temp_dept[b] = temp_dept.get(b, 0) + 1
                temp_title[u] = temp_title.get(u, 0) + 1
                
            f_labels_1 = list(temp_dept.keys())
            f_values_1 = list(temp_dept.values())
            f_labels_2 = list(temp_title.keys())
            f_values_2 = list(temp_title.values())

        else: # Asset Analysis
            q = db.session.query(
                Asset.name, 
                Asset.campus, 
                Asset.location, 
                func.sum(Asset.quantity).label('total_quantity')
            )
            
            if stat_material:
                q = q.filter(func.NORMALIZE(Asset.name).like(f"%{normalize_text(stat_material)}%"))
            if stat_campus and stat_campus != "All":
                q = q.filter(Asset.campus == stat_campus)
            if stat_location:
                q = q.filter(func.NORMALIZE(Asset.location).like(f"%{normalize_text(stat_location)}%"))
                
            analysis_results = q.group_by(Asset.name, Asset.campus, Asset.location)\
                                .order_by(Asset.campus.asc(), Asset.location.asc()).all()
            
            analysis_total = sum(item.total_quantity for item in analysis_results)
            
            temp_campus = {}
            temp_location = {}
            for item in analysis_results:
                k = item.campus
                qty = item.total_quantity
                temp_campus[k] = temp_campus.get(k, 0) + qty
                
                l_summary = item.location.split('/')[0].strip()
                temp_location[l_summary] = temp_location.get(l_summary, 0) + qty
                
            f_labels_1 = list(temp_campus.keys())
            f_values_1 = list(temp_campus.values())
            f_labels_2 = list(temp_location.keys())
            f_values_2 = list(temp_location.values())

    # 7.5 ASSIGNED ASSETS
    assigned_assets = []
    
    if current_user.is_authenticated and session.get('role') != 'admin':
        current_staff = Personnel.query.filter_by(email=current_user.email).first()
        if current_staff and current_staff.office:
            assigned_assets = Asset.query.filter(
                func.NORMALIZE(Asset.location).like(f"%{normalize_text(current_staff.office)}%")
            ).all()
            session['personnel_office'] = current_staff.office
    
    # 8. RENDER TEMPLATE
    return render_template('index.html',
                           active_tab=active_tab,
                           search_term=search_term,
                           assets=assets,
                           personnel=personnel,
                           
                           active_maintenance=active_maintenance,
                           past_maintenance=past_maintenance,
                           assigned_assets=assigned_assets,
                           notification_count=notification_count,
                           
                           page_a=page_a, total_pages_asset=total_pages_asset,
                           page_p=page_p, total_pages_personnel=total_pages_personnel,
                           
                           chart_campus_labels=chart_campus_labels, chart_campus_values=chart_campus_values,
                           chart_asset_labels=chart_asset_labels, chart_asset_values=chart_asset_values,
                           chart_personnel_labels=chart_personnel_labels, chart_personnel_values=chart_personnel_values,
                           chart_type_labels=chart_type_labels, chart_type_values=chart_type_values,
                           
                           campuses=CAMPUSES, departments=DEPARTMENTS, titles=TITLES,
                           last_upload=last_upload, all_history=all_history,
                           users_list=users_list, active_user_office=active_user_office,

                           analysis_results=analysis_results,
                           analysis_type=analysis_type,
                           analysis_total=analysis_total,
                           stat_material=stat_material, stat_campus=stat_campus, stat_location=stat_location,
                           stat_p_name=stat_p_name, stat_p_dept=stat_p_dept, stat_p_campus=stat_p_campus, stat_p_office=stat_p_office,
                           f_labels_1=f_labels_1, f_values_1=f_values_1,
                           f_labels_2=f_labels_2, f_values_2=f_values_2,
                           open_modal=request.args.get('open_modal', None)
                           )

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(bp.root_path, '../../static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@bp.route('/get-all-ids')
@login_required
def get_all_ids():
    tab = request.args.get('tab', 'assets')
    q = request.args.get('q', '').strip()
    
    auth_level = int(session.get('auth_level', 0))
    role = session.get('role')

    ids = []

    if tab == 'assets':
        query = Asset.query
        if auth_level == 0 and role != 'technician':
            return jsonify([])
            
        if q:
            t = f"%{normalize_text(q)}%"
            query = query.filter(
                or_(
                    func.NORMALIZE(Asset.name).like(t),
                    func.NORMALIZE(Asset.location).like(t)
                )
            )
        ids = [str(item.id) for item in query.all()]

    elif tab == 'personnel':
        query = Personnel.query
        if auth_level == 0 and role != 'technician':
            return jsonify([])

        if q:
            t = f"%{normalize_text(q)}%"
            query = query.filter(
                or_(
                    func.NORMALIZE(Personnel.full_name).like(t),
                    func.NORMALIZE(Personnel.office).like(t)
                )
            )
        ids = [str(item.id) for item in query.all()]

    elif tab == 'maintenance':
        query = MaintenanceLog.query
        if role not in ['admin', 'technician'] and auth_level < 3:
            query = query.filter(MaintenanceLog.user_id == current_user.id)
        
        if q:
            t = f"%{normalize_text(q)}%"
            query = query.filter(
                or_(
                    func.NORMALIZE(MaintenanceLog.title).like(t),
                    func.NORMALIZE(MaintenanceLog.location).like(t)
                )
            )
        ids = [str(item.id) for item in query.all()]

    return jsonify(ids)

@bp.route('/activity-logs')
@login_required
def activity_logs():
    if session.get('role') != 'admin':
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for('main.index'))
    
    logs = UploadHistory.query.order_by(UploadHistory.id.desc()).limit(500).all()
    return render_template('logs.html', logs=logs)

@bp.route('/clear-logs')
@login_required
def clear_logs():
    if session.get('role') != 'admin': return redirect(url_for('main.index'))
    
    try:
        db.session.query(UploadHistory).delete()
        db.session.commit()
        flash("All activity logs cleared.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")
        
    return redirect(url_for('main.activity_logs'))

@bp.route('/backup-db')
@login_required
def backup_db():
    if session.get('role') != 'admin':
        return redirect(url_for('main.index'))
    
    db_file = os.path.join(os.getcwd(), 'asset_management.db')
    
    try:
        return send_file(db_file, as_attachment=True, download_name=f"Backup_DB_{datetime.now().strftime('%Y-%m-%d_%H%M')}.db")
    except Exception as e:
        flash(f"Backup Error: {str(e)}", "danger")
        return redirect(url_for('main.activity_logs'))

@bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@bp.app_errorhandler(500)
def internal_server_error(e):
    db.session.rollback()
    return render_template('500.html'), 500