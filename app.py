"""
بوت Facebook Messenger كيحول فيديو (مشارك كمرفق، أو رابط مبعوت كنص) إلى ملف mp4
كيرجعو للمستخدم فنفس المحادثة.

يخدم فوق Messenger Platform API (Meta Graph API) + yt-dlp لجلب الفيديوهات من الروابط.
"""

import os
import re
import uuid
import hmac
import hashlib
import logging
import tempfile

import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fb-video-bot")

app = Flask(__name__)

VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]
APP_SECRET = os.environ.get("APP_SECRET")  # اختياري، ولكن موصى به بزاف
PAGE_ID = os.environ["PAGE_ID"]
GRAPH_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# أنواع المرفقات اللي كيتصايفط بيها فيديو/ريلز/بوست مشارك فـ Messenger
MEDIA_ATTACHMENT_TYPES = {"video", "reel", "post", "share"}

# للتقاط رابط فيسبوك مبعوت كنص عادي (facebook.com/... أو fb.watch/...)
FB_URL_RE = re.compile(
    r"https?://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.watch)/\S+", re.IGNORECASE
)


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """تتأكد أن الطلب جاي فعلا من Meta (X-Hub-Signature-256)."""
    if not APP_SECRET:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    received = signature_header.split("sha256=", 1)[1]
    return hmac.compare_digest(expected, received)


@app.get("/webhook")
def webhook_verify():
    """Meta كتصايفط GET باش تتأكد من الـ webhook (subscribe)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@app.post("/webhook")
def webhook_event():
    if not verify_signature(request.get_data(), request.headers.get("X-Hub-Signature-256", "")):
        logger.warning("توقيع غير صالح، تم رفض الطلب")
        return "Invalid signature", 403

    data = request.get_json(silent=True) or {}
    if data.get("object") != "page":
        return jsonify({"status": "ignored"}), 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            try:
                handle_messaging_event(event)
            except Exception:
                logger.exception("خطأ فمعالجة الرسالة")

    return jsonify({"status": "ok"}), 200


def handle_messaging_event(event: dict):
    sender_id = event.get("sender", {}).get("id")
    message = event.get("message", {})
    if not sender_id or not message:
        return

    # 1) واش الرسالة فيها مرفق فيديو/ريلز/بوست مشارك؟
    video_url = None
    for att in message.get("attachments", []):
        if att.get("type") in MEDIA_ATTACHMENT_TYPES:
            url = att.get("payload", {}).get("url")
            if url:
                video_url = url
                break

    text_link = None
    if not video_url:
        # 2) واش الرسالة نص فيه رابط فيسبوك؟
        text = message.get("text", "") or ""
        m = FB_URL_RE.search(text)
        if m:
            text_link = m.group(0)

    if not video_url and not text_link:
        return  # ماكاينش فيديو ولا رابط صالح

    send_text(sender_id, "⏳ كنحمّل الفيديو، تسنى شوية...")

    video_path = None
    try:
        if video_url:
            video_path = download_direct(video_url)
        else:
            video_path = download_via_ytdlp(text_link)

        attachment_id = upload_video_attachment(video_path)
        send_video_attachment(sender_id, attachment_id)
    except Exception:
        logger.exception("فشل تحميل/إرسال الفيديو")
        send_text(
            sender_id,
            "❌ ما قدرتش نحمل الفيديو. تأكد أنه فيديو عام (public) وجرب مرة أخرى.",
        )
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)


def download_direct(url: str) -> str:
    """كتحمل الفيديو من رابط مباشر (جاي فـ payload.url من Meta CDN)."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            f.write(chunk)
    return path


def download_via_ytdlp(page_url: str) -> str:
    """كتحمل فيديو فيسبوك عام انطلاقا من رابط الصفحة (facebook.com/... أو fb.watch/...)."""
    import yt_dlp

    out_template = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.%(ext)s")
    options = {
        "format": "mp4/best[ext=mp4]/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(page_url, download=True)
        filename = ydl.prepare_filename(info)
        if not filename.endswith(".mp4") and os.path.exists(filename.rsplit(".", 1)[0] + ".mp4"):
            filename = filename.rsplit(".", 1)[0] + ".mp4"
    return filename


def upload_video_attachment(video_path: str) -> str:
    """كترفع الفيديو لـ Graph API وكترجع attachment_id قابل لإعادة الاستعمال."""
    url = f"{GRAPH_BASE}/{PAGE_ID}/message_attachments"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"message": '{"attachment":{"type":"video","payload":{"is_reusable":true}}}'}
    with open(video_path, "rb") as f:
        files = {"filedata": ("video.mp4", f, "video/mp4")}
        resp = requests.post(url, params=params, data=data, files=files, timeout=180)
    resp.raise_for_status()
    return resp.json()["attachment_id"]


def send_video_attachment(recipient_id: str, attachment_id: str):
    url = f"{GRAPH_BASE}/{PAGE_ID}/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    body = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "video",
                "payload": {"attachment_id": attachment_id},
            }
        },
    }
    resp = requests.post(url, params=params, json=body, timeout=30)
    resp.raise_for_status()


def send_text(recipient_id: str, text: str):
    url = f"{GRAPH_BASE}/{PAGE_ID}/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    body = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    try:
        requests.post(url, params=params, json=body, timeout=30)
    except requests.RequestException:
        logger.exception("فشل إرسال رسالة نصية")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
