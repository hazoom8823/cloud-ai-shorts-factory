# مصنع الريلز السحابي — بدون Agent على الكمبيوتر

هذا المشروع يعمل داخل **GitHub Actions السحابي**؛ لا يحتاج Python أو FFmpeg أو أي Agent مثبتًا على جهازك. ارفع الملفات إلى مستودع GitHub من المتصفح فقط.

## ما الذي يفعله؟

1. Gemini يكتب قصة قصيرة عربية أصلية ويقسمها إلى 5 مشاهد.
2. Gemini TTS يولّد تعليقًا صوتيًا عربيًا.
3. Pexels API يبحث عن لقطات عمودية مجانية مناسبة لكل مشهد، ويضيف بيانات المصور والرابط.
4. FFmpeg على خادم GitHub يركّب الفيديو الرأسي 720×1280، ويضيف انتقالات Fade بين اللقطات وترجمة عربية مدمجة وHook افتتاحي.
5. YouTube Data API يرفع الفيديو إلى قناتك، مع ضبط الخصوصية على **Private افتراضيًا**.

**توضيح مهم:** هذه النسخة أوتوماتيكية ومجانية ضمن حدود الخطط المجانية، لكنها لا تصنع لقطات سينمائية جديدة بالكامل من النص؛ Gemini يكتب القصة وخطة المشاهد، ثم يختار النظام لقطات Stock من Pexels ويحررها. واجهات إنشاء فيديو حقيقي من النص عبر API التي تحققت منها لا تقدم خطة مجانية مستمرة موثقة. لا تستخدم هذا المشروع لتقديم لقطات Pexels على أنها مولّدة بالكامل بالذكاء الاصطناعي.

## المطلوب — كله من المتصفح

### 1) أنشئ مستودع GitHub

1. افتح https://github.com/new وأنشئ مستودعًا جديدًا. يجب أن يكون **Public** لاستخدام دقائق GitHub-hosted Actions المجانية دون اعتماد على استهلاك دقائق الخطة الخاصة.
2. من داخل المستودع اضغط **Add file → Upload files**، وارفع محتويات هذا المجلد، بما فيها المجلد المخفي `.github/workflows` وملف `src/creator.py`.
3. اضغط **Commit changes**.
4. افتح تبويب **Actions** وفعّل workflows عند ظهوره.

لا تضع أي API key داخل الملفات أو داخل سجل GitHub. كل المفاتيح تُحفظ في Secrets.

### 2) مفتاح Gemini المجاني

1. افتح https://aistudio.google.com/apikey وأنشئ API key.
2. هذا الـ API يستخدم نموذج النص `gemini-3.1-flash-lite` للصياغة ونموذج `gemini-3.8-flash-lite-tts` للصوت؛ كلاهما مدرج ضمن الفئة المجانية حاليًا، وفق حدود الحساب والاستخدام. الحدود والأسعار قد تتغير.

### 3) مفتاح Pexels المجاني

1. افتح https://www.pexels.com/api/ وسجّل الدخول.
2. أنشئ API key. الحدود الافتراضية المنشورة هي 200 طلب بالساعة و20,000 طلب بالشهر.
3. المشروع يضيف روابط اللقطات وأسماء المساهمين في وصف YouTube. اللقطات تُستخدم كمادة بصرية مركّبة وليست محتوى مستقلًا.

### 4) إعداد YouTube upload مرة واحدة

هذه أطول خطوة؛ مطلوبة لأن YouTube يحتاج موافقة OAuth صريحة من صاحب القناة.

1. افتح https://console.cloud.google.com/ وأنشئ مشروعًا جديدًا.
2. فعّل **YouTube Data API v3** للمشروع.
3. من **Google Auth Platform / OAuth consent screen**، جهز شاشة الموافقة. أضف حسابك كمستخدم اختبار إذا بقي التطبيق في وضع Testing.
4. أنشئ OAuth Client ID. نوع **Web application** مناسب لاستخدام OAuth Playground، وأضف عنوان إعادة التوجيه هذا حرفيًا ضمن Authorized redirect URIs:
   `https://developers.google.com/oauthplayground`
5. افتح https://developers.google.com/oauthplayground/ . من إعدادات OAuth (أيقونة الترس)، فعّل **Use your own OAuth credentials** وأدخل Client ID وClient Secret.
6. في Step 1 أدخل نطاق الصلاحية هذا:
   `https://www.googleapis.com/auth/youtube.upload`
   ثم اضغط Authorize APIs وسجّل الدخول بحساب القناة ووافق.
7. في Step 2 اضغط Exchange authorization code for tokens، وانسخ **Refresh token**. لا ترسله في المحادثة ولا تضعه في مستودع الملفات.
8. إذا Google رفض تسجيل الدخول بسبب حالة تطبيق OAuth، أكمل إعداد شاشة الموافقة وأضف حسابك كـ Test user. حسابات Testing قد تحتاج إعادة التفويض بعد فترة.

