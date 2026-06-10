from flask import render_template, redirect, url_for, flash, request, session, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from flask_mail import Message
from app import mail
from app.utils import get_reset_token, verify_reset_token, save_log
from app.models import User, UploadHistory
from app import db
from datetime import datetime

# ----------------------------------------------------
# LOGIN / LOGOUT OPERATIONS
# ----------------------------------------------------

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if session.get('role') == 'technician':
            return redirect(url_for('main.index', tab='maintenance'))
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        remember_me = True if request.form.get('remember_me') else False
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember_me)
            
            session['role'] = user.role
            session['full_name'] = user.full_name
            session['department'] = user.department
            session['auth_level'] = user.auth_level if user.auth_level is not None else 0
            
            next_page = request.args.get('next')
            if not next_page:
                if user.role == 'technician':
                    next_page = url_for('main.index', tab='maintenance')
                else:
                    next_page = url_for('main.index')
            
            response = make_response(redirect(next_page))
            
            if remember_me:
                response.set_cookie('last_username', username, max_age=30*24*60*60)
            else:
                response.delete_cookie('last_username')
            
            return response
            
        else:
            flash('Invalid username or password!', 'danger')
            
    last_username = request.cookies.get('last_username', '')
    
    return render_template('auth/login.html', last_username=last_username)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    
    for key in ['role', 'full_name', 'department', 'auth_level']:
        session.pop(key, None)
        
    flash('Successfully logged out.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/password-reset-request', methods=['POST'])
def request_password_reset():
    contact_info = request.form.get('contact_info')
    
    if '@' not in contact_info:
        email = contact_info + '@avrasya.edu.tr'
    else:
        email = contact_info
        
    user = User.query.filter_by(email=email).first()
    
    if user:
        token = get_reset_token(user.id)
        link = url_for('auth.reset_password', token=token, _external=True)
        
        msg = Message('🔒 Password Reset Request', recipients=[user.email])
        
        msg.body = f"Hello {user.full_name}, to reset your password, visit the following link: {link}"
        
        msg.html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    <h2 style="color: #092442; text-align: center;">Password Reset</h2>
                    <p>Hello <strong>{user.full_name}</strong>,</p>
                    <p>You have requested to reset your password. Click the button below to set a new password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{link}" style="background-color: #0d6efd; color: white; padding: 14px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; display: inline-block;">
                            Reset My Password
                        </a>
                    </div>
                    <p style="color: #666; font-size: 13px;">
                        This link is valid for 30 minutes.<br>
                        If the button doesn't work, copy and paste the following link into your browser:
                    </p>
                    <p style="word-break: break-all; color: #999; font-size: 11px;">{link}</p>
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="text-align: center; color: #aaa; font-size: 11px;">
                        Enterprise Asset Management System
                    </p>
                </div>
            </body>
        </html>
        """
        
        try:
            mail.send(msg)
            flash(f"Reset link sent to {user.email}.", "info")
        except Exception as e:
            flash(f"Failed to send email. Error: {str(e)}", "danger")
            print(f"MAIL ERROR: {e}")
            
    else:
        flash("No email registered with this username.", "warning")
        
    return redirect(url_for('auth.login'))

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user_id = verify_reset_token(token)
    if user_id is None:
        flash('The reset link is invalid or has expired.', 'warning')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('auth/reset_password.html', token=token)
            
        user = User.query.get(user_id)
        user.password = generate_password_hash(password)
        db.session.commit()
        
        flash('Your password has been successfully updated! You may now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', token=token)

@bp.route('/add-user', methods=['POST'])
@login_required
def add_user():
    if session.get('role') != 'admin': 
        return redirect(url_for('main.index'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    role = request.form.get('role')
    department = request.form.get('department')
    
    try: auth_level = int(request.form.get('auth_level', 0))
    except: auth_level = 0

    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        flash("This username or email is already in use.", "warning")
    else:
        new_user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            department=department,
            auth_level=auth_level,
            password=generate_password_hash(password),
            created_date=datetime.now().strftime("%d-%m-%Y %H:%M")
        )
        db.session.add(new_user)
        db.session.commit()
        save_log("User Added", f"{username}", "Addition")
        flash(f"User {username} added successfully.", "success")
        
    return redirect(url_for('main.index', open_modal='userModal'))

@bp.route('/update-user', methods=['POST'])
@login_required
def update_user():
    if session.get('role') != 'admin':
        return redirect(url_for('main.index'))

    user_id = request.form.get('user_id')
    user = User.query.get(user_id)
    
    if user:
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.full_name = request.form.get('full_name')
        user.role = request.form.get('role')
        user.department = request.form.get('department')
        try: user.auth_level = int(request.form.get('auth_level', 0))
        except: user.auth_level = 0
            
        password = request.form.get('password')
        if password and password.strip() != "":
            user.password = generate_password_hash(password)
            
        db.session.commit()
        save_log("User Updated", f"{user.username}", "Update")
        flash("User information updated.", "success")
    else:
        flash("User not found.", "danger")
        
    return redirect(url_for('main.index', open_modal='userModal'))

@bp.route('/delete-user/<int:id>')
@login_required
def delete_user(id):
    if session.get('role') != 'admin': return redirect(url_for('main.index'))
    
    user = User.query.get(id)
    if user:
        if user.username == 'admin':
            flash("The main administrator cannot be deleted!", "danger")
        else:
            username = user.username
            db.session.delete(user)
            db.session.commit()
            save_log("User Deleted", f"{username}", "Deletion")
            flash("User deleted.", "success")
            
    return redirect(url_for('main.index', open_modal='userModal'))