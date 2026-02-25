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
            {"id": 1, "title": "Bengaluru Protest", "price": "₹2500", "thumbnail": "https://via.placeholder.com/300x200?text=Protest"}
        ],
        "total": 12
    })

@app.route('/api/buyer/videos/approved')
def buyer_videos():
    return jsonify({
        "videos": [
            {"id": 1, "title": "Election Live", "price": 3500, "duration": "45s"},
            {"id": 2, "title": "MG Road Accident", "price": 1800, "duration": "1:15"}
        ],
        "total": 27
    })

@app.route('/api/admin/videos/pending')
def admin_pending():
    return jsonify({
        "pending_videos": [{"id": 101, "title": "New Upload", "status": "PENDING"}],
        "total": 3
    })

@app.route('/api/upload', methods=['POST'])
def upload():
    title = request.form.get('title', 'Untitled')
    price = float(request.form.get('price', 0))
    return jsonify({
        "success": True,
        "video_id": 999,
        "title": title,
        "price": price,
        "status": "PENDING",
        "message": "✅ Upload complete! Awaiting admin review"
    }), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

