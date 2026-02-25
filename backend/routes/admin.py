#newshub/backend/routes/admin.py             # Verification dashboard
"""
NewsHub Admin Verification Dashboard
- Pending video review queue
- 1-5 star quality rating
- Category tagging (protest/accident/etc)
- Approve/Reject with reasons
- Uploader notifications
- Analytics dashboard
"""

from flask import Blueprint, request, jsonify
from models import db, Video, User, VideoStatus, Role
from utils.payments import payments
from datetime import datetime
import logging

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

# JWT Admin auth middleware
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            return jsonify({"error": "Admin auth required"}), 401
        
        token = auth.split(' ')[1]
        # Verify admin JWT (mock)
        if token != 'admin-jwt-token-secure-change-me':
            return jsonify({"error": "Invalid admin token"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/videos/pending', methods=['GET'])
def pending_videos():
    """Admin dashboard - Videos awaiting verification"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        # Filter options
        location = request.args.get('location')
        min_price = request.args.get('min_price')
        
        # Mock → Real Prisma: Video.findMany({where: {status: 'PENDING'}})
        pending_videos = [
            {
                "id": "video-001",
                "uploader_id": "uploader-001",
                "uploader_email": "citizen@journalist.in",
                "title": "Bengaluru MG Road Protest Raw Footage",
                "thumbnail_url": "https://newshub-videos.s3.ap-south-1.amazonaws.com/thumbnails/video-001_thumb.jpg",
                "video_url": "https://newshub-videos.s3.ap-south-1.amazonaws.com/videos/video-001.mp4",
                "duration": "2m 47s",
                "location": "MG Road, Bengaluru",
                "gps": {"lat": 12.975, "lng": 77.605},
                "price": 15000,
                "uploaded_at": "2026-02-25T14:22:00Z",
                "uploader_verified": True
            },
            {
                "id": "video-002",
                "title": "Indiranagar Traffic Accident",
                "thumbnail_url": "https://newshub-videos.s3.ap-south-1.amazonaws.com/thumbnails/video-002_thumb.jpg",
                "location": "Indiranagar, Bengaluru", 
                "price": 12000,
                "uploaded_at": "2026-02-25T15:10:00Z"
            }
        ]
        
        # Apply filters
        filtered = pending_videos
        if location:
            filtered = [v for v in filtered if location.lower() in v['location'].lower()]
        
        return jsonify({
            "videos": filtered[offset:offset+limit],
            "total_pending": len(filtered),
            "page": page,
            "limit": limit,
            "avg_price": sum(v['price'] for v in filtered) / len(filtered) if filtered else 0,
            "hours_pending": 36  # SLA target
        })
        
    except Exception as e:
        logger.error(f"Pending videos error: {e}")
        return jsonify({"error": "Failed to fetch pending videos"}), 500

@admin_bp.route('/videos/<video_id>/verify', methods=['POST'])
@admin_required
def verify_video(video_id):
    """Admin rates/approves/rejects video"""
    try:
        data = request.get_json()
        rating = int(data.get('rating', 0))  # 1-5 stars
        categories = data.get('categories', [])  # ['protest', 'breaking']
        approved = data.get('approved', True)
        rejection_reason = data.get('rejection_reason', '')
        admin_id = "admin-001"  # From JWT
        
        if rating < 1 or rating > 5:
            return jsonify({"error": "Rating must be 1-5"}), 400
        
        # Fetch video
        video = db.get_video_by_id(video_id)
        if not video:
            return jsonify({"error": "Video not found"}), 404
        
        if video.status != VideoStatus.PENDING:
            return jsonify({"error": "Video already processed"}), 400
        
        # Decision logic
        if approved and rating >= 3:
            new_status = VideoStatus.APPROVED
        else:
            new_status = VideoStatus.REJECTED
        
        # Update video record
        updated_video = db.admin_verify_video(
            video_id=video_id,
            rating=rating,
            categories=categories,
            approved=(new_status == VideoStatus.APPROVED)
        )
        
        # Notify uploader
        notify_uploader(video.uploader_id, video_id, new_status, rating, rejection_reason)
        
        # Analytics
        logger.info(f"Admin verified {video_id}: {new_status} ⭐{rating}")
        
        return jsonify({
            "success": True,
            "video_id": video_id,
            "new_status": new_status.value,
            "rating": rating,
            "categories": categories,
            "admin_id": admin_id,
            "estimated_revenue": payments.calculate_royalty_split(video.price)['total'],
            "message": "Video processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Verify video error: {e}")
        return jsonify({"error": "Verification failed"}), 500

@admin_bp.route('/videos/<video_id>/reject', methods=['POST'])
@admin_required
def reject_video(video_id):
    """Quick reject with reason"""
    try:
        data = request.get_json()
        reason = data.get('reason', 'quality_issue')
        rating = 1  # Auto low rating
        
        reject_reasons = {
            'nudity': 'Graphic nudity detected (IT Rules 2021)',
            'quality_issue': 'Poor video/audio quality',
            'irrelevant': 'Not news-worthy content',
            'duplicate': 'Duplicate footage'
        }
        
        result = verify_video(video_id, {
            'rating': rating,
            'approved': False,
            'rejection_reason': reject_reasons.get(reason, 'unspecified')
        })
        
        return result
        
    except Exception as e:
        return jsonify({"error": "Reject failed"}), 500

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def admin_stats():
    """Admin dashboard analytics"""
    try:
        # Mock stats → Real database aggregates
        stats = {
            "pending_videos": 127,
            "approved_today": 34,
            "rejected_today": 8,
            "total_revenue": 2450000,  # ₹24.5L
            "avg_rating": 3.8,
            "top_categories": {
                "protest": 45,
                "accident": 28,
                "breaking": 67
            },
            "top_uploaders": [
                {"id": "uploader-001", "videos": 12, "revenue": 180000},
                {"id": "uploader-002", "videos": 8, "revenue": 120000}
            ],
            "sla_violations": 2,  # >48hr pending
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        return jsonify({"error": "Stats unavailable"}), 500

@admin_bp.route('/categories', methods=['GET'])
def get_categories():
    """Available categories for tagging"""
    categories = {
        "news": ["protest", "politics", "crime", "breaking"],
        "accidents": ["accident", "traffic", "fire", "crash"],
        "locations": ["bengaluru", "mumbai", "delhi", "chennai"],
        "quality": ["raw", "professional", "drone", "live"]
    }
    return jsonify(categories)

def notify_uploader(uploader_id: str, video_id: str, status: str, rating: int, reason: str = ''):
    """Email/SMS notification to uploader"""
    message = f"Your video {video_id} has been {status}"
    if status == VideoStatus.APPROVED:
        message += f" with {rating}/5 stars! Estimated payout: ₹9,000"
    elif reason:
        message += f". Reason: {reason}"
    
    # SendGrid/Twilio in production
    logger.info(f"📧 Notifying {uploader_id}: {message}")

# Register blueprint
def init_admin_routes(app):
    """Register admin routes"""
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

if __name__ == "__main__":
    print("NewsHub Admin Module Ready")