**ملاحظة:** مشاريع YouTube API غير المراجَعة قد تقيد الفيديوهات المرفوعة عبر API لتكون Private فقط. الرفع الخاص هو الاختبار الآمن الافتراضي، وقد يلزم تدقيق Google قبل أن يقبل النظام نشرًا عامًا من خلال API.

### 5) أضف المفاتيح إلى GitHub Secrets

في المستودع افتح **Settings → Secrets and variables → Actions → New repository secret** وأضف هذه الأسرار واحدًا واحدًا:

- `GEMINI_API_KEY` — مفتاح Google AI Studio.
- `PEXELS_API_KEY` — مفتاح Pexels.
- `YOUTUBE_CLIENT_ID` — OAuth Client ID.
- `YOUTUBE_CLIENT_SECRET` — OAuth Client Secret.
- `YOUTUBE_REFRESH_TOKEN` — Refresh token.

### 6) اضبط إعدادات التشغيل الاختيارية

من **Settings → Secrets and variables → Actions → Variables** يمكنك إضافة:

- `CHANNEL_TOPIC`: مثال `قصص غموض قصيرة بنهاية غير متوقعة` أو `حقائق علمية سهلة للمبتدئين`.
- `YOUTUBE_PRIVACY`: اتركها `private` للتجربة. لا تغيّرها إلى `public` قبل مراجعة فيديوهاتك والتأكد من أهلية مشروع YouTube API.
- `GEMINI_MODEL`: الافتراضي `gemini-3.1-flash-lite`.
- `TTS_MODEL`: الافتراضي `gemini-3.8-flash-lite-tts`.

لا تحتاج تضيف المتغيرات الاختيارية؛ يوجد لها إعداد افتراضي.

### 7) شغّل أول تجربة

1. افتح تبويب **Actions** ثم **Cloud AI Shorts Factory**.
2. اضغط **Run workflow** ثم أكّد.
3. افتح التشغيل الجديد وانتظر انتهاء كل الخطوات.
4. افتح رابط الفيديو في سجل التشغيل. ستجد أيضًا Artifact باسم `cloud-ai-shorts-output` يحتوي ملف الفيديو والبيانات لمدة 7 أيام.
5. راجع الفيديو في YouTube Studio. يظل خاصًا.

### الجدولة

بعد نجاح الاختبار، شغّل الـ workflow على الجدول اليومي المحدد في `.github/workflows/daily-short.yml`، الساعة 16:00 UTC. هذا يساوي 19:00 في القاهرة أثناء التوقيت الصيفي و18:00 بعد العودة للتوقيت الشتوي؛ عدّل سطر `cron` إذا كنت تريد ساعة محلية ثابتة.

## التكلفة والحدود

- GitHub-hosted runners: استخدم مستودعًا عامًا حتى لا تعتمد على حصة دقائق المستودعات الخاصة.
- Gemini script + TTS: مجانيان حاليًا ضمن حدود API المجانية؛ قد تختلف الحدود حسب المنطقة والحساب والضغط.
- Pexels API: مجاني ضمن الحدود المنشورة.
- YouTube upload API: لا توجد رسوم لكل رفع ضمن الحصة الافتراضية، لكنه يتطلب OAuth وحصة يومية.
- لا توجد هنا خدمة توليد مشاهد Text-to-Video حقيقية. إذا كان هذا شرطًا لا يمكن التنازل عنه، فلا أقدر أضمن أتمتة كاملة مجانية باستمرار باستخدام API موثوق من الخدمات التي تحققت منها.

## أعطال شائعة

- **429 من Gemini:** حدود مجانية مؤقتة؛ أعد التشغيل لاحقًا أو غيّر النموذج إلى نموذج متاح في الفئة المجانية.
- **Pexels no results:** غيّر `CHANNEL_TOPIC` أو أعد التشغيل. يجب تظل استعلامات البحث مناسبة للمشهد.
- **TTS model not found:** راجع نموذج TTS المتاح في Google AI Studio ثم غيّر متغير `TTS_MODEL`.
- **YouTube Unauthorized:** أعد إنشاء Refresh token بنفس Client ID وClient Secret والنطاق `youtube.upload`.
- **رفع عام لا يزال Private:** قد يكون المشروع غير مراجع لدى YouTube API؛ لا يمكن تجاوز هذا القيد من داخل السكريبت.

## الخصوصية والأمان

- لا تشارك GitHub Secrets مع أي شخص.
- المستودع Public يعني أن **الكود والتعليمات** عامة، لكن Secrets تظل مخفية عن قراء المستودع.
- سجلات Actions لا تطبع API keys عمدًا. لو نشرت سرًا بالخطأ، أبطله وأنشئ بديلًا فورًا.
- راجع كل فيديو قبل النشر العام، وتأكد من حقوق كل لقطة وسياسة المحتوى على YouTube.
