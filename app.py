from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import numpy as np
import json


app = Flask(__name__)

# # ====== APP STATE (simple version) ======
# domains = None
# scores = None


# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'  # Needed for sessions

db = SQLAlchemy(app)


# ============================================
# DATABASE MODELS
# ============================================

class User(db.Model):
    """User account table"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Hash the password before storing"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class DomainData(db.Model):
    """Stores domain names and scores for radar chart - ONE ROW PER USER"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    
    # Store as JSON strings
    domains = db.Column(db.Text, nullable=True)  # JSON array: ["Sport", "Intellect", ...]
    scores = db.Column(db.Text, nullable=True)   # JSON array: [0, 5, 10, ...]
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='domain_data')
    
    def get_domains(self):
        """Parse JSON string to list"""
        return json.loads(self.domains) if self.domains else None
    
    def get_scores(self):
        """Parse JSON string to list"""
        return json.loads(self.scores) if self.scores else None
    
    def set_domains(self, domain_list):
        """Convert list to JSON string"""
        self.domains = json.dumps(domain_list)
    
    def set_scores(self, score_list):
        """Convert list to JSON string"""
        self.scores = json.dumps(score_list)



class HourEntry(db.Model):
    """Hours tracking for bar chart - MULTIPLE ROWS PER USER"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    work_hours = db.Column(db.Float, nullable=False)
    # study_hours = db.Column(db.Float, nullable=False)
    
    date = db.Column(db.Date, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='hour_entries')
    
    def to_dict(self):
        return {
            'id': self.id,
            'work_hours': self.work_hours,
            # 'study_hours': self.study_hours,
            'date': self.date.strftime('%Y-%m-%d'),
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }



# Create tables
with app.app_context():
    db.create_all()


# ============================================
# AUTHENTICATION DECORATOR
# ============================================

def login_required(f):
    """
    Decorator to protect routes that require login
    
    Usage:
        @app.route('/protected')
        @login_required
        def protected_page():
            return "You can only see this if logged in"
    
    How it works:
        1. Checks if 'user_id' exists in session
        2. If yes, calls the original function
        3. If no, redirects to login page
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



# ============================================
# AUTHENTICATION ROUTES
# ============================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        # Find user in database
        user = User.query.filter_by(username=username).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(password):
            # Store user_id in session (this is how Flask remembers you're logged in)
            session['user_id'] = user.id
            session['username'] = user.username
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
    
    # GET request - show login page
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page and handler"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        # Validation
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password required'}), 400
        
        if len(password) < 4:
            return jsonify({'success': False, 'message': 'Password must be at least 4 characters'}), 400
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': 'Username already taken'}), 400
        
        # Create new user
        new_user = User(username=username)
        new_user.set_password(password)  # This hashes the password
        
        db.session.add(new_user)
        db.session.commit()
        
        # Auto-login after registration
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        
        return jsonify({'success': True, 'message': 'Registration successful'})
    
    # GET request - show registration page
    return render_template('register.html')



@app.route('/logout')
def logout():
    """Clear session and redirect to login"""
    session.clear()
    return redirect(url_for('login'))







# ====== HELPERS ======
def sigmoid(x):
    return 1 / (1 + np.exp(-0.1 * x))


def get_graph_data():
    return {
        "theta": domains,
        "r": [100 * sigmoid(s) for s in scores]
    }

def get_or_create_domain_data(user_id):
    """Get user's domain data, create if doesn't exist"""
    domain_data = DomainData.query.filter_by(user_id=user_id).first()
    if not domain_data:
        domain_data = DomainData(user_id=user_id)
        db.session.add(domain_data)
        db.session.commit()
    return domain_data



# ============================================
# RADAR CHART ROUTES (Domain Scores)
# ============================================

@app.route('/')
@login_required
def index():
    """Main app page"""
    return render_template('index.html', username=session.get('username'))


@app.route('/status')
@login_required
def status():
    """Check if user has initialized domains"""
    user_id = session['user_id']
    domain_data = get_or_create_domain_data(user_id)
    
    initialized = domain_data.get_domains() is not None
    
    return jsonify({'initialized': initialized})


@app.route('/init', methods=['POST'])
@login_required
def init():
    """Initialize user's domains"""
    user_id = session['user_id']
    domain_data = get_or_create_domain_data(user_id)
    
    data = request.get_json()
    domains = data['domains']
    
    # Save domains and initialize scores to 0
    domain_data.set_domains(domains)
    domain_data.set_scores([0.0] * len(domains))
    
    db.session.commit()
    
    return jsonify({
        'theta': domains,
        'r': [100 * sigmoid(0) for _ in domains]
    })


@app.route('/get-data')
@login_required
def get_data():
    """Get radar chart data"""
    user_id = session['user_id']
    domain_data = get_or_create_domain_data(user_id)
    
    domains = domain_data.get_domains()
    scores = domain_data.get_scores()
    
    if domains is None:
        return jsonify({'error': 'Not initialized'}), 400
    
    return jsonify({
        'theta': domains,
        'r': [100 * sigmoid(s) for s in scores]
    })


@app.route('/update-score', methods=['POST'])
@login_required
def update_score():
    """Update a domain score"""
    user_id = session['user_id']
    domain_data = get_or_create_domain_data(user_id)
    
    data = request.get_json()
    index = data['index']
    change = data['change']
    
    # Get current scores
    scores = domain_data.get_scores()
    domains = domain_data.get_domains()
    
    # Update the score
    scores[index] += change
    
    # Save back to database
    domain_data.set_scores(scores)
    db.session.commit()
    
    return jsonify({
        'theta': domains,
        'r': [100 * sigmoid(s) for s in scores]
    })



# ============================================
# HOURS TRACKING ROUTES (Bar Chart)
# ============================================

@app.route('/get-hours')
@login_required
def get_hours():
    """Get all hour entries for bar chart"""
    user_id = session['user_id']
    entries = HourEntry.query.filter_by(user_id=user_id).order_by(HourEntry.date).all()
    
    return jsonify([entry.to_dict() for entry in entries])


@app.route('/add-hours', methods=['POST'])
@login_required
def add_hours():
    """Add a new hours entry"""
    user_id = session['user_id']
    data = request.get_json()
    
    new_entry = HourEntry(
        user_id=user_id,
        work_hours=data['work_hours'],
        # study_hours=data['study_hours']
    )
    
    db.session.add(new_entry)
    db.session.commit()
    
    return jsonify(new_entry.to_dict())


@app.route('/update-hours/<int:entry_id>', methods=['PUT'])
@login_required
def update_hours(entry_id):
    """Update an hours entry"""
    user_id = session['user_id']
    entry = HourEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()
    
    data = request.get_json()
    entry.work_hours = data['work_hours']
    # entry.study_hours = data['study_hours']
    
    db.session.commit()
    
    return jsonify(entry.to_dict())


# @app.route('/delete-hours/<int:entry_id>', methods=['DELETE'])
# @login_required
# def delete_hours(entry_id):
#     """Delete an hours entry"""
#     user_id = session['user_id']
#     entry = HourEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()
    
#     db.session.delete(entry)
#     db.session.commit()
    
#     return jsonify({'message': 'Entry deleted', 'id': entry_id})



if __name__ == "__main__":
    app.run(debug=True)
