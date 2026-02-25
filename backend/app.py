from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "service": "newshub-backend", 
        "port": 8080,
        "version": "1.0.0",
        "database": "mock-ready"
    })

@app.route('/api/feed/public-feed')
def public_feed():
    return jsonify({
        "feed": "📰 NewsHub Public Feed LIVE!",
        "videos": [
            {
                "id": 1,
                "title": "Breaking: Bengaluru Protest", 
                "thumbnail": "https://via.placeholder.com/300x200?text=Protest",
                "duration": "2:30",
                "price": "₹2500"
            }
        ],
        "total": 12
    })

@app.route('/api/buyer/videos/approved')
def buyer_videos():
    return jsonify({
        "videos": [
            {
                "id": 1,
                "title": "Election Results Live", 
                "price": 3500,
                "duration": "45s",
                "thumbnail": "https://via.placeholder.com/300x200?text=Election",
                "seller": "NewsHub Pro"
            },
            {
                "id": 2,
                "title": "Traffic Accident MG Road", 
                "price": 1800,
                "duration": "1:15",
                "thumbnail": "https://via.placeholder.com/300x200?text=Accident",
                "seller": "Citizen Journalist"
            }
        ],
        "total": 27
    })

@app.route('/api/admin/videos/pending')
def admin_pending():
    return jsonify({
        "pending_videos": [
            {
                "id": 101,
                "title": "New Upload - Review Needed",
                "uploader": "test@newshub.com",
                "price": 2500,
                "created_at": "2026-02-25T15:20:00Z",
                "ai_status": "passed"
            }
        ],
        "total": 3
    })

@app.route('/api/upload', methods=['POST'])
def upload():
    title = request.form.get('title', 'Untitled Video')
    price = float(request.form.get('price', 0))
    
    return jsonify({
        "success": True,
        "video_id": 999,
        "title": title,
        "price": price,
        "status": "PENDING",
        "message": "✅ Video uploaded successfully! Awaiting admin approval (mock mode)",
        "next_steps": [
            "1. AI Moderation: Completed",
            "2. Admin Review: Pending", 
            "3. Publish: Available for buyers"
        ]
    }), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

