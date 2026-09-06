import os
import json
import re
import time
import requests
import yt_dlp

from flask import Flask, request

app = Flask(__name__)

# =========================================================
# CONFIG
# =========================================================

# مهم:
# حط Access Token في Environment Variable
#
# Linux:
# export PAGE_ACCESS_TOKEN="YOUR_NEW_TOKEN"
#
# Windows:
# set PAGE_ACCESS_TOKEN=YOUR_NEW_TOKEN

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

VERIFY_TOKEN = os.getenv(
    "VERIFY_TOKEN",
    "ddddddddd"
)

# Meta Graph API version
META_VERSION = "v26.0"

# Instagram Graph API
IG_GRAPH = f"https://graph.instagram.com/{META_VERSION}"

# Facebook Graph API
FB_GRAPH = f"https://graph.facebook.com/{META_VERSION}"


# =========================================================
# SECURITY CHECK
# =========================================================

if not PAGE_ACCESS_TOKEN:
    print("WARNING: PAGE_ACCESS_TOKEN is not configured.")


# =========================================================
# DATA
# =========================================================

processed_messages = set()

message_count = 0
download_count = 0
total_usage = 0


# =========================================================
# PLATFORM STATS
# =========================================================

platform_stats = {
    "TikTok": 0,
    "Instagram": 0,
    "YouTube": 0,
    "Facebook": 0,
    "Twitter": 0,
    "Reddit": 0
}


# =========================================================
# SPAM PROTECTION
# =========================================================

user_last_request = {}

REQUEST_COOLDOWN = 10


# =========================================================
# USERS FILE
# =========================================================

USERS_FILE = "users.txt"


def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return f.read().splitlines()
    except Exception:
        return []


def save_user(user_id):
    users = load_users()

    user_id = str(user_id)

    if user_id not in users:
        try:
            with open(USERS_FILE, "a", encoding="utf-8") as f:
                f.write(user_id + "\n")
        except Exception as e:
            print("SAVE USER ERROR:", e)


# =========================================================
# URL EXTRACTION
# =========================================================

def extract_url(text):
    if not text:
        return None

    urls = re.findall(
        r'https?://[^\s<>"\']+',
        text
    )

    if urls:
        return urls[0].rstrip(".,!?)]}")

    return None


# =========================================================
# PLATFORM DETECTION
# =========================================================

def detect_platform(url):

    if not url:
        return "Unknown"

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


# =========================================================
# YT-DLP
# =========================================================

def download_video(url):

    ydl_opts = {
        "format": "best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            url,
            download=False
        )

        return info


# =========================================================
# META REQUEST HELPER
# =========================================================

def meta_post(endpoint, payload=None):

    if not PAGE_ACCESS_TOKEN:
        print("META ERROR: PAGE_ACCESS_TOKEN missing")
        return None

    try:

        response = requests.post(
            endpoint,
            params={
                "access_token": PAGE_ACCESS_TOKEN
            },
            json=payload,
            timeout=30
        )

        print(
            "META POST:",
            response.status_code,
            response.text[:1000]
        )

        return response

    except requests.RequestException as e:

        print(
            "META REQUEST ERROR:",
            str(e)
        )

        return None


# =========================================================
# WEBHOOK VERIFICATION
# =========================================================

@app.route("/webhook", methods=["GET"])
def verify():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if (
        mode == "subscribe"
        and token == VERIFY_TOKEN
    ):
        return challenge, 200

    return "Forbidden", 403


# =========================================================
# AUTOMATIC MESSAGES
# =========================================================

auto_message = None

auto_pub_message = None
auto_pub_link = None


# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    global message_count
    global download_count
    global total_usage

    global auto_message
    global auto_pub_message
    global auto_pub_link

    try:
        data = request.get_json(
            silent=True
        ) or {}

        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            )
        )

    except Exception as e:

        print(
            "JSON ERROR:",
            e
        )

        return "OK", 200


    # =====================================================
    # COMMENTS
    # =====================================================

    for entry in data.get("entry", []):

        for change in entry.get(
            "changes",
            []
        ):

            if change.get("field") == "comments":

                comment_data = change.get(
                    "value",
                    {}
                )

                comment_id = comment_data.get(
                    "id"
                )

                if not comment_id:
                    continue

                reply_to_comment(
                    comment_id,
                    "💚💢💌"
                )


    # =====================================================
    # ONLY INSTAGRAM
    # =====================================================

    if data.get("object") != "instagram":
        return "OK", 200


    # =====================================================
    # MESSAGING EVENTS
    # =====================================================

    for entry in data.get(
        "entry",
        []
    ):

        for event in entry.get(
            "messaging",
            []
        ):

            sender_id = (
                event
                .get("sender", {})
                .get("id")
            )

            if not sender_id:
                continue


            if "message" not in event:
                continue


            message = event.get(
                "message",
                {}
            )


            # =================================================
            # MESSAGE ID
            # =================================================

            message_id = message.get(
                "mid"
            )

            if message_id:

                if message_id in processed_messages:
                    print(
                        "DUPLICATE MESSAGE:",
                        message_id
                    )
                    continue

                processed_messages.add(
                    message_id
                )


            # =================================================
            # STATS
            # =================================================

            message_count += 1

            save_user(sender_id)


            # =================================================
            # TEXT
            # =================================================

            text = message.get(
                "text",
                ""
            ).strip()


            # =================================================
            # SPAM PROTECTION
            # =================================================

            now = time.time()

            last_request = user_last_request.get(
                sender_id
            )

            if (
                last_request
                and
                now - last_request < REQUEST_COOLDOWN
            ):

                send_reply(
                    sender_id,
                    "⚠️ انتظر 10 ثواني قبل إرسال رابط جديد"
                )

                continue


            user_last_request[sender_id] = now


            # =================================================
            # /user
            # =================================================

            if text == "/user":

                send_reply(
                    sender_id,
                    f"""📊 إحصائيات البوت

📩 عدد الرسائل: {message_count}

🎬 عدد الفيديوهات: {download_count}

📈 إجمالي الاستخدام: {total_usage}
"""
                )

                continue


            # =================================================
            # /stats
            # =================================================

            if text == "/stats":

                stats_text = (
                    "📊 إحصائيات المنصات\n\n"
                )

                for platform, count in platform_stats.items():

                    stats_text += (
                        f"{platform} : {count}\n"
                    )

                send_reply(
                    sender_id,
                    stats_text
                )

                continue


            # =================================================
            # /message
            # =================================================

            if text.startswith("/message"):

                msg = (
                    text
                    .replace(
                        "/message",
                        "",
                        1
                    )
                    .strip()
                )

                if not msg:

                    send_reply(
                        sender_id,
                        "❌ كتب الرسالة بعد /message"
                    )

                    continue


                users = load_users()

                sent = 0

                for user in users:

                    if send_reply(
                        user,
                        f"📢 رسالة:\n\n{msg}"
                    ):
                        sent += 1


                send_reply(
                    sender_id,
                    f"✅ تم إرسال الرسالة إلى {sent} مستخدم"
                )

                continue


            # =================================================
            # /hi
            # =================================================

            if text.startswith("/hi"):

                msg = (
                    text
                    .replace(
                        "/hi",
                        "",
                        1
                    )
                    .strip()
                )

                if not msg:

                    send_reply(
                        sender_id,
                        "❌ كتب الرسالة بعد /hi"
                    )

                    continue


                auto_message = msg

                send_reply(
                    sender_id,
                    f"✅ تم تشغيل الرسالة التلقائية:\n\n{msg}"
                )

                continue


            # =================================================
            # /histop
            # =================================================

            if text == "/histop":

                auto_message = None

                send_reply(
                    sender_id,
                    "🛑 تم إيقاف الرسالة التلقائية"
                )

                continue


            # =================================================
            # /menu
            # =================================================

            if text == "/menu":

                menu_text = """📜 قائمة الأوامر:

/user - إحصائيات البوت

/stats - إحصائيات المنصات

/message <نص> - إرسال رسالة لكل المستخدمين

/hi <نص> - تشغيل رسالة تلقائية بعد كل فيديو

/histop - إيقاف الرسالة التلقائية

/pub <نص>|<رابط> - تعيين الإعلان الذي يرسل بعد كل فيديو

/pubstop - إيقاف الإعلان التلقائي

/menu - عرض قائمة الأوامر
"""

                send_reply(
                    sender_id,
                    menu_text
                )

                continue


            # =================================================
            # /pub
            # =================================================

            if text.startswith("/pub"):

                command = (
                    text
                    .replace(
                        "/pub",
                        "",
                        1
                    )
                    .strip()
                )

                parts = command.split("|")

                if len(parts) != 2:

                    send_reply(
                        sender_id,
                        "❌ استعمل:\n/pub <نص الرسالة>|<رابط>"
                    )

                    continue


                auto_pub_message = (
                    parts[0].strip()
                )

                auto_pub_link = (
                    parts[1].strip()
                )


                send_reply(
                    sender_id,
                    "✅ تم تفعيل الإعلان التلقائي بعد كل فيديو"
                )

                continue


            # =================================================
            # /pubstop
            # =================================================

            if text == "/pubstop":

                auto_pub_message = None
                auto_pub_link = None

                send_reply(
                    sender_id,
                    "🛑 تم إيقاف الإعلان التلقائي"
                )

                continue


            # =================================================
            # ATTACHMENTS
            # =================================================

            attachments = message.get(
                "attachments",
                []
            )


            if attachments:

                for att in attachments:

                    if not isinstance(
                        att,
                        dict
                    ):
                        continue


                    att_type = att.get(
                        "type"
                    )

                    payload = att.get(
                        "payload",
                        {}
                    )

                    if not isinstance(
                        payload,
                        dict
                    ):
                        payload = {}


                    # =========================================
                    # DEBUG
                    # =========================================

                    print(
                        "ATTACHMENT TYPE:",
                        att_type
                    )

                    print(
                        "ATTACHMENT PAYLOAD:",
                        json.dumps(
                            payload,
                            indent=2,
                            ensure_ascii=False
                        )
                    )


                    # =========================================
                    # INSTAGRAM REEL
                    # =========================================

                    if att_type == "ig_reel":

                        video_url = payload.get(
                            "url"
                        )


                        if video_url:

                            send_reply(
                                sender_id,
                                "⏳ يتم تحميل REEL"
                            )


                            success = send_video(
                                sender_id,
                                video_url
                            )


                            if success:

                                download_count += 1

                                total_usage += 1

                                platform_stats[
                                    "Instagram"
                                ] += 1


                                if auto_message:

                                    send_reply(
                                        sender_id,
                                        auto_message
                                    )


                                if (
                                    auto_pub_message
                                    and
                                    auto_pub_link
                                ):

                                    send_button_message(
                                        sender_id,
                                        auto_pub_message,
                                        auto_pub_link
                                    )

                            else:

                                send_reply(
                                    sender_id,
                                    "❌ تعذر إرسال الفيديو من Instagram"
                                )


                            continue


                    # =========================================
                    # VIDEO
                    # =========================================

                    if att_type == "video":

                        video_url = payload.get(
                            "url"
                        )


                        if video_url:

                            send_reply(
                                sender_id,
                                "⏳ جاري إرسال الفيديو"
                            )


                            success = send_video(
                                sender_id,
                                video_url
                            )


                            if success:

                                download_count += 1

                                total_usage += 1

                                platform_stats[
                                    "Instagram"
                                ] += 1


                                if auto_message:

                                    send_reply(
                                        sender_id,
                                        auto_message
                                    )


                                if (
                                    auto_pub_message
                                    and
                                    auto_pub_link
                                ):

                                    send_button_message(
                                        sender_id,
                                        auto_pub_message,
                                        auto_pub_link
                                    )


                            else:

                                send_reply(
                                    sender_id,
                                    "❌ تعذر إرسال الفيديو"
                                )


                            continue


                    # =========================================
                    # STORY
                    # =========================================

                    if att_type in [
                        "story",
                        "ig_story"
                    ]:

                        story_url = (
                            payload.get("url")
                            or
                            payload.get(
                                "story_media_url"
                            )
                        )


                        if story_url:

                            send_reply(
                                sender_id,
                                "⏳ جاري تحميل STORI"
                            )


                            success = send_video(
                                sender_id,
                                story_url
                            )


                            if success:

                                download_count += 1

                                total_usage += 1

                                platform_stats[
                                    "Instagram"
                                ] += 1


                                if auto_message:

                                    send_reply(
                                        sender_id,
                                        auto_message
                                    )


                                if (
                                    auto_pub_message
                                    and
                                    auto_pub_link
                                ):

                                    send_button_message(
                                        sender_id,
                                        auto_pub_message,
                                        auto_pub_link
                                    )


                            else:

                                send_reply(
                                    sender_id,
                                    "❌ تعذر إرسال STORI"
                                )


                            continue


            # =================================================
            # TEXT URL
            # =================================================

            url = extract_url(text)


            if url:

                platform = detect_platform(
                    url
                )


                send_reply(
                    sender_id,
                    f"⏳ جاري تحميل الفيديو من {platform}"
                )


                try:

                    info = download_video(
                        url
                    )


                    # =========================================
                    # YOUTUBE LIMIT
                    # =========================================

                    if (
                        platform == "YouTube"
                        and
                        info.get("duration", 0) > 300
                    ):

                        send_reply(
                            sender_id,
                            "❌ فيديو YouTube يجب أن يكون أقل من 5 دقائق"
                        )

                        continue


                    video_url = info.get(
                        "url"
                    )


                    if not video_url:

                        raise Exception(
                            "yt-dlp did not return video URL"
                        )


                    success = send_video(
                        sender_id,
                        video_url
                    )


                    if not success:

                        send_reply(
                            sender_id,
                            "❌ تعذر إرسال الفيديو"
                        )

                        continue


                    download_count += 1

                    total_usage += 1


                    if platform in platform_stats:

                        platform_stats[
                            platform
                        ] += 1


                    if auto_message:

                        send_reply(
                            sender_id,
                            auto_message
                        )


                    if (
                        auto_pub_message
                        and
                        auto_pub_link
                    ):

                        send_button_message(
                            sender_id,
                            auto_pub_message,
                            auto_pub_link
                        )


                except Exception as e:

                    print(
                        "DOWNLOAD ERROR:",
                        repr(e)
                    )


                    send_reply(
                        sender_id,
                        "❌ لم أستطع تحميل الفيديو"
                    )


            else:

                # إذا كانت الرسالة مجرد نص عادي
                # وما فيهاش attachment

                send_reply(
                    sender_id,
                    "قوم بإرسال ريلز أو ستوري من أجل تحميل 🎶"
                )


    return "OK", 200


