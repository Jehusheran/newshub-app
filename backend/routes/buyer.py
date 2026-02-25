#buyer.py             # Stripe purchases
#newshub/backend/routes/buyer.py
"""
NewsHub Buyer Routes - Media Buyers Dashboard
- Browse approved videos
- Stripe checkout + 60/40 splits  
- DRM license download
- Public feed posting (30sec clips)
"""

from flask import Blueprint, request, jsonify, current_app
from models import db, Video, User, Role, VideoStatus
from utils.payments import create_video_checkout, handle_stripe_webhook
from utils.moderation import moderator
from datetime import datetime, timedelta
import stripe
import os
import jwt
import logging

buyer_bp = Blueprint('buyer', __name__)
logger = logging.getLogger(__name__)

# JWT secret (move to .env in production)
JWT_SECRET = os.getenv("JWT_SECRET", "news-hub-super-secret-key-change-me")

@buyer_bp.route('/videos/approved', methods=['GET'])
def get_approved_videos():
    """Media buyers browse admin-approved videos"""
    try:
        # Filters
        category = request.args.get('category')
        location = request.args.get('location')
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        # Mock data → Replace with real Prisma query
        videos = [
            Video({
                'id': 'video-001',
                'title': 'Bengaluru Protest Live Footage',
                'thumbnailUrl': 'https://newshub.in/static/protest-thumb.jpg',
                'videoUrl': 'https://s3.newshub.in/videos/video-001.mp4',
                'location': 'Bengaluru',
                'gps': {'lat': 12.9716, 'lng': 77.5946},
                'rating': 4,
                'categories': ['protest', 'breaking'],
                'status': VideoStatus.APPROVED,
                'price': 15000,
                'verifiedBy': 'admin-001',
                'verifiedAt': '2026-02-25T12:00:00Z'
            }),
            Video({
                'id': 'video-002',
                'title': 'Mumbai Accident Raw Footage',
                'thumbnailUrl': 'https://newshub.in/static/accident-thumb.jpg',
                'location': 'Mumbai',
                'rating': 3,
                'categories': ['accident', 'traffic'],
                'status': VideoStatus.APPROVED,
                'price': 12000
            })
        ]
        
        # Apply filters (mock filtering)
        filtered_videos = videos
        
        return jsonify({
            "videos": [v.__dict__ for v in filtered_videos[offset:offset+limit]],
            "total": len(filtered_videos),
            "page": page,
            "limit": limit,
            "has_more": offset + limit < len(filtered_videos)
        })
        
    except Exception as e:
        logger.error(f"Buyer videos error: {e}")
        return jsonify({"error": "Failed to fetch videos"}), 500

@buyer_bp.route('/buy/<video_id>', methods=['POST'])
def buy_video(video_id):
    """Create Stripe checkout session for video purchase"""
    try:
        data = request.get_json()
        buyer_email = data.get('buyer_email')
        buyer_id = data.get('buyer_id')  # From JWT
        
        if not buyer_email:
            return jsonify({"error": "Buyer email required"}), 400
        
        # Verify video exists and is approved
        video = get_video_by_id(video_id)
        if not video or video.status != VideoStatus.APPROVED:
            return jsonify({"error": "Video not available for purchase"}), 404
        
        # Create Stripe checkout
        checkout = create_video_checkout(
            video_id=video_id,
            buyer_email=buyer_email,
            price_tier="premium"
        )
        
        logger.info(f"Buyer checkout created: {video_id} -> {buyer_email}")
        
        return jsonify({
            "success": True,
            "checkout_url": checkout['url'],
            "session_id": checkout['session_id'],
            "video_title": video.title,
            "price": checkout['price']
        })
        
    except Exception as e:
        logger.error(f"Buy video error: {e}")
        return jsonify({"error": "Payment initiation failed"}), 500

