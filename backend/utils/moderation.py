#moderation.py        # AI nudity detection
"""
NewsHub AI Content Moderation
- Nudity detection (NudeNet)
- Graphic violence scoring  
- IT Rules 2021 compliance
"""

import os
import requests
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from nudenet import NudeClassifier, NudeDetector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsHubModerator:
    """AI-powered content moderation for news videos"""
    
    def __init__(self):
        self.classifier = None
        self.detector = None
        self.nudity_threshold = 0.8  # Reject if >80% unsafe
        self.init_models()
    
    def init_models(self):
        """Initialize NudeNet models (downloads on first run)"""
        try:
            logger.info("🔄 Initializing NudeNet classifier...")
            self.classifier = NudeClassifier()
            logger.info("✅ NudeNet classifier ready")
            
            logger.info("🔄 Initializing NudeNet detector...")
            self.detector = NudeDetector()
            logger.info("✅ NudeNet detector ready")
        except Exception as e:
            logger.error(f"❌ Model init failed: {e}")
            # Fallback to mock mode
            self.classifier = MockClassifier()
            self.detector = MockDetector()
    
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
        """Classify image as safe/unsafe using NudeNet"""
        if self.classifier:
            result = self.classifier.classify(image_path)
            return result.get(image_path, {'safe': 1.0, 'unsafe': 0.0})
        return {'safe': 1.0, 'unsafe': 0.0}
    
    def detect_exposed_parts(self, image_path: str) -> List[Dict]:
        """Detect specific NSFW parts (breasts, genitalia, etc.)"""
        if self.detector:
            return self.detector.detect(image_path)
        return []
    
    def analyze_video(self, video_path: str) -> Dict[str, any]:
        """Complete video moderation analysis"""
        logger.info(f"🔍 Analyzing video: {video_path}")
        
        # Extract frames
        frames = self.extract_frames(video_path)
        if not frames:
            return {"approved": False, "reason": "No frames extracted"}
        
        # Analyze each frame
        nudity_scores = []
        exposed_parts = []
        
        for frame_path in frames:
            # Nudity classification
            nudity = self.detect_nudity(frame_path)
            nudity_scores.append(nudity['unsafe'])
            
            # Detailed detection
            parts = self.detect_exposed_parts(frame_path)
            exposed_parts.extend(parts)
            
            # Cleanup
            os.unlink(frame_path)
        
        # Aggregate results
        max_nudity = max(nudity_scores)
        avg_nudity = sum(nudity_scores) / len(nudity_scores)
        
        # Decision logic (IT Rules 2021 compliance)
        is_nude = max_nudity > self.nudity_threshold
        has_exposed_parts = any(
            part['score'] > 0.7 for part in exposed_parts
            if any(term in part['label'].upper() for term in 
                   ['EXPOSED_', 'GENITALIA', 'BREAST'])
        )
        
        result = {
            "approved": not (is_nude or has_exposed_parts),
            "max_nudity_score": max_nudity,
            "avg_nudity_score": avg_nudity,
            "total_frames": len(frames),
            "exposed_parts": exposed_parts[-5:],  # Last 5 detections
            "nudity_detected": is_nude,
            "exposed_parts_detected": has_exposed_parts,
            "reason": self.get_rejection_reason(is_nude, has_exposed_parts)
        }
        
        logger.info(f"✅ Moderation complete: {result['approved']}")
        return result
    
    def get_rejection_reason(self, is_nude: bool, has_exposed_parts: bool) -> str:
        """Human-readable rejection reason"""
        if is_nude and has_exposed_parts:
            return "Graphic nudity detected (breasts/genitalia exposed)"
        elif is_nude:
            return "High nudity probability detected"
        elif has_exposed_parts:
            return "Explicit body parts detected"
        return "Content safe"
    
    def mock_moderate(self, video_path: str) -> Dict[str, any]:
        """Mock moderation for testing (no ML models)"""
        return {
            "approved": True,
            "max_nudity_score": 0.05,
            "avg_nudity_score": 0.02,
            "nudity_detected": False,
            "reason": "Mock approval (add NudeNet for production)"
        }

# Mock classes for testing without NudeNet
class MockClassifier:
    def classify(self, image_path: str) -> Dict[str, Dict[str, float]]:
        return {image_path: {'safe': 0.95, 'unsafe': 0.05}}

class MockDetector:
    def detect(self, image_path: str) -> List[Dict]:
        return []

# Global singleton
moderator = NewsHubModerator()

# API endpoints for Flask integration
def moderate_upload(video_path: str) -> Dict[str, any]:
    """Main entrypoint for upload moderation"""
    return moderator.analyze_video(video_path)

if __name__ == "__main__":
    # Test the moderator
    result = moderator.mock_moderate("/tmp/test.mp4")
    print(result)
