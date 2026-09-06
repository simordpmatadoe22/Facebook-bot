# بوت Facebook Messenger ديال تحميل الفيديوهات

كيخدم هكا: المستخدم كيبعث فيديو (كمرفق مشارك) أو غير رابط فيديو فيسبوك عادي
(facebook.com/... أو fb.watch/...) فـ Messenger ديال الصفحة. البوت كيحمّل الفيديو
ويرجعو كملف mp4 (attachment قابل للتحميل) فنفس المحادثة.

## 1. شروط قبل ما تبدا

- صفحة Facebook (Page).
- حساب على [Meta for Developers](https://developers.facebook.com) وتطبيق (App) فيه
  منتوج **Messenger**.
- `PAGE_ACCESS_TOKEN` مولّد للصفحة ديالك بالصلاحيات: `pages_messaging`.
- الموافقة ديال Meta (App Review) باش تخدم مع مستخدمين حقيقيين خارج الـ Testers.

## 2. تثبيت المشروع محليا

```bash
python -m venv venv
source venv/bin/activate  # على Windows: venv\Scripts\activate
pip install -r requirements.txt
```

بلا ملف `.env`: القيم كتعطى مباشرة كـ environment variables فالـ terminal قبل
ما تشغل البوت:

```bash
export VERIFY_TOKEN=choose_any_random_string_you_want
export PAGE_ACCESS_TOKEN=your_page_access_token_from_meta
export APP_SECRET=your_meta_app_secret
export PAGE_ID=your_facebook_page_id
export GRAPH_API_VERSION=v21.0
```

على Windows (PowerShell)، بدل `export` استعمل `$env:VERIFY_TOKEN="..."`.

⚠️ محليا خاصك `ffmpeg` مثبت فالجهاز (`sudo apt install ffmpeg` / `brew install ffmpeg`)
باش يخدم `yt-dlp` مزيان. فالديبلوي بـ Docker، `ffmpeg` مزيد ليك فـ `Dockerfile`.

## 3. تجربة محلية + ngrok

```bash
python app.py
# فـ terminal آخر:
ngrok http 8000
```

## 4. ربط الـ Webhook فـ Meta

1. App Dashboard > Webhooks > Page، دخل:
   - **Callback URL**: `https://xxxx.ngrok-free.app/webhook`
   - **Verify Token**: نفس `VERIFY_TOKEN` ديال `.env`
2. اشترك فـ field **messages**.
3. اربط الصفحة ديالك مع التطبيق فـ Messenger Settings.

## 5. النشر — Back4App Containers (مجاني، بلا بطاقة بنكية)

الملف `Dockerfile` جاهز.

1. `git push` المشروع كامل لـ GitHub (بما فيه `Dockerfile`)
2. [back4app.com](https://www.back4app.com) > **Sign up** (بلا بطاقة)
3. **Containers** > **Create New App** > اختار الـ GitHub repo ديالك
4. Back4app غادي يبني الصورة تلقائيا من `Dockerfile`
5. فإعدادات الـ Container، زيد Environment Variables:
   `VERIFY_TOKEN`, `PAGE_ACCESS_TOKEN`, `APP_SECRET`, `PAGE_ID`, `GRAPH_API_VERSION`
6. بعد الديبلوي، الرابط غادي يكون بحال `https://your-app.back4app.io` — زيد `/webhook`
   وحطو فـ Meta Webhook settings

## ملاحظات مهمة

- **الفيديوهات المشتركة كمرفق**: الرابط جاي مباشر (signed) من CDN ديال Meta،
  البوت كيحمّلو بلا يحتاج `yt-dlp`.
- **الروابط المبعوتة كنص**: البوت كيستعمل `yt-dlp` باش يجلب الفيديو من صفحة
  فيسبوك عامة (public). الفيديوهات الخاصة أو المحدودة بمجموعة أصدقاء ماغاديش تخدم
  بلا تسجيل دخول (cookies)، وهاد الشي ماشي مدعوم هنا لأسباب أمنية.
- إيلا Meta بدّلت شكل webhook payload مع الوقت، شوف الـ logs باش تصاوب
  `MEDIA_ATTACHMENT_TYPES` أو الـ regex ديال الروابط.
- احترم قوانين الملكية الفكرية وشروط استخدام Facebook: هاد البوت مصمم لتحميل
  فيديوهات عامة أو اللي المستخدم شاركها بنفسو معاك، ماشي باش يسكرايب محتوى
  بلا إذن أو يوزع محتوى محمي بحقوق النشر.
