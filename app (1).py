import json
import requests
import yt_dlp
import re
import time
from flask import Flask, request

app = Flask(__name__)

PAGE_ACCESS_TOKEN = "IGAARWboxCWU1BZAFpqYTVyOFFHcTlLd3dKcEVZAWTlORU1DRjBsQXAyREk0VDdRZAnpJajM2TU4wN2gyRUoyRlFhdEQ5NUYtNGl6TDM4cjdTbzRzemhBR213MzktS3F0RVhQZAlVlSHQ1a1dDTWlaLXNKdC1YVm9fWXF2Q0ZAFbnktbwZDZD"
VERIFY_TOKEN = "ddddddddd"

processed_messages = set()

# ==============================
# الإحصائيات
# ==============================
message_count = 0
download_count = 0
total_usage = 0

# ==============================
# احصائيات المنصات
# ==============================
platform_stats = {
    "TikTok":0,
    "Instagram":0,
    "YouTube":0,
    "Facebook":0,
    "Twitter":0,
    "Reddit":0
}

# ==============================
# منع السبام
# ==============================
user_last_request = {}

# ==============================
# ملف المستخدمين
# ==============================
USERS_FILE = "users.txt"

def load_users():
    try:
        with open(USERS_FILE,"r") as f:
            return f.read().splitlines()
    except:
        return []

def save_user(user_id):
    users = load_users()
    if str(user_id) not in users:
        with open(USERS_FILE,"a") as f:
            f.write(str(user_id)+"\n")

# ==============================
# استخراج الرابط
# ==============================
def extract_url(text):
    urls = re.findall(r'(https?://[^\s]+)', text)
    if urls:
        return urls[0]
    return None

# ==============================
# كشف المنصة
# ==============================
def detect_platform(url):
    url = url.lower()
    if "tiktok.com" in url:
        return "TikTok"
    if "instagram.com" in url:
        return "Instagram"
    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    if "facebook.com" in url or "fb.watch" in url:
        return "Facebook"
    if "twitter.com" in url or "x.com" in url:
        return "Twitter"
    if "reddit.com" in url:
        return "Reddit"
    return "Unknown"

# ==============================
# تحميل الفيديو
# ==============================
def download_video(url):
    ydl_opts = {
        "format":"best",
        "quiet":True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url,download=False)
        return info

