#newshub/backend/routes/upload.py            # Video upload + S3
"""
NewsHub Video Upload Routes
- Multi-file upload (video + thumbnail)
- GPS metadata extraction
- AI moderation (nudity rejection)
- AWS S3 storage (Bengaluru region)
- Database record creation
- Pending → Admin verification
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import boto3
import json
from models import db, Video, User, VideoStatus, Role
from utils.moderation import moderator
from utils.payments import payments
from datetime import datetime
import uuid
import logging
import exifread  # GPS metadata

upload_bp = Blueprint('upload', __name__)
logger = logging.getLogger(__name__)

# AWS S3 Configuration
S3_BUCKET = os.getenv("AWS_S3_BUCKET", "newshub-videos-blr")
S3_REGION = "ap-south-1"  # Mumbai (closest to Bengaluru)
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=S3_REGION
)

# Allowed file types
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@upload_bp.route('/videos', methods=['POST'])
def upload_video():
    """Complete video upload pipeline"""
    try:
        # Check file presence
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({"error": "No video selected"}), 400
        
        if not allowed_file(video_file.filename):
            return jsonify({"error": "Invalid video format. Use MP4/MOV"}), 400
        
        # Form data
        uploader_id = request.form.get('uploader_id', 'guest-001')
        title = request.form.get('title', 'Untitled Footage')
        price = float(request.form.get('price', 15000))
        location = request.form.get('location', 'Unknown')
        description = request.form.get('description', '')
        
        # Generate secure filenames
        video_uuid = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"videos/{video_uuid}_{timestamp}_{secure_filename(video_file.filename)}"
        thumbnail_filename = f"thumbnails/{video_uuid}_{timestamp}.jpg"
        
        # Temporary local save
        temp_video = f"/tmp/{video_uuid}_video.mp4"
        temp_thumbnail = f"/tmp/{video_uuid}_thumb.jpg"
        video_file.save(temp_video)
        
        # Generate thumbnail if not provided
        thumbnail_file = request.files.get('thumbnail')
        if thumbnail_file and allowed_file(thumbnail_file.filename):
            thumbnail_file.save(temp_thumbnail)
        else:
            generate_thumbnail(temp_video, temp_thumbnail)
        
        # GPS extraction (from video metadata)
        gps_data = extract_gps_metadata(temp_video)
        
        # AI Moderation (critical gate)
        logger.info(f"🔍 Moderating video: {video_uuid}")
        moderation_result = moderator.analyze_video(temp_video)
        
        if not moderation_result['approved']:
            cleanup_temp_files([temp_video, temp_thumbnail])
            return jsonify({
                "error": "Content rejected by AI moderation",
                "reason": moderation_result['reason'],
                "max_nudity_score": moderation_result['max_nudity_score']
            }), 400
        
        # Upload to S3 (parallel)
        logger.info(f"📤 Uploading to S3: {video_uuid}")
        s3_tasks = [
            upload_to_s3(temp_video, f"{S3_BUCKET}/{video_filename}"),
            upload_to_s3(temp_thumbnail, f"{S3_BUCKET}/{thumbnail_filename}")
        ]
        
        # Wait for uploads
        video_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{video_filename}"
        thumbnail_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{thumbnail_filename}"
        
        # Create database record (PENDING status)
        video_record = db.create_video(
            uploader_id=uploader_id,
            title=title,
            price=price,
            location=location,
            gps=gps_data,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            categories=parse_categories(request.form.get('categories', ''))
        )
        
        # Cleanup
        cleanup_temp_files([temp_video, temp_thumbnail])
        
        logger.info(f"✅ Video uploaded: {video_record.id}")
        
        return jsonify({
            "success": True,
            "video_id": video_record.id,
            "status": "PENDING",
            "moderation": moderation_result,
            "s3_urls": {
                "video": video_url,
                "thumbnail": thumbnail_url
            },
            "estimated_payout": payments.calculate_royalty_split(price)['uploader_share'],
            "next_step": "Awaiting admin verification (24-48hr)"
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        cleanup_temp_files([temp_video, temp_thumbnail] if 'temp_video' in locals() else [])
        return jsonify({"error": "Upload failed", "details": str(e)}), 500

@upload_bp.route('/videos/<video_id>', methods=['GET'])
def get_upload_status(video_id):
    """Check video verification status"""
    try:
        video = db.get_video_by_id(video_id)  # Mock → Real Prisma
        if not video:
            return jsonify({"error": "Video not found"}), 404
        
        return jsonify({
            "video_id": video.id,
            "status": video.status,
            "rating": video.rating,
            "verified_by": video.verified_by,
            "categories": video.categories,
            "earnings_estimate": payments.calculate_royalty_split(video.price)['uploader_share']
        })
    except Exception as e:
        return jsonify({"error": "Status check failed"}), 500

def generate_thumbnail(video_path: str, output_path: str):
    """Generate thumbnail at 1-second mark"""
    import cv2
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, 1000)  # 1st second
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(output_path, frame)
    cap.release()

def extract_gps_metadata(video_path: str) -> dict:
    """Extract GPS from video EXIF metadata"""
    try:
        with open(video_path, 'rb') as f:
            tags = exifread.process_file(f)
        gps = {}
        if 'GPS GPSLatitude' in tags:
            gps['lat'] = float(tags['GPS GPSLatitude'].values[0])
        if 'GPS GPSLongitude' in tags:
            gps['lng'] = float(tags['GPS GPSLongitude'].values[0])
        return gps
    except:
        # Default Bengaluru coordinates
        return {"lat": 12.9716, "lng": 77.5946}

def upload_to_s3(local_path: str, s3_key: str):
    """Upload file to S3 with public-read ACL"""
    s3_client.upload_file(
        local_path, S3_BUCKET, s3_key,
        ExtraArgs={'ACL': 'public-read', 'ContentType': 'video/mp4'}
    )

def parse_categories(categories_str: str) -> list:
    """Parse comma-separated categories"""
    if not categories_str:
        return ['general']
    return [c.strip() for c in categories_str.split(',')]

def cleanup_temp_files(file_paths: list):
    """Remove temporary files"""
    for path in file_paths:
        try:
            os.unlink(path)
        except:
            pass

# Register blueprint
def init_upload_routes(app):
    """Register upload routes"""
    app.register_blueprint(upload_bp, url_prefix='/api/upload')

if __name__ == "__main__":
    print("NewsHub Upload Module Ready")
