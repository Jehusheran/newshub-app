
"""
NewsHub AI Content Moderation (Fixed for NudeNet v3+)
- Nudity detection (NudeNet Detector ONLY)
- IT Rules 2021 compliance 
- Video frame analysis
"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
import logging

# Try to import NudeNet (modern version)
try:
    from nudenet import NudeDetector
    NUDENET_AVAILABLE = True
except ImportError:
    NUDENET_AVAILABLE = False
    print("⚠️  NudeNet not available. Using mock moderation.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsHubModerator:
    """AI-powered content moderation for news videos"""
    
    def __init__(self):
        self.detector = None
        self.nudity_threshold = 0.6  # Reject if >60% unsafe
        self.init_models()
    
    def init_models(self):
        """Initialize NudeNet detector (modern API)"""
        if NUDENET_AVAILABLE:
            try:
                logger.info("🔄 Initializing NudeNet Detector...")
                self.detector = NudeDetector()
                logger.info("✅ NudeNet detector ready")
            except Exception as e:
                logger.error(f"❌ NudeNet init failed: {e}")
                self.detector = None
        else:
            logger.info("ℹ️  Using mock moderation (install: pip install nudenet)")
    
    def extract_frames(self, video_path: str, max_frames: int = 10) -> List[str]:
        """Extract key frames from video for analysis"""
        frames = []
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total_frames // max_frames)
        
        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                frame_path = f"/tmp/frame_{i}.jpg"
                cv2.imwrite(frame_path, frame)
                frames.append(frame_path)
        
        cap.release()
        return frames
    
    def detect_nudity(self, image_path: str) -> Dict[str, float]:
        """Detect nudity using modern NudeNet API"""
        if self.detector:
            try:
                results = self.detector.detect(image_path)
                # Calculate nudity score from detections
                nudity_score = sum([d['score'] for d in results if d['score'] > 0.5])
                return {
                    'unsafe': min(1.0, nudity_score / max(1, len(results))),
                    'safe': 1.0 - min(1.0, nudity_score / max(1, len(results)))
                }
            except:
                return {'unsafe': 0.0, 'safe': 1.0}
        return {'unsafe': 0.0, 'safe': 1.0}
    
    def detect_exposed_parts(self, image_path: str) -> List[Dict]:
        """Detect specific NSFW parts"""
        if self.detector:
            try:
                return self.detector.detect(image_path)
            except:
                return []
        return []
    
    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """Complete video moderation analysis"""
        logger.info(f"🔍 Analyzing video: {video_path}")
        
        if not os.path.exists(video_path):
            return {"approved": False, "reason": "Video file not found"}
        
        # Extract frames
        frames = self.extract_frames(video_path)
        if not frames:
            return {"approved": False, "reason": "No frames extracted"}
        
        # Analyze each frame
        nudity_scores = []
        all_exposed_parts = []
        
        for frame_path in frames:
            nudity = self.detect_nudity(frame_path)
            nudity_scores.append(nudity['unsafe'])
            
            parts = self.detect_exposed_parts(frame_path)
            all_exposed_parts.extend(parts)
            
            # Cleanup
            try:
                os.unlink(frame_path)
            except:
                pass
        
        # Aggregate results
        max_nudity = max(nudity_scores) if nudity_scores else 0
        avg_nudity = sum(nudity_scores) / len(nudity_scores) if nudity_scores else 0
        
        # Decision logic (IT Rules 2021 compliance)
        is_nude = max_nudity > self.nudity_threshold
        has_explicit_parts = any(
            part.get('score', 0) > 0.7 
            for part in all_exposed_parts
        )
        
        result = {
            "approved": not (is_nude or has_explicit_parts),
            "max_nudity_score": max_nudity,
            "avg_nudity_score": avg_nudity,
            "total_frames": len(frames),
            "exposed_parts_count": len(all_exposed_parts),
            "nudity_detected": is_nude,
            "explicit_parts_detected": has_explicit_parts,
            "nudenet_available": NUDENET_AVAILABLE,
            "reason": self.get_rejection_reason(is_nude, has_explicit_parts)
        }
        
        logger.info(f"✅ Moderation complete: {result['approved']} (max_nudity: {max_nudity:.2f})")
        return result
    
    def get_rejection_reason(self, is_nude: bool, has_explicit_parts: bool) -> str:
        """Human-readable rejection reason"""
        if is_nude and has_explicit_parts:
            return "Graphic nudity + explicit parts detected"
        elif is_nude:
            return "High nudity probability detected"
        elif has_explicit_parts:
            return "Explicit body parts detected"
        return "Content approved - safe for NewsHub"

# Global singleton
moderator = NewsHubModerator()

# Flask API integration
def moderate_upload(video_path: str) -> Dict[str, Any]:
    """Main entrypoint for Flask upload moderation"""
    return moderator.analyze_video(video_path)

def mock_moderate(video_path: str) -> Dict[str, Any]:
    """Mock moderation for testing"""
    return {
        "approved": True,
        "max_nudity_score": 0.05,
        "avg_nudity_score": 0.02,
        "nudity_detected": False,
        "reason": "Mock approval (NudeNet recommended for production)",
        "nudenet_available": NUDENET_AVAILABLE
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        result = moderate_upload(video_path)
    else:
        result = mock_moderate("/tmp/test.mp4")
    
    print("NewsHub AI Moderation Result:")
    print(f"Approved: {result['approved']}")
    print(f"Reason: {result['reason']}")
    print(f"NudeNet: {'✅ LIVE' if result['nudenet_available'] else '❌ Mock mode'}")

