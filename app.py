from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
import csv
from io import StringIO, BytesIO
import json
from dateutil.relativedelta import relativedelta

from models import db, Task, AppSettings, User, create_default_admin
from config import get_config
import secrets
from datetime import datetime, timedelta

# Initialize Flask app with configuration
app = Flask(__name__)
config_class = get_config()
app.config.from_object(config_class)

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin-only decorator
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Password reset token generation
def generate_reset_token():
    return secrets.token_urlsafe(32)

def verify_reset_token(token, max_age=3600):  # 1 hour expiry
    """Simple token verification (in production, use JWT or database storage)"""
    # For now, we'll use a simple approach
    # In production, you'd want to store tokens in database with expiry
    return token and len(token) > 20  # Basic validation

# Create database tables on app startup
with app.app_context():
    try:
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')
        print(f"Database URL: {db_url}")

        # Drop and recreate tables if needed (for migration)
        print("Dropping existing tables...")
        db.drop_all()
        print("Creating new tables...")
        db.create_all()

        create_default_admin()  # Create default admin user
        print("✅ Database tables initialized successfully")
        print(f"✅ Connected to: {'PostgreSQL' if 'postgresql' in db_url else 'SQLite'}")
        print("✅ Default admin user created")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print(f"Database URL: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')}")

# Helper function to parse dates flexibly
def parse_date_flexible(date_str):
    """Parse date string that could be in multiple formats"""
    from datetime import datetime
    if not date_str:
        return None

    # Common date formats to try
    formats = [
        '%Y-%m-%d',      # 2025-05-12
        '%d/%m/%Y',      # 12/05/2025
        '%m/%d/%Y',      # 05/12/2025
        '%d-%m-%Y',      # 12-05-2025
        '%Y/%m/%d',      # 2025/05/12
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue

    # If no format works, try to handle Excel date numbers
    try:
        # Excel sometimes stores dates as numbers (days since 1900-01-01)
        if isinstance(date_str, (int, float)):
            from datetime import datetime as dt, timedelta
            excel_epoch = dt(1900, 1, 1)
            return (excel_epoch + timedelta(days=int(date_str) - 2)).date()
    except:
        pass

    return None

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('register.html')

            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'error')
                return render_template('register.html')

            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'error')
                return render_template('register.html')

            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Registration error: {e}")
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('register.html')

    return render_template('register.html')

