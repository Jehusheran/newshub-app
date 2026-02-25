#newshub/backend/routes/feed.py              # Public news feed
"""
NewsHub Public Feed Routes
- 30sec channel highlight clips
- Infinite scroll + viral sharing
- Ad pre-rolls (₹20 CPM)
- Trending + location-based
- Bengaluru-first optimization
"""

from flask import Blueprint, request, jsonify
from models import PublicPost, Video, User
from datetime import datetime, timedelta
import random
import logging

feed_bp = Blueprint('feed', __name__)
logger = logging.getLogger(__name__)

# Mock data → Real Prisma queries in production
SAMPLE_POSTS = [
    {
        "id": "post-001",
        "video_id": "video-001",
        "channel_id": "channel-etv",
        "channel_name": "ETV News Bengaluru",
        "clip_url": "https://newshub.in/clips/bengaluru-protest-30s.mp4",
        "thumbnail": "https://newshub.in/thumbs/protest-thumb.jpg",
        "title": "Bengaluru Protest Escalates - Live Raw Footage",
        "location": "MG Road, Bengaluru",
        "categories": ["protest", "breaking", "bengaluru"],
        "views": 12543,
        "likes": 2847,
        "ad_revenue": 250.86,  # ₹20 CPM
        "created_at": "2026-02-25T14:30:00Z",
        "ad_url": "https://ads.newshub.in/pre-roll-001.mp4"
    },
    {
        "id": "post-002", 
        "video_id": "video-002",
        "channel_id": "channel-tv9",
        "channel_name": "TV9 Kannada",
        "clip_url": "https://newshub.in/clips/mumbai-accident-30s.mp4",
        "thumbnail": "https://newshub.in/thumbs/accident-thumb.jpg",
        "title": "Mumbai Highway Pileup - Citizen Footage",
        "location": "Western Express Highway",
        "categories": ["accident", "traffic"],
        "views": 8923,
        "likes": 1567,
        "ad_revenue": 178.46,
        "created_at": "2026-02-24T19:15:00Z",
        "ad_url": "https://ads.newshub.in/pre-roll-002.mp4"
    }
]

@feed_bp.route('/public-feed', methods=['GET'])
def public_feed():
    """Infinite scroll public news feed"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit
        
        # Location-based (Bengaluru priority)
        location = request.args.get('location', 'bengaluru')
        category = request.args.get('category')
        
        # Trending algorithm: views * 0.6 + likes * 0.3 + fresh * 0.1
        trending_posts = sorted(
            SAMPLE_POSTS,
            key=lambda p: (
                p['views'] * 0.6 + 
                p['likes'] * 0.3 + 
                (1 / (datetime.now().timestamp() - 
                      datetime.fromisoformat(p['created_at'].replace('Z','+00:00')).timestamp()) + 1) * 0.1
            ),
            reverse=True
        )
        
        # Filter by location/category
        filtered_posts = trending_posts
        if location and location.lower() != 'all':
            filtered_posts = [p for p in filtered_posts if location.lower() in p['location'].lower()]
        if category:
            filtered_posts = [p for p in filtered_posts if category.lower() in p['categories']]
        
        paginated = filtered_posts[offset:offset + limit]
        
        return jsonify({
            "posts": paginated,
            "page": page,
            "limit": limit,
            "total": len(filtered_posts),
            "has_more": offset + limit < len(filtered_posts),
            "trending_categories": get_trending_categories(filtered_posts),
            "location_suggestions": ["bengaluru", "mumbai", "delhi", "chennai"]
        })
        
    except Exception as e:
        logger.error(f"Public feed error: {e}")
        return jsonify({"error": "Failed to load feed"}), 500

@feed_bp.route('/public-feed/trending', methods=['GET'])
def trending_feed():
    """Top trending clips (last 24hr)"""
    try:
        hours = int(request.args.get('hours', 24))
        
        # Mock trending → Real Redis sorted set in production
        trending = sorted(SAMPLE_POSTS, key=lambda p: p['views'], reverse=True)[:20]
        
        return jsonify({
            "trending": trending,
            "time_window": f"{hours}hr",
            "total_views": sum(p['views'] for p in trending),
            "ad_revenue_today": 429.32  # ₹20 CPM aggregate
        })
    except Exception as e:
        logger.error(f"Trending error: {e}")
        return jsonify({"error": "Failed to load trending"}), 500

@feed_bp.route('/public-feed/<post_id>/view', methods=['POST'])
def record_view(post_id):
    """Track video views + ad impressions"""
    try:
        data = request.get_json()
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        device = data.get('device', 'unknown')
        
        # Update view count (Redis incr in production)
        post = next((p for p in SAMPLE_POSTS if p['id'] == post_id), None)
        if post:
            post['views'] += 1
        
        # Log ad impression
        logger.info(f"📺 View recorded: {post_id} from {user_ip} ({device})")
        
        return jsonify({
            "success": True,
            "post_id": post_id,
            "new_views": post['views'] if post else 0,
            "ad_impressions": 1
        })
    except Exception as e:
        logger.error(f"View tracking error: {e}")
        return jsonify({"error": "Failed to record view"}), 500

@feed_bp.route('/public-feed/search', methods=['GET'])
def search_feed():
    """Search clips by title/location"""
    try:
        query = request.args.get('q', '').lower()
        page = int(request.args.get('page', 1))
        
        if len(query) < 2:
            return jsonify({"error": "Query too short"}), 400
        
        # Mock search → Elasticsearch in production
        results = [
            p for p in SAMPLE_POSTS 
            if query in p['title'].lower() or query in p['location'].lower()
        ]
        
        return jsonify({
            "results": results,
            "query": query,
            "total": len(results),
            "took": 23  # ms
        })
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": "Search failed"}), 500

@feed_bp.route('/public-feed/categories', methods=['GET'])
def categories_feed():
    """Popular categories for filtering"""
    categories = {
        "trending": ["protest", "accident", "breaking", "bengaluru"],
        "all": [
            "protest", "accident", "traffic", "breaking", 
            "politics", "crime", "fire", "flood", "bengaluru", "mumbai"
        ],
        "stats": {
            "protest": 1245,
            "accident": 892,
            "breaking": 5678
        }
    }
    
    return jsonify(categories)

def get_trending_categories(posts):
    """Extract trending categories from posts"""
    all_cats = []
    for post in posts:
        all_cats.extend(post.get('categories', []))
    
    cat_counts = {}
    for cat in all_cats:
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    return sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:5]

# Register blueprint
def init_feed_routes(app):
    """Register with main Flask app"""
    app.register_blueprint(feed_bp, url_prefix='/api/feed')

if __name__ == "__main__":
    # Test feed
    print("📰 Sample public feed response:")
    print(json.dumps(SAMPLE_POSTS[0], indent=2))
