"""
Web Push notifications via VAPID (pywebpush).
"""
import json
import logging
import os

from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


def get_vapid_public_key() -> str:
    return os.getenv("VAPID_PUBLIC_KEY", "")


def send_push_notification(subscription_json: str, title: str, body: str) -> bool:
    private_key = os.getenv("VAPID_PRIVATE_KEY", "")
    public_key = os.getenv("VAPID_PUBLIC_KEY", "")
    email = os.getenv("VAPID_CLAIMS_EMAIL", "admin@example.com")

    if not private_key or not public_key:
        logger.warning("VAPID keys not configured — push notification skipped")
        return False

    try:
        subscription = json.loads(subscription_json)
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{email}"},
        )
        logger.info("Push notification sent: %s", title)
        return True
    except WebPushException as exc:
        logger.error("Push notification failed (WebPushException): %s", exc)
        return False
    except Exception as exc:
        logger.error("Push notification error: %s", exc)
        return False
