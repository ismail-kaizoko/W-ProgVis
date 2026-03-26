from datetime import date, datetime, timedelta
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


class RadarDailyAdjustment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    widget_id = db.Column(db.Integer, db.ForeignKey("dashboard_widget.id"), nullable=False)
    domain_index = db.Column(db.Integer, nullable=False)
    entry_date = db.Column(db.Date, nullable=False, default=date.today)
    delta = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    widget = db.relationship(
        "DashboardWidget",
        backref=db.backref("radar_daily_adjustments", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        db.UniqueConstraint("widget_id", "domain_index", "entry_date", name="uq_radar_daily_adjustment"),
    )


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
    date = db.Column(db.Date, default=date.today)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    widget = db.relationship(
        "DashboardWidget",
        backref=db.backref("bar_entries", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        db.UniqueConstraint("widget_id", "date", name="uq_bar_entry_widget_date"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "date": self.date.strftime("%Y-%m-%d"),
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }


class PieWidgetData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    widget_id = db.Column(
        db.Integer, db.ForeignKey("dashboard_widget.id"), unique=True, nullable=False
    )
    categories = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    widget = db.relationship(
        "DashboardWidget",
        backref=db.backref("pie_data", uselist=False, cascade="all, delete-orphan"),
    )

    def get_categories(self):
        return json.loads(self.categories)

    def set_categories(self, category_list):
        self.categories = json.dumps(category_list)

    def to_dict(self):
        return {
            "categories": self.get_categories(),
        }


class PieEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    widget_id = db.Column(db.Integer, db.ForeignKey("dashboard_widget.id"), nullable=False)
    category_index = db.Column(db.Integer, nullable=False)
    hours = db.Column(db.Float, nullable=False, default=0)
    entry_date = db.Column(db.Date, nullable=False, default=date.today)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    widget = db.relationship(
        "DashboardWidget",
        backref=db.backref("pie_entries", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        db.UniqueConstraint("widget_id", "category_index", "entry_date", name="uq_pie_entry_widget_category_date"),
    )

    def to_dict(self):
        return {
            "category_index": self.category_index,
            "hours": self.hours,
            "entry_date": self.entry_date.strftime("%Y-%m-%d"),
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


def current_day():
    return datetime.now().date()


def sigmoid(x):
    return 1 / (1 + np.exp(-0.1 * x))


def normalize_domains(raw_domains):
    domains = [domain.strip() for domain in raw_domains if domain and domain.strip()]
    if len(domains) < 3:
        raise ValueError("Please enter at least three domains for a radar chart.")
    return domains


def normalize_pie_categories(raw_categories):
    categories = [category.strip() for category in raw_categories if category and category.strip()]
    if not categories:
        raise ValueError("Please enter at least one activity for the pie chart.")

    normalized = []
    seen = set()
    for category in categories:
        lower_category = category.lower()
        if lower_category == "wasted":
            continue
        if lower_category in seen:
            continue
        seen.add(lower_category)
        normalized.append(category)

    if not normalized:
        raise ValueError('Please add at least one activity other than "Wasted".')

    return normalized


def build_bar_series(entries, days=30):
    today = current_day()
    value_map = {entry.date: entry.value for entry in entries}
    start_day = today - timedelta(days=days - 1)

    labels = []
    values = []
    for offset in range(days):
        point_date = start_day + timedelta(days=offset)
        labels.append(point_date.strftime("%m-%d"))
        values.append(value_map.get(point_date, 0))

    return {"labels": labels, "values": values}


def get_today_radar_adjustments(widget, domain_count):
    today = current_day()
    adjustments = (
        RadarDailyAdjustment.query.filter_by(widget_id=widget.id, entry_date=today)
        .order_by(RadarDailyAdjustment.domain_index)
        .all()
    )
    delta_map = {item.domain_index: item.delta for item in adjustments}
    return [delta_map.get(index, 0) for index in range(domain_count)]


def serialize_radar_widget(widget):
    domains = widget.radar_data.get_domains()
    scores = widget.radar_data.get_scores()
    daily_deltas = get_today_radar_adjustments(widget, len(domains))
    return {
        **widget.to_dict(),
        "config": {
            "domains": domains,
            "scores": scores,
            "today_deltas": daily_deltas,
        },
        "plot": {
            "theta": domains,
            "r": [100 * sigmoid(score) for score in scores],
        },
    }


def serialize_bar_widget(widget):
    entries = sorted(widget.bar_entries, key=lambda item: item.date)
    today_entry = next((entry for entry in entries if entry.date == current_day()), None)
    return {
        **widget.to_dict(),
        "config": widget.bar_data.to_dict(),
        "entries": [entry.to_dict() for entry in entries],
        "today_entry": today_entry.to_dict() if today_entry else None,
        "series": build_bar_series(entries),
    }


def get_today_pie_entries(widget, category_count):
    today = current_day()
    entries = (
        PieEntry.query.filter_by(widget_id=widget.id, entry_date=today)
        .order_by(PieEntry.category_index)
        .all()
    )
    entry_map = {item.category_index: item.hours for item in entries}
    return [entry_map.get(index, 0) for index in range(category_count)]


def build_pie_plot(values):
    total_tracked = sum(values)
    wasted_hours = max(0, 24 - total_tracked)
    base_colors = ["#FFA500", "#D90AE4", "#2196F3", "#FF5722", "#16A34A", "#E11D48"]
    category_colors = [base_colors[index % len(base_colors)] for index in range(len(values))]
    return {
        "values": values + [wasted_hours],
        "wasted_hours": wasted_hours,
        "total_tracked": total_tracked,
        "colors": category_colors + ["#363436"],
    }


def serialize_pie_widget(widget):
    categories = widget.pie_data.get_categories()
    today_values = get_today_pie_entries(widget, len(categories))
    plot = build_pie_plot(today_values)
    return {
        **widget.to_dict(),
        "config": widget.pie_data.to_dict(),
        "today_entries": today_values,
        "plot": {
            "labels": categories + ["Wasted"],
            "values": plot["values"],
            "colors": plot["colors"],
            "wasted_hours": plot["wasted_hours"],
            "total_tracked": plot["total_tracked"],
        },
    }


def serialize_widget(widget):
    if widget.widget_type == "radar":
        return serialize_radar_widget(widget)
    if widget.widget_type == "bar":
        return serialize_bar_widget(widget)
    if widget.widget_type == "pie":
        return serialize_pie_widget(widget)
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
    user_id = session["user_id"]

    position = DashboardWidget.query.filter_by(user_id=user_id).count()

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
    elif widget_type == "pie":
        try:
            categories = normalize_pie_categories(data.get("categories", []))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        widget = DashboardWidget(
            user_id=user_id,
            widget_type="pie",
            title=title or "Time Distribution",
            position=position,
        )
        db.session.add(widget)
        db.session.flush()

        pie_data = PieWidgetData(widget_id=widget.id)
        pie_data.set_categories(categories)
        db.session.add(pie_data)
    else:
        return jsonify({"error": "Unsupported widget type"}), 400

    db.session.commit()
    return jsonify({"widget": serialize_widget(widget)}), 201


@app.route("/widgets/<int:widget_id>", methods=["DELETE"])
@login_required
def delete_widget(widget_id):
    widget = DashboardWidget.query.filter_by(id=widget_id, user_id=session["user_id"]).first_or_404()
    deleted_position = widget.position
    user_id = widget.user_id

    db.session.delete(widget)

    widgets_to_shift = (
        DashboardWidget.query.filter(
            DashboardWidget.user_id == user_id,
            DashboardWidget.position > deleted_position,
        )
        .order_by(DashboardWidget.position)
        .all()
    )
    for item in widgets_to_shift:
        item.position -= 1

    db.session.commit()
    return jsonify({"success": True})


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

    today = current_day()
    adjustment = RadarDailyAdjustment.query.filter_by(
        widget_id=widget.id,
        domain_index=index,
        entry_date=today,
    ).first()

    if not adjustment:
        adjustment = RadarDailyAdjustment(
            widget_id=widget.id,
            domain_index=index,
            entry_date=today,
            delta=0,
        )
        db.session.add(adjustment)

    new_delta = adjustment.delta + change
    if new_delta < -1 or new_delta > 1:
        return jsonify({"error": "For each domain, today's net change must stay between -1 and +1."}), 400

    adjustment.delta = new_delta
    scores[index] += change
    widget.radar_data.set_scores(scores)

    if adjustment.delta == 0:
        if adjustment in db.session.new:
            db.session.expunge(adjustment)
        else:
            db.session.delete(adjustment)

    db.session.commit()

    return jsonify(
        {
            "theta": domains,
            "r": [100 * sigmoid(score) for score in scores],
            "scores": scores,
            "today_deltas": get_today_radar_adjustments(widget, len(domains)),
        }
    )


@app.route("/widgets/<int:widget_id>/bar/entry", methods=["POST"])
@login_required
def create_bar_entry(widget_id):
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

    today = current_day()
    existing_entry = BarEntry.query.filter_by(widget_id=widget.id, date=today).first()
    if existing_entry:
        return jsonify({"error": "Today's bar already exists. Update or delete it instead."}), 400

    db.session.add(BarEntry(widget_id=widget.id, value=value, date=today))
    db.session.commit()
    return jsonify({"widget": serialize_bar_widget(widget)})


@app.route("/widgets/<int:widget_id>/bar/entry", methods=["PUT"])
@login_required
def update_bar_entry(widget_id):
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

    today = current_day()
    existing_entry = BarEntry.query.filter_by(widget_id=widget.id, date=today).first()
    if not existing_entry:
        return jsonify({"error": "No bar has been entered for today yet."}), 404

    existing_entry.value = value
    existing_entry.timestamp = datetime.utcnow()
    db.session.commit()
    return jsonify({"widget": serialize_bar_widget(widget)})


@app.route("/widgets/<int:widget_id>/bar/entry", methods=["DELETE"])
@login_required
def delete_bar_entry(widget_id):
    widget = DashboardWidget.query.filter_by(
        id=widget_id, user_id=session["user_id"], widget_type="bar"
    ).first_or_404()

    today = current_day()
    existing_entry = BarEntry.query.filter_by(widget_id=widget.id, date=today).first()
    if not existing_entry:
        return jsonify({"error": "No bar has been entered for today yet."}), 404

    db.session.delete(existing_entry)
    db.session.commit()
    return jsonify({"widget": serialize_bar_widget(widget)})


@app.route("/widgets/<int:widget_id>/pie/entry", methods=["PUT"])
@login_required
def update_pie_entry(widget_id):
    widget = DashboardWidget.query.filter_by(
        id=widget_id, user_id=session["user_id"], widget_type="pie"
    ).first_or_404()

    data = request.get_json() or {}
    raw_hours = data.get("hours")
    categories = widget.pie_data.get_categories()

    if not isinstance(raw_hours, list) or len(raw_hours) != len(categories):
        return jsonify({"error": "Please provide one hour value for each activity."}), 400

    parsed_hours = []
    for value in raw_hours:
        try:
            parsed_value = float(value)
        except (TypeError, ValueError):
            return jsonify({"error": "Please enter valid hour values."}), 400

        if parsed_value < 0:
            return jsonify({"error": "Hours cannot be negative."}), 400

        parsed_hours.append(round(parsed_value, 2))

    if sum(parsed_hours) > 24:
        return jsonify({"error": "Tracked hours cannot exceed 24 for the current day."}), 400

    today = current_day()
    existing_entries = PieEntry.query.filter_by(widget_id=widget.id, entry_date=today).all()
    existing_by_index = {entry.category_index: entry for entry in existing_entries}

    for index, hours in enumerate(parsed_hours):
        existing_entry = existing_by_index.get(index)
        if hours == 0:
            if existing_entry:
                db.session.delete(existing_entry)
            continue

        if existing_entry:
            existing_entry.hours = hours
        else:
            db.session.add(
                PieEntry(
                    widget_id=widget.id,
                    category_index=index,
                    hours=hours,
                    entry_date=today,
                )
            )

    db.session.commit()
    return jsonify({"widget": serialize_pie_widget(widget)})


if __name__ == "__main__":
    app.run(debug=True)
