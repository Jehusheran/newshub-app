#newshub/backend/models.py
"""NewsHub Database Models - Prisma Client Python"""
from enum import Enum
from typing import List, Optional, Dict, Any
from prisma import Prisma
import os
from dotenv import load_dotenv

load_dotenv()

# Global Prisma client (singleton)
prisma = Prisma()

class Role(str, Enum):
    UPLOADER = "UPLOADER"
    MEDIA_BUYER = "MEDIA_BUYER" 
    ADMIN = "ADMIN"
    PUBLIC = "PUBLIC"

class VideoStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SOLD = "SOLD"

# NewsHub Core Models
class User:
    """User model for uploaders, buyers, admins"""
    id: str
    email: str
    role: Role
    organization: Optional[str]  # For MEDIA_BUYER
    verified: bool
    created_at: str
    
    def __init__(self,  Dict[str, Any]):
        self.id = data.get('id')
        self.email = data.get('email')
        self.role = Role(data.get('role', 'PUBLIC'))
        self.organization = data.get('organization')
        self.verified = data.get('verified', False)
        self.created_at = data.get('createdAt')

class Video:
    """News video with metadata, ratings, licensing"""
    id: str
    uploader_id: str
    title: str
    thumbnail_url: str
    video_url: str
    location: str
    gps: Dict[str, float]  # {"lat": 12.97, "lng": 77.59}
    rating: Optional[int]  # 1-5 stars (admin)
    categories: List[str]  # ["protest", "accident"]
    status: VideoStatus
    price: float  # INR
    verified_by: Optional[str]  # admin ID
    verified_at: Optional[str]
    created_at: str
    
    def __init__(self,  Dict[str, Any]):
        self.id = data.get('id')
        self.uploader_id = data.get('uploaderId')
        self.title = data.get('title')
        self.thumbnail_url = data.get('thumbnailUrl')
        self.video_url = data.get('videoUrl')
        self.location = data.get('location')
        self.gps = data.get('gps', {})
        self.rating = data.get('rating')
        self.categories = data.g

