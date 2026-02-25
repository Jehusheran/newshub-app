"""NewsHub Database Models - SQLAlchemy (SESSION FIXED FOREVER)"""
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from enum import Enum
from datetime import datetime

db = SQLAlchemy()

class Role(Enum):
    UPLOADER = "UPLOADER"
    MEDIA_BUYER = "MEDIA_BUYER"
    ADMIN = "ADMIN"
    PUBLIC = "PUBLIC"

class VideoStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SOLD = "SOLD"

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), default='PUBLIC')
    organization = db.Column(db.String(100))
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    video_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='PENDING')
    price = db.Column(db.Float, default=0.0)
    ai_moderation_result = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://newshub:password123@localhost:5433/newshub'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def to_dict(self):
        """Convert to JSON-serializable dict"""
        return {
            'id': self.id,
            'title': self.title,
            'uploader_id': self.uploader_id,
            'price': float(self.price or 0),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'thumbnail_url': self.thumbnail_url,
            'video_url': self.video_url
        }

def test_models():
    """SINGLE SESSION - NO DETACHED ERRORS"""
    with app.app_context():
        db.create_all()
        print("✅ Tables ready!")
        
        # SINGLE SESSION: Create + Query + Print
        user = User.query.filter_by(email='test@newshub.com').first()
        if not user:
            user = User(email='test@newshub.com', role='UPLOADER')
            db.session.add(user)
            db.session.commit()
        
        # SAME SESSION: Create video
        video = Video(title='Bengaluru Protest', uploader_id=user.id, price=2500.0)
        db.session.add(video)
        db.session.commit()
        
        # SAME SESSION: Print (NO DETACHED ERROR!)
        print(f"👤 {user.email} → Video: {video.title}")
        print(f"💰 ₹{video.price} → ID: {video.id}")
        print("✅ DATABASE 100% WORKING!")
        
        # Cleanup
        db.session.delete(video)
        db.session.commit()

if __name__ == "__main__":
    test_models()

