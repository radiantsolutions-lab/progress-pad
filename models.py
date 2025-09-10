from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    # Relationship with tasks
    tasks = db.relationship('Task', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.String(10), primary_key=True)
    type = db.Column(db.String(50))
    product = db.Column(db.String(100))
    module = db.Column(db.String(100))
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='Not Started')
    priority = db.Column(db.String(50))
    created_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    status_update_date = db.Column(db.Date)
    action_plan_status = db.Column(db.String(100))
    current_action_plan = db.Column(db.Text)
    action_plan_history = db.Column(db.Text)
    category = db.Column(db.String(100))  # Added category field
    requester = db.Column(db.String(100))  # New field: Requester
    business_unit = db.Column(db.String(100))  # New field: Business Unit

    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Custom columns stored as JSON for flexibility
    custom_fields = db.Column(JSON, default=dict)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert task to dictionary format compatible with existing code"""
        result = {
            'ID': self.id,
            'Type': self.type,
            'Product': self.product,
            'Module': self.module,
            'Description': self.description,
            'Status': self.status,
            'Priority': self.priority,
            'Created Date': self.created_date.isoformat() if self.created_date else None,
            'Due Date': self.due_date.isoformat() if self.due_date else None,
            'Status Update Date': self.status_update_date.isoformat() if self.status_update_date else None,
            'Action Plan Status': self.action_plan_status,
            'Current Action Plan': self.current_action_plan,
            'Action Plan History': self.action_plan_history,
            'Category': self.category,
            'Requester': self.requester,
            'Business Unit': self.business_unit,
            'is_overdue': False,
            'due_soon': False,
            'due_today': False
        }

        # Add custom fields
        if self.custom_fields:
            result.update(self.custom_fields)

        # Calculate date-based flags
        if self.due_date and self.status != 'Completed':
            today = datetime.today().date()
            if self.due_date < today:
                result['is_overdue'] = True
            elif self.due_date == today:
                result['due_today'] = True
            elif (self.due_date - today).days <= 3:
                result['due_soon'] = True

        return result

class AppSettings(db.Model):
    __tablename__ = 'app_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_settings():
        """Get all settings as a dictionary"""
        settings = {}
        for setting in AppSettings.query.all():
            settings[setting.key] = setting.value
        return settings

    @staticmethod
    def set_setting(key, value):
        """Set a setting value"""
        setting = AppSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = AppSettings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

def create_default_admin():
    """Create a default admin user if none exists"""
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin user created: admin/admin123")
        return admin
    return None