# ==============================
# Webhook Verification
# ==============================
@app.route('/webhook',methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge,200
    return "Forbidden",403

# ==============================
# المتغيرات الجديدة للرسائل التلقائية والإعلانات
# ==============================
auto_message = None
auto_pub_message = None
auto_pub_link = None

# ==============================
# Webhook الرئيسي
# ==============================
@app.route('/webhook',methods=['POST'])
def webhook():
    global message_count, download_count, total_usage
    global auto_message, auto_pub_message, auto_pub_link

    data = request.json
    print(json.dumps(data, indent=2))

    # الرد على التعليقات
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                comment_data = change.get("value", {})
                comment_id = comment_data.get("id")
                if not comment_id:
                    continue
                reply_to_comment(comment_id, "💚💢💌")

    # رسائل الخاص
    if data.get("object") != "instagram":
        return "OK", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            if not sender_id or "message" not in event:
                continue

            message = event["message"]
            message_id = message.get("mid")
            if message_id in processed_messages:
                continue
            processed_messages.add(message_id)
            message_count += 1
            save_user(sender_id)
            text = message.get("text","")
            now = time.time()

            if sender_id in user_last_request and now - user_last_request[sender_id] < 5:
                send_reply(sender_id, "⚠️ انتظر 10 ثواني قبل إرسال رابط جديد")
                return "OK", 200
            user_last_request[sender_id] = now

            # ======= الأوامر =======
            if text == "/user":
                send_reply(sender_id, f"""📊 إحصائيات البوت
📩 عدد الرسائل: {message_count}
🎬 عدد الفيديوهات: {download_count}
📈 إجمالي الاستخدام: {total_usage}
""")
                return "OK", 200

            if text == "/stats":
                stats_text = "📊 إحصائيات المنصات\n\n"
                for p, v in platform_stats.items():
                    stats_text += f"{p} : {v}\n"
                send_reply(sender_id, stats_text)
                return "OK", 200

            if text.startswith("/message"):
                msg = text.replace("/message", "").strip()
                users = load_users()
                for u in users:
                    send_reply(u, f"📢 رسالة:\n\n{msg}")
                send_reply(sender_id, f"✅ تم إرسال الرسالة إلى {len(users)} مستخدم")
                return "OK", 200

            # /hi
            if text.startswith("/hi"):
                msg = text.replace("/hi","").strip()
                if msg == "":
                    send_reply(sender_id, "❌ كتب الرسالة بعد /hi")
                    return "OK", 200
                auto_message = msg
                send_reply(sender_id, f"✅ تم تشغيل الرسالة التلقائية:\n\n{msg}")
                return "OK", 200

            # /histop
            if text == "/histop":
                auto_message = None
                send_reply(sender_id, "🛑 تم إيقاف الرسالة التلقائية")
                return "OK", 200

            # /menu
            if text == "/menu":
                menu_text = """📜 قائمة الأوامر:
/user - إحصائيات البوت
/stats - إحصائيات المنصات
/message <نص> - إرسال رسالة لكل المستخدمين
/hi <نص> - تشغيل رسالة تلقائية بعد كل فيديو
/histop - إيقاف الرسالة التلقائية
/menu - عرض قائمة الأوامر
/pub <نص>|<رابط> - تعيين الإعلان الذي يرسل بعد كل فيديو
/pubstop - إيقاف الإعلان التلقائي
"""
                send_reply(sender_id, menu_text)
                return "OK", 200

            # /pub
            if text.startswith("/pub"):
                parts = text.replace("/pub","").strip().split("|")
                if len(parts) != 2:
                    send_reply(sender_id, "❌ استعمل: /pub <نص الرسالة>|<رابط>")
                    return "OK", 200
                auto_pub_message, auto_pub_link = parts[0].strip(), parts[1].strip()
                send_reply(sender_id, f"✅ تم تفعيل الإعلان التلقائي بعد كل فيديو")
                return "OK", 200

            # /pubstop
            if text == "/pubstop":
                auto_pub_message, auto_pub_link = None, None
                send_reply(sender_id, "🛑 تم إيقاف الإعلان التلقائي")
                return "OK", 200

            # التعامل مع الفيديوهات
            if "attachments" in message:
                for att in message["attachments"]:
                    if att["type"] == "ig_reel" and "url" in att["payload"]:
                        send_reply(sender_id, "⏳ يتم تحميل REEL")
                        reel_url = att["payload"]["url"]
                        send_video(sender_id, reel_url)
                        download_count += 1
                        total_usage += 1
                        platform_stats["Instagram"] += 1
                        # رسالة /hi
                        if auto_message:
                            send_reply(sender_id, auto_message)
                        # إرسال الإعلان بعد الفيديو
                        if auto_pub_message and auto_pub_link:
                            send_button_message(sender_id, auto_pub_message, auto_pub_link)
                        return "OK", 200

                    if att["type"] in ["story","ig_story"]:
                        payload = att.get("payload",{})
                        story_url = payload.get("url") or payload.get("story_media_url")
                        if story_url:
                            send_reply(sender_id, "⏳ جاري تحميل STORI")
                            send_video(sender_id, story_url)
                            download_count += 1
                            total_usage += 1
                            platform_stats["Instagram"] += 1
                            if auto_message:
                                send_reply(sender_id, auto_message)
                            if auto_pub_message and auto_pub_link:
                                send_button_message(sender_id, auto_pub_message, auto_pub_link)
                            return "OK", 200

            url = extract_url(text)
            if url:
                platform = detect_platform(url)
                send_reply(sender_id, f"⏳ جاري تحميل الفيديو من {platform}")
                try:
                    info = download_video(url)
                    if platform == "YouTube" and info.get("duration",0) > 300:
                        send_reply(sender_id, "❌ فيديو YouTube يجب أن يكون أقل من 5 دقائق")
                        return "OK", 200
                    video_url = info["url"]
                    send_video(sender_id, video_url)
                    download_count += 1
                    total_usage += 1
                    if platform in platform_stats:
                        platform_stats[platform] += 1
                    if auto_message:
                        send_reply(sender_id, auto_message)
                    if auto_pub_message and auto_pub_link:
                        send_button_message(sender_id, auto_pub_message, auto_pub_link)
                except:
                    send_reply(sender_id, "❌ لم أستطع تحميل الفيديو")
            else:
                send_reply(sender_id, "قوم بي ارسال ريلز او صطوري من اجل تحميل 🎶")

    return "OK",200

# ==============================
# إرسال رسالة بزر (للإعلان)
# ==============================
def send_button_message(user_id, text, url):
    endpoint = f"https://graph.instagram.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": user_id},
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": [
                        {"type": "web_url", "url": url, "title": "فتح "}
                    ]
                }
            }
        }
    }
    requests.post(endpoint, json=payload)

# ==============================
# الرد على التعليق
# ==============================
def reply_to_comment(comment_id,text):
    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    payload = {"message":text,"access_token":PAGE_ACCESS_TOKEN}
    requests.post(url,data=payload)

# ==============================
# إرسال رسالة نصية
# ==============================
def send_reply(user_id,text):
    endpoint = f"https://graph.instagram.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient":{"id":user_id},"messaging_type":"RESPONSE","message":{"text":text}}
    requests.post(endpoint,json=payload)

# ==============================
# إرسال فيديو
# ==============================
def send_video(user_id,url):
    endpoint = f"https://graph.instagram.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient":{"id":user_id},
        "messaging_type":"RESPONSE",
        "message":{"attachment":{"type":"video","payload":{"url":url}}}
    }
    requests.post(endpoint,json=payload)

# ==============================
# تشغيل السيرفر
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0",port=13833)
