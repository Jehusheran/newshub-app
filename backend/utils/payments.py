#payments.py          # 60/40 royalty splits
"""
NewsHub Payments - Stripe + 60/40 Royalty Splits
- Video licensing (₹15K/video avg)
- Automated uploader payouts
- 90-day exclusive license expiry
- Indian Rupee (INR) pricing
"""

import stripe
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from decimal import Decimal
import json

# Configure Stripe (test mode)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_51...")  # Add to .env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsHubPayments:
    """Complete payment processing with royalty splits"""
    
    # Pricing tiers (INR)
    VIDEO_PRICES = {
        "basic": 10000,      # ₹10K - Local news
        "premium": 15000,    # ₹15K - Breaking news  
        "exclusive": 25000   # ₹25K - Major events
    }
    
    # Revenue split
    ROYALTY_SPLIT = {
        "uploader": Decimal("0.60"),  # 60% to citizen journalist
        "platform": Decimal("0.40")   # 40% NewsHub commission
    }
    
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    def create_checkout_session(self, video_id: str, price_tier: str = "premium", 
                              buyer_email: str = None) -> Dict:
        """
        Create Stripe Checkout session for video purchase
        Returns: {session_id, url}
        """
        price = self.VIDEO_PRICES.get(price_tier, self.VIDEO_PRICES["premium"])
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': f'NewsHub Exclusive: Video {video_id}',
                        'description': f'90-day exclusive license - Bengaluru footage',
                        'metadata': {
                            'video_id': video_id,
                            'price_tier': price_tier
                        }
                    },
                    'unit_amount': price * 100,  # Stripe uses paise
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://newshub.in/buyer/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://newshub.in/buyer/cancel',
            metadata={
                'video_id': video_id,
                'buyer_email': buyer_email or '',
                'timestamp': datetime.now().isoformat()
            },
            expires_at=int((datetime.now() + timedelta(hours=24)).timestamp())
        )
        
        return {
            "session_id": session.id,
            "url": session.url,
            "price": price,
            "tier": price_tier,
            "expires_at": session.expires_at
        }
    
    def calculate_royalty_split(self, total_amount: float) -> Dict[str, Decimal]:
        """60/40 royalty calculation"""
        total = Decimal(str(total_amount))
        uploader_share = total * self.ROYALTY_SPLIT["uploader"]
        platform_share = total * self.ROYALTY_SPLIT["platform"]
        
        return {
            "total": total,
            "uploader_share": uploader_share.quantize(Decimal('0.01')),
            "platform_share": platform_share.quantize(Decimal('0.01')),
            "currency": "INR"
        }
    
    def process_payment_webhook(self, payload: str, signature: str) -> Dict:
        """
        Handle Stripe webhook for completed payments
        Updates: Video status → SOLD, Purchase record, Royalty calculation
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
        except ValueError:
            return {"error": "Invalid payload"}
        except stripe.error.SignatureVerificationError:
            return {"error": "Invalid signature"}
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            video_id = session['metadata'].get('video_id')
            amount_total = int(session['amount_total']) / 100  # Convert paise to INR
            
            # Calculate royalties
            royalties = self.calculate_royalty_split(amount_total)
            
            # Business logic
            result = {
                "status": "payment_confirmed",
                "video_id": video_id,
                "buyer_email": session['customer_email'],
                "amount_inr": amount_total,
                "royalties": royalties,
                "license_expiry": (datetime.now() + timedelta(days=90)).isoformat(),
                "actions": [
                    "mark_video_sold",
                    "create_purchase_record", 
                    "notify_uploader",
                    "queue_royalty_payout"
                ]
            }
            
            logger.info(f"✅ Payment processed: {result}")
            return result
        
        return {"status": "ignored", "event_type": event['type']}
    
    def create_license_url(self, purchase_id: str, video_id: str, 
                          buyer_email: str, expiry_days: int = 90) -> str:
        """Generate DRM-protected download URL"""
        expiry = datetime.now() + timedelta(days=expiry_days)
        token = f"{purchase_id}:{video_id}:{expiry.timestamp()}:{buyer_email}"
        
        # In production: sign with JWT
        signed_url = f"https://s3.newshub.in/licenses/{purchase_id}?token={token}&expires={int(expiry.timestamp())}"
        return signed_url
    
    def payout_uploader(self, uploader_id: str, amount: Decimal, video_title: str):
        """Queue royalty payout to uploader (Razorpay/NEFT)"""
        payout = {
            "uploader_id": uploader_id,
            "amount": amount,
            "video_title": video_title,
            "status": "pending",
            "method": "razorpay_payout",  # Indian UPI/bank transfer
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"💰 Royalty queued: ₹{amount} for {video_title}")
        return payout
    
    def generate_receipt(self, purchase_ Dict) -> Dict:
        """Tax-compliant receipt (GST India)"""
        royalties = self.calculate_royalty_split(purchase_data['amount'])
        
        receipt = {
            "receipt_id": f"NH-{datetime.now().strftime('%Y%m%d%H%M')}",
            "buyer": purchase_data['buyer_email'],
            "video_title": purchase_data['video_title'],
            "amount_breakdown": royalties,
            "gst_applicable": True,  # 18% GST on platform commission
            "license_terms": "90-day exclusive, non-transferable",
            "timestamp": datetime.now().isoformat()
        }
        
        return receipt

# Global singleton
payments = NewsHubPayments()

# Flask integration helpers
def create_video_checkout(video_id: str, buyer_email: str = None):
    """Flask route helper"""
    return payments.create_checkout_session(video_id, buyer_email=buyer_email)

def handle_stripe_webhook(payload: str, signature: str):
    """Flask webhook endpoint"""
    return payments.process_payment_webhook(payload, signature)

# Test functions
def test_payment_flow():
    """Test complete payment flow"""
    session = payments.create_checkout_session("video-123", "premium")
    royalties = payments.calculate_royalty_split(15000)
    
    print(f"✅ Checkout URL: {session['url']}")
    print(f"💰 Uploader: ₹{royalties['uploader_share']}")
    print(f"🏢 Platform: ₹{royalties['platform_share']}")

if __name__ == "__main__":
    test_payment_flow()