# Password reset routes
@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            # In production, send email with reset token
            reset_token = generate_reset_token()
            # Store token in session for demo (in production, store in database)
            session['reset_token'] = reset_token
            session['reset_user_id'] = user.id
            session['reset_expiry'] = (datetime.utcnow() + timedelta(hours=1)).isoformat()

            flash('Password reset instructions sent to your email.', 'info')
            return redirect(url_for('reset_password', token=reset_token))
        else:
            flash('Email address not found.', 'error')

    return render_template('reset_password_request.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    # Verify token
    if not verify_reset_token(token):
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', token=token)

        # Get user from session (in production, verify token properly)
        user_id = session.get('reset_user_id')
        if not user_id:
            flash('Invalid reset session.', 'error')
            return redirect(url_for('login'))

        user = User.query.get(user_id)
        if user:
            user.set_password(password)
            db.session.commit()

            # Clear session
            session.pop('reset_token', None)
            session.pop('reset_user_id', None)
            session.pop('reset_expiry', None)

            flash('Password reset successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'error')

    return render_template('reset_password.html', token=token)

# Admin routes
@app.route('/admin/users')
@login_required
@admin_required
def manage_users():
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/admin/reset_user_password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password')

    if new_password:
        user.set_password(new_password)
        db.session.commit()
        flash(f'Password reset for user {user.username}', 'success')
    else:
        flash('Password cannot be empty', 'error')

    return redirect(url_for('manage_users'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    if current_user.id == user_id:
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('manage_users'))

    user = User.query.get_or_404(user_id)

    # Delete user's tasks first
    Task.query.filter_by(user_id=user_id).delete()

    # Delete user
    db.session.delete(user)
    db.session.commit()

    flash(f'User {user.username} deleted successfully', 'success')
    return redirect(url_for('manage_users'))

# Load tasks from database
def load_tasks():
    """Load all active (non-deleted) tasks for current user"""
    if current_user.is_authenticated:
        tasks_db = Task.query.filter_by(user_id=current_user.id).filter(Task.status != "Deleted").all()
        return [task.to_dict() for task in tasks_db]
    return []

# Load archived (deleted) tasks
def load_archived_tasks():
    """Load all deleted/archived tasks for current user"""
    if current_user.is_authenticated:
        tasks_db = Task.query.filter_by(user_id=current_user.id, status="Deleted").all()
        return [task.to_dict() for task in tasks_db]
    return []

# Save a new task to database
def add_task(data):
    """Add a new task to the database"""
    # Load current settings and custom columns
    settings = load_settings()
    custom_columns = [col['name'] for col in settings.get('custom_columns', [])]

    # Auto-generate next ID
    last_task = Task.query.order_by(Task.id.desc()).first()
    if last_task and last_task.id.startswith('T'):
        try:
            last_num = int(last_task.id[1:])
            next_id = f"T{last_num + 1:03d}"
        except ValueError:
            next_id = f"T{Task.query.count() + 1:03d}"
    else:
        next_id = f"T{Task.query.count() + 1:03d}"

    # Prepare custom fields
    custom_fields = {}
    for col in custom_columns:
        if col in data:
            custom_fields[col] = data.get(col, '')

    # Create new task
    task = Task(
        id=next_id,
        type=data.get('Type'),
        product=data.get('Product'),
        module=data.get('Module'),
        description=data.get('Description'),
        status=data.get('Status', 'Not Started'),
        priority=data.get('Priority'),
        created_date=parse_date_flexible(data.get('Created Date', datetime.today().strftime('%Y-%m-%d'))),
        due_date=parse_date_flexible(data.get('Due Date')),
        current_action_plan=data.get('Current Action Plan'),
        action_plan_history=f"[{datetime.today().strftime('%Y-%m-%d')}]\n{data.get('Current Action Plan', '').strip()}" if data.get('Current Action Plan') else '',
        custom_fields=custom_fields if custom_fields else None,
        user_id=current_user.id
    )

    db.session.add(task)
    db.session.commit()

# Update action plan
@app.route('/update_action_plan', methods=['POST'])
def update_action_plan():
    data = request.json
    row_id = str(data['id']).strip()
    new_plan = data['new_action_plan'].strip()

    task = Task.query.filter_by(id=row_id).first()
    if task:
        task.current_action_plan = new_plan
        history = task.action_plan_history or ''
        timestamp = datetime.now().date().isoformat()
        new_entry = f"[{timestamp}]\n{new_plan.strip()}\n"
        task.action_plan_history = (new_entry + '\n' + history).strip()
        db.session.commit()
        return jsonify({'status': 'success'})

    return jsonify({'status': 'error', 'message': 'Task not found'})

# Standup action plan update - moves current plan to history and sets new plan as current
@app.route('/standup_update_action_plan', methods=['POST'])
def standup_update_action_plan():
    data = request.json
    row_id = str(data['id']).strip()
    new_plan = data['new_action_plan'].strip()

    task = Task.query.filter_by(id=row_id).first()
    if task:
        # Get current action plan to move to history
        current_plan = task.current_action_plan or ''
        history = task.action_plan_history or ''

        # Move current plan to history with standup timestamp
        if current_plan.strip():
            timestamp = datetime.now().date().isoformat()
            standup_entry = f"[STANDUP {timestamp}]\n{current_plan.strip()}\n"
            if history:
                task.action_plan_history = (standup_entry + '\n' + history).strip()
            else:
                task.action_plan_history = standup_entry.strip()

        # Set new plan as current action plan
        task.current_action_plan = new_plan
        db.session.commit()
        return jsonify({'status': 'success'})

    return jsonify({'status': 'error', 'message': 'Task not found'})

# Delete task by ID (mark as Deleted)
@app.route('/get_task/<task_id>')
def get_task(task_id):
    task = Task.query.filter_by(id=task_id, status='Deleted').first()
    if task:
        return jsonify(task.to_dict())

    return jsonify({'error': 'Task not found'}), 404

@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.json
    task_id = str(data['id']).strip()

    task = Task.query.filter_by(id=task_id).first()
    if task:
        task.status = "Deleted"
        db.session.commit()
        return jsonify({'status': 'success'})

    return jsonify({'status': 'error', 'message': 'Task not found'})

# Load settings from database
def load_settings():
    """Load settings from database with defaults"""
    settings = AppSettings.get_settings()

    # Set defaults if not found
    defaults = {
        'status_options': ['Not Started', 'In Progress', 'Completed', 'Pending from User', 'On Hold'],
        'type_options': ['Bug', 'Feature', 'Task'],
        'priority_options': ['Low', 'Medium', 'High', 'Critical'],
        'product_options': ['Finance', 'Procurement', 'OIC', 'ROSS', 'E-Invoice'],
        'module_options': ['Authentication', 'Dashboard', 'Reports', 'Settings', 'User Management', 'Task Management']
    }

    # Merge database settings with defaults
    for key, default_value in defaults.items():
        if key not in settings:
            settings[key] = default_value
            AppSettings.set_setting(key, default_value)

    # Ensure custom_columns is properly formatted
    if 'custom_columns' not in settings:
        settings['custom_columns'] = []
        AppSettings.set_setting('custom_columns', [])
    elif isinstance(settings['custom_columns'], list):
        settings['custom_columns'] = [
            {"name": col, "type": "text"} if isinstance(col, str) else col
            for col in settings['custom_columns']
        ]

    return settings

# Save settings to database
def save_settings(data):
    """Save settings to database"""
    if 'custom_columns' not in data:
        data['custom_columns'] = []
    elif isinstance(data['custom_columns'], list):
        data['custom_columns'] = [
            {"name": col['name'], "type": col.get('type', 'text')} if isinstance(col, dict) else {"name": col, "type": "text"}
            for col in data['custom_columns']
        ]

    # Save each setting to database
    for key, value in data.items():
        AppSettings.set_setting(key, value)

# Load tasks view
@app.route('/')
@login_required
def index():
    tasks = load_tasks()
    settings = load_settings()
    summary = {
        'completed': sum(1 for t in tasks if t.get('Status') == 'Completed'),
        'in_progress': sum(1 for t in tasks if t.get('Status') == 'In Progress'),
        'overdue': sum(1 for t in tasks if t.get('is_overdue')),
        'total': len(tasks)
    }

    # Enhanced standup metrics
    from datetime import datetime, timedelta
    today = datetime.today().date()
    week_ago = today - timedelta(days=7)

    standup_metrics = {
        'completed_this_week': sum(1 for t in tasks if t.get('Status') == 'Completed' and t.get('Created Date') and
                                   parse_date_flexible(t.get('Created Date')) and
                                   parse_date_flexible(t.get('Created Date')) >= week_ago),
        'overdue_tasks': [t for t in tasks if t.get('is_overdue') and t.get('Status') != 'Completed'],
        'high_priority_open': sum(1 for t in tasks if t.get('Priority') in ['High', 'Critical'] and t.get('Status') != 'Completed'),
        'tasks_by_category': {}
    }

    # Group tasks by category for standup
    for task in tasks:
        category = task.get('Category', 'Uncategorized')
        if category not in standup_metrics['tasks_by_category']:
            standup_metrics['tasks_by_category'][category] = {'total': 0, 'completed': 0, 'in_progress': 0}
        standup_metrics['tasks_by_category'][category]['total'] += 1
        if task.get('Status') == 'Completed':
            standup_metrics['tasks_by_category'][category]['completed'] += 1
        elif task.get('Status') == 'In Progress':
            standup_metrics['tasks_by_category'][category]['in_progress'] += 1

    return render_template('index.html', tasks=tasks, settings=settings, summary=summary, standup_metrics=standup_metrics)

# Archived tasks view
@app.route('/archived')
def archived():
    tasks = load_archived_tasks()
    return render_template('archived.html', tasks=tasks)

# Add new task
@app.route('/add_task', methods=['POST'])
def add_new_task():
    data = request.json
    add_task(data)
    return jsonify({'status': 'success'})

# Export to CSV
@app.route('/export_csv')
def export_csv():
    tasks = load_tasks()
    if not tasks:
        return "No data to export", 400

    headers = tasks[0].keys()
    text_stream = StringIO()
    writer = csv.DictWriter(text_stream, fieldnames=headers)
    writer.writeheader()
    writer.writerows(tasks)

    output = BytesIO()
    output.write(text_stream.getvalue().encode('utf-8'))
    output.seek(0)

    return send_file(
        output,
        mimetype='text/csv',
        download_name='tasks_export.csv',
        as_attachment=True
    )

# Import from CSV
@app.route('/import_csv', methods=['POST'])
def import_csv():
    file = request.files['file']
    if not file or not file.filename.endswith('.csv'):
        return jsonify({'status': 'error', 'message': 'Invalid file format'})

    csv_data = file.read().decode('utf-8').splitlines()
    reader = csv.DictReader(csv_data)

    # Clear existing tasks
    Task.query.delete()
    db.session.commit()

    # Import new tasks from CSV
    for row in reader:
        task = Task(
            id=row.get('ID', '').strip(),
            type=row.get('Type'),
            product=row.get('Product'),
            module=row.get('Module'),
            description=row.get('Description'),
            status=row.get('Status', 'Not Started'),
            priority=row.get('Priority'),
            created_date=parse_date_flexible(row.get('Created Date')),
            due_date=parse_date_flexible(row.get('Due Date')),
            status_update_date=parse_date_flexible(row.get('Status Update Date')),
            action_plan_status=row.get('Action Plan Status'),
            current_action_plan=row.get('Current Action Plan'),
            action_plan_history=row.get('Action Plan History'),
            category=row.get('Category')
        )
        db.session.add(task)

    db.session.commit()
    return jsonify({'status': 'success'})

# Settings page view
@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        data = request.json
        save_settings(data)
        return jsonify({'status': 'success'})
    else:
        return jsonify(load_settings())

# Restore archived task
@app.route('/restore_task', methods=['POST'])
def restore_task():
    data = request.json
    task_id = str(data['id']).strip()

    task = Task.query.filter_by(id=task_id, status="Deleted").first()
    if task:
        task.status = "Not Started"
        db.session.commit()
        return jsonify({'status': 'success'})

    return jsonify({'status': 'error', 'message': 'Task not found or not deleted'})



# Update task details
@app.route('/edit_task', methods=['POST'])
def edit_task():
    data = request.json
    task_id = str(data.get('ID', '')).strip()

    task = Task.query.filter_by(id=task_id).first()
    if not task:
        return jsonify({'status': 'error', 'message': 'Task not found'}), 404

    settings = load_settings()
    custom_columns = [col['name'] for col in settings.get('custom_columns', [])]

    # Update standard fields
    if 'Type' in data:
        task.type = data['Type']
    if 'Product' in data:
        task.product = data['Product']
    if 'Module' in data:
        task.module = data['Module']
    if 'Description' in data:
        task.description = data['Description']
    if 'Status' in data:
        task.status = data['Status']
    if 'Priority' in data:
        task.priority = data['Priority']
    if 'Created Date' in data:
        task.created_date = parse_date_flexible(data['Created Date'])
    if 'Due Date' in data:
        task.due_date = parse_date_flexible(data['Due Date'])
    if 'Status Update Date' in data:
        task.status_update_date = parse_date_flexible(data['Status Update Date'])
    if 'Action Plan Status' in data:
        task.action_plan_status = data['Action Plan Status']
    if 'Current Action Plan' in data:
        task.current_action_plan = data['Current Action Plan']
    if 'Action Plan History' in data:
        task.action_plan_history = data['Action Plan History']
    if 'Category' in data:
        task.category = data['Category']

    # Update custom fields
    if not task.custom_fields:
        task.custom_fields = {}

    for col in custom_columns:
        if col in data:
            task.custom_fields[col] = data[col]

    db.session.commit()
    return jsonify({'status': 'success'})

# Analytics page
@app.route('/analytics')
def analytics():
    tasks = load_tasks()

    # Calculate analytics data
    analytics_data = {
        'total_tasks': len(tasks),
        'completed_tasks': sum(1 for t in tasks if t.get('Status') == 'Completed'),
        'in_progress_tasks': sum(1 for t in tasks if t.get('Status') == 'In Progress'),
        'not_started_tasks': sum(1 for t in tasks if t.get('Status') == 'Not Started'),
        'on_hold_tasks': sum(1 for t in tasks if t.get('Status') == 'On Hold'),
        'overdue_tasks': sum(1 for t in tasks if t.get('is_overdue')),
        'tasks_by_type': {},
        'tasks_by_category': {},
        'tasks_by_product': {},
        'tasks_by_module': {},
        'tasks_by_priority': {},
        'completion_trend': {},
        'productivity_trend': {},
        'weekly_stats': {}
    }

    # Group tasks by various dimensions
    for task in tasks:
        # By Type
        task_type = task.get('Type', 'Unknown')
        if task_type not in analytics_data['tasks_by_type']:
            analytics_data['tasks_by_type'][task_type] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_type'][task_type]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_type'][task_type]['completed'] += 1

        # By Category
        category = task.get('Category', 'Unknown')
        if category not in analytics_data['tasks_by_category']:
            analytics_data['tasks_by_category'][category] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_category'][category]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_category'][category]['completed'] += 1

        # By Product
        product = task.get('Product', 'Unknown')
        if product not in analytics_data['tasks_by_product']:
            analytics_data['tasks_by_product'][product] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_product'][product]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_product'][product]['completed'] += 1

        # By Module
        module = task.get('Module', 'Unknown')
        if module not in analytics_data['tasks_by_module']:
            analytics_data['tasks_by_module'][module] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_module'][module]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_module'][module]['completed'] += 1

        # By Priority
        priority = task.get('Priority', 'Unknown')
        if priority not in analytics_data['tasks_by_priority']:
            analytics_data['tasks_by_priority'][priority] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_priority'][priority]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_priority'][priority]['completed'] += 1

        # Completion trend by date
        created_date = task.get('Created Date', '')
        if created_date and task.get('Status') == 'Completed':
            if created_date not in analytics_data['completion_trend']:
                analytics_data['completion_trend'][created_date] = 0
            analytics_data['completion_trend'][created_date] += 1

    # Calculate completion rates
    for key in ['tasks_by_type', 'tasks_by_category', 'tasks_by_product', 'tasks_by_module', 'tasks_by_priority']:
        for item_key, item_data in analytics_data[key].items():
            if item_data['total'] > 0:
                item_data['completion_rate'] = round((item_data['completed'] / item_data['total']) * 100, 1)
            else:
                item_data['completion_rate'] = 0

    # Calculate overall completion rate
    analytics_data['overall_completion_rate'] = 0
    if analytics_data['total_tasks'] > 0:
        analytics_data['overall_completion_rate'] = round((analytics_data['completed_tasks'] / analytics_data['total_tasks']) * 100, 1)

    # Calculate average tasks per day (last 30 days)
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_tasks = [t for t in tasks if t.get('Created Date') and
                   parse_date_flexible(t.get('Created Date')) and
                   parse_date_flexible(t.get('Created Date')) >= thirty_days_ago]

    analytics_data['avg_tasks_per_day'] = round(len(recent_tasks) / 30, 1) if recent_tasks else 0

    return render_template('analytics.html', analytics=analytics_data)