# =========================================================
# SEND BUTTON MESSAGE
# =========================================================

def send_button_message(
    user_id,
    text,
    url
):

    endpoint = (
        f"{IG_GRAPH}/me/messages"
    )


    payload = {

        "recipient": {
            "id": user_id
        },

        "messaging_type": "RESPONSE",

        "message": {

            "attachment": {

                "type": "template",

                "payload": {

                    "template_type": "button",

                    "text": text,

                    "buttons": [

                        {
                            "type": "web_url",
                            "url": url,
                            "title": "فتح"
                        }

                    ]

                }

            }

        }

    }


    response = meta_post(
        endpoint,
        payload
    )


    if response is None:
        return False


    return response.ok


# =========================================================
# REPLY TO COMMENT
# =========================================================

def reply_to_comment(
    comment_id,
    text
):

    endpoint = (
        f"{FB_GRAPH}/{comment_id}/replies"
    )


    payload = {
        "message": text
    }


    response = meta_post(
        endpoint,
        payload
    )


    if response is None:
        return False


    return response.ok


# =========================================================
# SEND TEXT
# =========================================================

def send_reply(
    user_id,
    text
):

    endpoint = (
        f"{IG_GRAPH}/me/messages"
    )


    payload = {

        "recipient": {
            "id": user_id
        },

        "messaging_type": "RESPONSE",

        "message": {
            "text": text
        }

    }


    response = meta_post(
        endpoint,
        payload
    )


    if response is None:
        return False


    return response.ok


# =========================================================
# SEND VIDEO
# =========================================================

def send_video(
    user_id,
    video_url
):

    if not video_url:

        print(
            "SEND VIDEO ERROR: URL missing"
        )

        return False


    endpoint = (
        f"{IG_GRAPH}/me/messages"
    )


    payload = {

        "recipient": {
            "id": user_id
        },

        "messaging_type": "RESPONSE",

        "message": {

            "attachment": {

                "type": "video",

                "payload": {

                    "url": video_url

                }

            }

        }

    }


    response = meta_post(
        endpoint,
        payload
    )


    if response is None:
        return False


    if response.ok:

        print(
            "VIDEO SENT SUCCESSFULLY"
        )

        return True


    print(
        "VIDEO SEND FAILED:",
        response.status_code,
        response.text
    )

    return False


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return {
        "status": "online",
        "meta_version": META_VERSION
    }, 200


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=13833
    )