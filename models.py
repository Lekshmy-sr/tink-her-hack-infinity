from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    want = db.Column(db.Float, default=0.0)
    need = db.Column(db.Float, default=0.0)
    savings = db.Column(db.Float, default=0.0)
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    last_month_points = db.Column(db.Integer, default=0)
    last_month_level = db.Column(db.Integer, default=1)
    bills = db.relationship('Bill', backref='user', lazy=True)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, unique=True, nullable=False) # The incremented ID requested
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(20), nullable=False) # 'want', 'need', 'savings'
    date = db.Column(db.DateTime, default=datetime.utcnow)
    image_url = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