# Export analytics report
@app.route('/export_analytics')
def export_analytics():
    tasks = load_tasks()

    # Calculate analytics data (same as analytics route)
    analytics_data = {
        'total_tasks': len(tasks),
        'completed_tasks': sum(1 for t in tasks if t.get('Status') == 'Completed'),
        'in_progress_tasks': sum(1 for t in tasks if t.get('Status') == 'In Progress'),
        'not_started_tasks': sum(1 for t in tasks if t.get('Status') == 'Not Started'),
        'on_hold_tasks': sum(1 for t in tasks if t.get('Status') == 'On Hold'),
        'overdue_tasks': sum(1 for t in tasks if t.get('is_overdue')),
        'tasks_by_type': {},
        'tasks_by_category': {},
        'tasks_by_product': {},
        'tasks_by_module': {},
        'tasks_by_priority': {},
    }

    # Group tasks by various dimensions
    for task in tasks:
        # By Type
        task_type = task.get('Type', 'Unknown')
        if task_type not in analytics_data['tasks_by_type']:
            analytics_data['tasks_by_type'][task_type] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_type'][task_type]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_type'][task_type]['completed'] += 1

        # By Product
        product = task.get('Product', 'Unknown')
        if product not in analytics_data['tasks_by_product']:
            analytics_data['tasks_by_product'][product] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_product'][product]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_product'][product]['completed'] += 1

        # By Module
        module = task.get('Module', 'Unknown')
        if module not in analytics_data['tasks_by_module']:
            analytics_data['tasks_by_module'][module] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_module'][module]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_module'][module]['completed'] += 1

        # By Priority
        priority = task.get('Priority', 'Unknown')
        if priority not in analytics_data['tasks_by_priority']:
            analytics_data['tasks_by_priority'][priority] = {'total': 0, 'completed': 0}
        analytics_data['tasks_by_priority'][priority]['total'] += 1
        if task.get('Status') == 'Completed':
            analytics_data['tasks_by_priority'][priority]['completed'] += 1

    # Calculate completion rates
    for key in ['tasks_by_type', 'tasks_by_product', 'tasks_by_module', 'tasks_by_priority']:
        for item_key, item_data in analytics_data[key].items():
            if item_data['total'] > 0:
                item_data['completion_rate'] = round((item_data['completed'] / item_data['total']) * 100, 1)
            else:
                item_data['completion_rate'] = 0

    # Create CSV content
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['ProgressPad Analytics Report'])
    writer.writerow(['Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])

    # Write summary metrics
    writer.writerow(['SUMMARY METRICS'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total Tasks', analytics_data['total_tasks']])
    writer.writerow(['Completed Tasks', analytics_data['completed_tasks']])
    writer.writerow(['In Progress Tasks', analytics_data['in_progress_tasks']])
    writer.writerow(['Not Started Tasks', analytics_data['not_started_tasks']])
    writer.writerow(['On Hold Tasks', analytics_data['on_hold_tasks']])
    writer.writerow(['Overdue Tasks', analytics_data['overdue_tasks']])
    writer.writerow(['Overall Completion Rate (%)', f"{round((analytics_data['completed_tasks'] / max(analytics_data['total_tasks'], 1)) * 100, 1)}"])
    writer.writerow([])

    # Write product performance
    writer.writerow(['PRODUCT PERFORMANCE'])
    writer.writerow(['Product', 'Total Tasks', 'Completed', 'Completion Rate (%)'])
    for product, data in analytics_data['tasks_by_product'].items():
        writer.writerow([product, data['total'], data['completed'], data['completion_rate']])
    writer.writerow([])

    # Write module performance
    writer.writerow(['MODULE PERFORMANCE'])
    writer.writerow(['Module', 'Total Tasks', 'Completed', 'Completion Rate (%)'])
    for module, data in analytics_data['tasks_by_module'].items():
        writer.writerow([module, data['total'], data['completed'], data['completion_rate']])
    writer.writerow([])

    # Write priority distribution
    writer.writerow(['PRIORITY DISTRIBUTION'])
    writer.writerow(['Priority', 'Total Tasks', 'Completed', 'Completion Rate (%)'])
    for priority, data in analytics_data['tasks_by_priority'].items():
        writer.writerow([priority, data['total'], data['completed'], data['completion_rate']])
    writer.writerow([])

    # Write task types
    writer.writerow(['TASK TYPES'])
    writer.writerow(['Type', 'Total Tasks', 'Completed', 'Completion Rate (%)'])
    for task_type, data in analytics_data['tasks_by_type'].items():
        writer.writerow([task_type, data['total'], data['completed'], data['completion_rate']])

    # Prepare response
    output.seek(0)
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        download_name=f'ProgressPad_Analytics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        as_attachment=True
    )

# Health check endpoint for Railway
@app.route('/health')
def health_check():
    """Health check endpoint for deployment monitoring"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'database_url': app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')[:50] + '...',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'database_url': app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')[:50] + '...',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Debug endpoint to check database tables
@app.route('/debug/db')
def debug_database():
    """Debug endpoint to check database status"""
    try:
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        # Check counts
        task_count = Task.query.count()
        user_count = User.query.count()

        return jsonify({
            'database_connected': True,
            'tables': tables,
            'task_count': task_count,
            'user_count': user_count,
            'database_url': app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')[:50] + '...',
            'has_tasks_table': 'tasks' in tables,
            'has_users_table': 'users' in tables,
            'has_app_settings_table': 'app_settings' in tables
        })
    except Exception as e:
        return jsonify({
            'database_connected': False,
            'error': str(e),
            'database_url': app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')[:50] + '...'
        }), 500

if __name__ == '__main__':
    with app.app_context():
        # Create database tables
        db.create_all()
        print("✅ Database tables initialized")

    # Run the application
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])