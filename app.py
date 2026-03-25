from datetime import datetime
from functools import wraps
import json

import numpy as np
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tracker.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key-change-this-in-production"

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class DashboardWidget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    widget_type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="dashboard_widgets")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.widget_type,
            "title": self.title,
            "position": self.position,
        }


class RadarWidgetData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    widget_id = db.Column(
        db.Integer, db.ForeignKey("dashboard_widget.id"), unique=True, nullable=False
    )
    domains = db.Column(db.Text, nullable=False)
    scores = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    widget = db.relationship(
        "DashboardWidget",
        backref=db.backref("radar_data", uselist=False, cascade="all, delete-orphan"),
    )

    def get_domains(self):
        return json.loads(self.domains)

    def get_scores(self):
        return json.loads(self.scores)

    def set_domains(self, domain_list):
        self.domains = json.dumps(domain_list)

    def set_scores(self, score_list):
        self.scores = json.dumps(score_list)


class BarWidgetData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    widget_id = db.Column(
        db.Integer, db.ForeignKey("dashboard_widget.id"), unique=True, nullable=False
    )
    metric_name = db.Column(db.String(120), nullable=False)
    unit = db.Column(db.String(40), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    widget = db.relationship(
        "DashboardWidget",
        backref=db.backref("bar_data", uselist=False, cascade="all, delete-orphan"),
    )

    def to_dict(self):
        return {
            "metric_name": self.metric_name,
            "unit": self.unit or "",
        }


class BarEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    widget_id = db.Column(db.Integer, db.ForeignKey("dashboard_widget.id"), nullable=False)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=lambda: datetime.utcnow().date())
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    widget = db.relationship(
        "DashboardWidget",
        backref=db.backref("bar_entries", cascade="all, delete-orphan"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "date": self.date.strftime("%Y-%m-%d"),
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }


with app.app_context():
    db.create_all()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def sigmoid(x):
    return 1 / (1 + np.exp(-0.1 * x))


def normalize_domains(raw_domains):
    domains = [domain.strip() for domain in raw_domains if domain and domain.strip()]
    if len(domains) < 3:
        raise ValueError("Please enter at least three domains for a radar chart.")
    return domains


def serialize_radar_widget(widget):
    domains = widget.radar_data.get_domains()
    scores = widget.radar_data.get_scores()
    return {
        **widget.to_dict(),
        "config": {
            "domains": domains,
            "scores": scores,
        },
        "plot": {
            "theta": domains,
            "r": [100 * sigmoid(score) for score in scores],
        },
    }


def serialize_bar_widget(widget):
    entries = [entry.to_dict() for entry in sorted(widget.bar_entries, key=lambda item: (item.date, item.id))]
    return {
        **widget.to_dict(),
        "config": widget.bar_data.to_dict(),
        "entries": entries,
    }


def serialize_widget(widget):
    if widget.widget_type == "radar":
        return serialize_radar_widget(widget)
    if widget.widget_type == "bar":
        return serialize_bar_widget(widget)
    return widget.to_dict()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            return jsonify({"success": True, "message": "Login successful"})

        return jsonify({"success": False, "message": "Invalid username or password"}), 401

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400
        if len(password) < 4:
            return jsonify({"success": False, "message": "Password must be at least 4 characters"}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({"success": False, "message": "Username already taken"}), 400

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id
        session["username"] = new_user.username
        return jsonify({"success": True, "message": "Registration successful"})

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"))


@app.route("/dashboard-data")
@login_required
def dashboard_data():
    widgets = (
        DashboardWidget.query.filter_by(user_id=session["user_id"])
        .order_by(DashboardWidget.position, DashboardWidget.created_at)
        .all()
    )
    return jsonify({"widgets": [serialize_widget(widget) for widget in widgets]})


@app.route("/widgets", methods=["POST"])
@login_required
def create_widget():
    data = request.get_json() or {}
    widget_type = data.get("type")
    title = (data.get("title") or "").strip()
    insert_after_id = data.get("insert_after_id")
    user_id = session["user_id"]

    widgets = (
        DashboardWidget.query.filter_by(user_id=user_id)
        .order_by(DashboardWidget.position, DashboardWidget.created_at)
        .all()
    )

    position = len(widgets)
    if insert_after_id is not None:
        previous_widget = DashboardWidget.query.filter_by(id=insert_after_id, user_id=user_id).first()
        if not previous_widget:
            return jsonify({"error": "Reference widget not found"}), 404
        position = previous_widget.position + 1
        widgets_to_shift = (
            DashboardWidget.query.filter(
                DashboardWidget.user_id == user_id, DashboardWidget.position >= position
            ).all()
        )
        for widget in widgets_to_shift:
            widget.position += 1

    if widget_type == "radar":
        try:
            domains = normalize_domains(data.get("domains", []))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        widget = DashboardWidget(
            user_id=user_id,
            widget_type="radar",
            title=title or "Radar Chart",
            position=position,
        )
        db.session.add(widget)
        db.session.flush()

        radar_data = RadarWidgetData(widget_id=widget.id)
        radar_data.set_domains(domains)
        radar_data.set_scores([0.0] * len(domains))
        db.session.add(radar_data)

    elif widget_type == "bar":
        metric_name = (data.get("metric_name") or "").strip()
        unit = (data.get("unit") or "").strip()
        if not metric_name:
            return jsonify({"error": "Please enter the habit or metric name for the bar chart."}), 400

        widget = DashboardWidget(
            user_id=user_id,
            widget_type="bar",
            title=title or f"{metric_name} Tracker",
            position=position,
        )
        db.session.add(widget)
        db.session.flush()

        db.session.add(
            BarWidgetData(
                widget_id=widget.id,
                metric_name=metric_name,
                unit=unit or None,
            )
        )
    else:
        return jsonify({"error": "Unsupported widget type"}), 400

    db.session.commit()
    return jsonify({"widget": serialize_widget(widget)}), 201


@app.route("/widgets/<int:widget_id>/radar/update-score", methods=["POST"])
@login_required
def update_radar_score(widget_id):
    widget = DashboardWidget.query.filter_by(
        id=widget_id, user_id=session["user_id"], widget_type="radar"
    ).first_or_404()

    data = request.get_json() or {}
    index = data.get("index")
    change = data.get("change")
    scores = widget.radar_data.get_scores()
    domains = widget.radar_data.get_domains()

    if not isinstance(index, int) or index < 0 or index >= len(scores):
        return jsonify({"error": "Invalid domain index"}), 400
    if change not in (-1, 1):
        return jsonify({"error": "Invalid score change"}), 400

    scores[index] += change
    widget.radar_data.set_scores(scores)
    db.session.commit()

    return jsonify(
        {
            "theta": domains,
            "r": [100 * sigmoid(score) for score in scores],
            "scores": scores,
        }
    )


@app.route("/widgets/<int:widget_id>/bar/entries", methods=["POST"])
@login_required
def add_bar_entry(widget_id):
    widget = DashboardWidget.query.filter_by(
        id=widget_id, user_id=session["user_id"], widget_type="bar"
    ).first_or_404()

    data = request.get_json() or {}
    try:
        value = float(data.get("value"))
    except (TypeError, ValueError):
        return jsonify({"error": "Please enter a valid number."}), 400

    if value < 0:
        return jsonify({"error": "Please enter a positive number."}), 400

    db.session.add(BarEntry(widget_id=widget.id, value=value))
    db.session.commit()

    entries = BarEntry.query.filter_by(widget_id=widget.id).order_by(BarEntry.date, BarEntry.id).all()
    return jsonify({"entries": [entry.to_dict() for entry in entries]})


if __name__ == "__main__":
    app.run(debug=True)