@buyer_bp.route('/purchases', methods=['GET'])
def get_purchases():
    """Buyer's purchase history + license status"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authentication required"}), 401
        
        # Decode JWT (mock)
        buyer_id = "buyer-001"  # From JWT payload
        
        # Mock purchases → Replace with real DB query
        purchases = [
            {
                "id": "purchase-001",
                "video_id": "video-001",
                "video_title": "Bengaluru Protest Live Footage",
                "amount": 15000,
                "purchase_date": "2026-02-25T13:00:00Z",
                "expiry_date": "2026-05-26T13:00:00Z",  # 90 days
                "status": "active",
                "license_url": f"https://s3.newshub.in/licenses/purchase-001?token=abc123"
            }
        ]
        
        return jsonify({
            "purchases": purchases,
            "total_purchases": len(purchases),
            "total_spent": 15000
        })
        
    except Exception as e:
        logger.error(f"Get purchases error: {e}")
        return jsonify({"error": "Failed to fetch purchases"}), 500

@buyer_bp.route('/purchases/<purchase_id>/download', methods=['GET'])
def download_license(purchase_id):
    """DRM-protected video download (90-day expiry)"""
    try:
        auth_header = request.headers.get('Authorization')
        buyer_id = "buyer-001"  # From JWT
        
        # Verify purchase ownership + expiry
        purchase = get_purchase_by_id(purchase_id)
        if not purchase or purchase['buyer_id'] != buyer_id:
            return jsonify({"error": "Unauthorized"}), 403
        
        expiry = datetime.fromisoformat(purchase['expiry_date'].replace('Z', '+00:00'))
        if datetime.now(expiry.tzinfo) > expiry:
            return jsonify({"error": "License expired"}), 403
        
        # Generate signed S3 URL (mock)
        license_url = f"https://s3.newshub.in/licenses/{purchase_id}?token={purchase_id}&expires=90days"
        
        return jsonify({
            "success": True,
            "download_url": license_url,
            "expires": purchase['expiry_date'],
            "watermark": f"Licensed to {purchase['buyer_email']}"
        })
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"error": "Download failed"}), 500

@buyer_bp.route('/public-posts', methods=['POST'])
def create_public_post():
    """Channel posts 30sec highlight to public feed"""
    try:
        data = request.get_json()
        video_id = data.get('video_id')
        channel_id = data.get('channel_id')
        clip_start = data.get('clip_start', 30)  # seconds
        
        # Verify buyer owns video
        purchase = get_purchase_by_video(video_id, channel_id)
        if not purchase:
            return jsonify({"error": "Must purchase video first"}), 403
        
        # Generate 30sec clip URL (FFmpeg in production)
        clip_url = f"https://s3.newshub.in/clips/{video_id}_highlight_{clip_start}.mp4"
        
        # Create public post record
        public_post = {
            "id": f"post-{hash(video_id + channel_id)}",
            "video_id": video_id,
            "channel_id": channel_id,
            "clip_url": clip_url,
            "views": 0,
            "ad_revenue": 0,
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"Public post created: {public_post['id']}")
        
        return jsonify({
            "success": True,
            "post_id": public_post['id'],
            "clip_url": clip_url,
            "message": "30sec highlight posted to public feed"
        })
        
    except Exception as e:
        logger.error(f"Public post error: {e}")
        return jsonify({"error": "Failed to create public post"}), 500

# Mock data helpers (replace with real DB queries)
def get_video_by_id(video_id: str) -> Video:
    """Mock video lookup"""
    if video_id == "video-001":
        return Video({
            'id': video_id,
            'title': 'Bengaluru Protest Live Footage',
            'status': VideoStatus.APPROVED,
            'price': 15000
        })
    return None

def get_purchase_by_id(purchase_id: str) -> dict:
    """Mock purchase lookup"""
    if purchase_id == "purchase-001":
        return {
            "id": purchase_id,
            "buyer_id": "buyer-001",
            "buyer_email": "buyer@channel.in",
            "expiry_date": "2026-05-26T13:00:00Z"
        }
    return None

def get_purchase_by_video(video_id: str, buyer_id: str) -> dict:
    """Verify purchase ownership"""
    return {"id": "purchase-001"} if video_id == "video-001" else None

def authenticate_buyer(token: str) -> Optional[str]:
    """JWT authentication"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload.get('user_id')
    except:
        return None

# Register blueprint
def init_buyer_routes(app):
    """Register routes with main app"""
    app.register_blueprint(buyer_bp, url_prefix='/api/buyer')
