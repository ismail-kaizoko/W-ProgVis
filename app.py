from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps



app = Flask(__name__)

# ====== APP STATE (simple version) ======
domains = None
scores = None


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


class DataEntry(db.Model):
    """Data table - now linked to users"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    value1 = db.Column(db.Float, nullable=False)
    value2 = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to User
    user = db.relationship('User', backref='entries')
    
    def to_dict(self):
        return {
            'id': self.id,
            'value1': self.value1,
            'value2': self.value2,
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



# ============================================
# PROTECTED ROUTES (require login)
# ============================================

@app.route("/")
@login_required
def index():
    """Main app - only accessible if logged in"""
    return render_template('index.html', username=session.get('username'))


@app.route("/status")
def status():
    """Tell frontend whether domains are already initialized"""
    return jsonify({"initialized": domains is not None})


@app.route("/init", methods=["POST"])
def init():
    global domains, scores

    data = request.get_json()
    domains = data["domains"]
    scores = [0.0] * len(domains)

    return jsonify(get_graph_data())


# @app.route("/get-data")
# def get_data():
#     if domains is None:
#         return jsonify({"error": "Not initialized"}), 400
#     return jsonify(get_graph_data())


@app.route('/get-data')
@login_required
def get_data():
    """Get only the current user's data"""
    user_id = session['user_id']
    entries = DataEntry.query.filter_by(user_id=user_id).all()
    return jsonify([entry.to_dict() for entry in entries])


@app.route('/add-entry', methods=['POST'])
@login_required
def add_entry():
    """Add entry for current user"""
    data = request.get_json()
    user_id = session['user_id']
    
    new_entry = DataEntry(
        user_id=user_id,
        value1=data['value1'],
        value2=data['value2']
    )
    
    db.session.add(new_entry)
    db.session.commit()
    
    return jsonify(new_entry.to_dict())



@app.route("/update-score", methods=["POST"])
def update_score():
    global scores

    data = request.get_json()
    index = data["index"]
    change = data["change"]

    scores[index] += change

    return jsonify(get_graph_data())


if __name__ == "__main__":
    app.run(debug=True)
