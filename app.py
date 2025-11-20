import os
import sqlite3
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# تنظیمات CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
DB_NAME = "mehrsa_clients.db"

# لینک‌های ضروری (لطفاً لینک کلندلی واقعی را جایگزین کنید)
BOOKING_URL = "https://calendly.com/mehrsasharoleslam"  # لینک کلندلی
WEBSITE_URL = "https://mehrsasharoleslam.com"
INSTAGRAM_URL = "https://www.instagram.com/mehrsasharoleslam"
YOUTUBE_URL = "https://www.youtube.com/@mehrsasharoleslam"

# اطلاعات مشاور
CONSULTANT_NAME = "Mehrsa Sharoleslam"
CONSULTANT_TITLE = {
    "en": "Luxury Business Advisor & Investment Consultant",
    "fa": "مشاور کسب‌وکارهای لوکس و سرمایه‌گذاری",
    "ar": "مستشارة الأعمال الفاخرة والاستثمار",
    "ru": "Советник по люксовому бизнесу и инвестициям"
}
LOCATION = "Dubai, United Arab Emirates"

# --- DATABASE ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            chat_id TEXT PRIMARY KEY,
            lang TEXT,
            name TEXT,
            phone TEXT,
            registration_date INTEGER,
            step TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_lead_state(chat_id, lang, name, phone, step):
    conn = get_db_connection()
    timestamp = int(time.time())
    cursor = conn.execute("SELECT * FROM leads WHERE chat_id = ?", (str(chat_id),))
    if cursor.fetchone():
        conn.execute("""
            UPDATE leads 
            SET lang=COALESCE(?, lang), name=COALESCE(?, name), phone=COALESCE(?, phone), step=? 
            WHERE chat_id=?
        """, (lang or None, name or None, phone or None, step, str(chat_id)))
    else:
        conn.execute("INSERT INTO leads (chat_id, lang, name, phone, registration_date, step) VALUES (?, ?, ?, ?, ?, ?)", 
                     (str(chat_id), lang, name, phone, timestamp, step))
    conn.commit()
    conn.close()

def load_lead_state(chat_id):
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM leads WHERE chat_id = ?", (str(chat_id),))
    row = cursor.fetchone()
    conn.close()
    if row: return dict(row)
    return {'step': 'awaiting_lang_selection', 'lang': None}

init_db()

# --- MENU OPTIONS ---
def get_main_menu_options(lang):
    if lang == 'fa': 
        return ["مشاوره بیزینس لوکس 💎", "سرمایه‌گذاری در امارات 🏙", "درباره مهرسا شرع‌الاسلام", "رزرو وقت مشاوره (Calendly)", "ارتباط با ما"]
    if lang == 'ar': 
        return ["استشارات الأعمال الفاخرة 💎", "الاستثمار في الإمارات 🏙", "عن مهرسا شرع الإسلام", "حجز موعد (Calendly)", "اتصل بنا"]
    if lang == 'ru': 
        return ["Люксовый бизнес-консалтинг 💎", "Инвестиции в ОАЭ 🏙", "О Mehrsa Sharoleslam", "Забронировать (Calendly)", "Контакты"]
    # Default English
    return ["Luxury Business Consulting 💎", "Investment in UAE 🏙", "About Mehrsa Sharoleslam", "Book Consultation (Calendly)", "Contact Us"]

# --- LOGIC ---
async def process_user_input(chat_id: str, text: str, responder_func):
    state = load_lead_state(chat_id)
    step = state.get('step')
    lang = state.get('lang')

    # 0. شروع / ریست
    if text in ["/start", "start", "شروع", "Start"]:
        save_lead_state(chat_id, '', '', '', 'awaiting_lang_selection')
        welcome_msg = (
            f"Welcome to <b>{CONSULTANT_NAME}</b>'s Official Bot 🌟\n"
            "Your Gateway to Luxury Business & Investment in Dubai.\n\n"
            "Please select your language / لطفاً زبان خود را انتخاب کنید:"
        )
        await responder_func(welcome_msg, options=["English (EN)", "فارسی (FA)", "العربية (AR)", "Русский (RU)"])
        return

    # 1. انتخاب زبان
    if step == 'awaiting_lang_selection':
        sel_lang = None
        if "EN" in text.upper(): sel_lang = "en"
        elif "FA" in text.upper() or "فارسی" in text: sel_lang = "fa"
        elif "AR" in text.upper() or "العربية" in text: sel_lang = "ar"
        elif "RU" in text.upper() or "РУССКИЙ" in text: sel_lang = "ru"

        if sel_lang:
            save_lead_state(chat_id, sel_lang, '', '', 'awaiting_name')
            prompt = {
                "en": "Thank you. Please enter your Full Name:",
                "fa": "سپاسگزارم. لطفاً نام و نام خانوادگی خود را وارد کنید:",
                "ar": "شكراً لك. الرجاء إدخال اسمك الكامل:",
                "ru": "Спасибо. Пожалуйста, введите ваше полное имя:"
            }[sel_lang]
            await responder_func(prompt)
        else:
            await responder_func("Please select a language:", options=["English (EN)", "فارسی (FA)"])
        return

    # 2. دریافت نام
    if step == 'awaiting_name':
        save_lead_state(chat_id, lang, text, '', 'awaiting_phone')
        prompt = {
            "en": f"Pleasure to meet you, {text}. To provide you with premium support, please share your WhatsApp number:",
            "fa": f"خوشبختم {text} عزیز. برای دریافت خدمات ویژه، لطفاً شماره واتساپ خود را ارسال کنید:",
            "ar": f"تشرفنا {text}. لتقديم دعم متميز، يرجى مشاركة رقم الواتساب:",
            "ru": f"Приятно познакомиться, {text}. Для предоставления премиум-поддержки укажите ваш номер WhatsApp:"
        }.get(lang, "Send phone:")
        await responder_func(prompt)
        return

    # 3. دریافت شماره و نمایش منو
    if step == 'awaiting_phone':
        save_lead_state(chat_id, lang, state.get('name'), text, 'main_menu')
        welcome = {
            "en": "Registration Complete. How can we assist you in scaling your business globally?",
            "fa": "ثبت نام تکمیل شد. چگونه می‌توانیم در جهانی‌سازی کسب‌وکارتان به شما کمک کنیم؟",
            "ar": "اكتمل التسجيل. كيف يمكننا مساعدتك في توسيع نطاق عملك عالمياً؟",
            "ru": "Регистрация завершена. Как мы можем помочь вам масштабировать бизнес?"
        }.get(lang, "Done.")
        await responder_func(welcome, options=get_main_menu_options(lang))
        return

    # 4. منوی اصلی
    if step == 'main_menu':
        
        # --- OPTION 1: LUXURY CONSULTING ---
        if any(x in text for x in ["Luxury", "لوکس", "الفاخرة", "Люксовый"]):
            msg_en = (
                "💎 <b>Luxury Business Consulting:</b>\n\n"
                "We specialize in helping brands enter the <b>Premium & Luxury Markets</b>.\n"
                "✅ Global Brand Positioning\n"
                "✅ High-Ticket Sales Strategy\n"
                "✅ Business Expansion to GCC\n\n"
                "<i>Let's build your world-class brand.</i>"
            )
            msg_fa = (
                "💎 <b>مشاوره کسب‌وکارهای لوکس:</b>\n\n"
                "تخصص ما کمک به ورود برندها به <b>بازارهای پریمیوم و لوکس</b> است.\n"
                "✅ جایگاه‌سازی برند در سطح جهانی\n"
                "✅ استراتژی فروش High-Ticket\n"
                "✅ توسعه کسب‌وکار در کشورهای حوزه خلیج فارس (GCC)\n\n"
                "<i>بیایید برند جهانی شما را بسازیم.</i>"
            )
            msg_ar = (
                "💎 <b>استشارات الأعمال الفاخرة:</b>\n\n"
                "نحن متخصصون في مساعدة العلامات التجارية على دخول <b>الأسواق الفاخرة</b>.\n"
                "✅ تحديد موقع العلامة التجارية عالمياً\n"
                "✅ استراتيجية المبيعات عالية القيمة\n"
                "✅ توسيع الأعمال في دول مجلس التعاون الخليجي"
            )
            msg_ru = (
                "💎 <b>Люксовый бизнес-консалтинг:</b>\n\n"
                "Мы помогаем брендам выйти на <b>рынки премиум-класса</b>.\n"
                "✅ Глобальное позиционирование бренда\n"
                "✅ Стратегия продаж с высоким чеком\n"
                "✅ Расширение бизнеса в страны Персидского залива"
            )
            
            content = {"en": msg_en, "fa": msg_fa, "ar": msg_ar, "ru": msg_ru}
            await responder_func(content.get(lang, msg_en), options=get_main_menu_options(lang))

        # --- OPTION 2: INVESTMENT ---
        elif any(x in text for x in ["Investment", "سرمایه‌گذاری", "الاستثمار", "Инвестиции"]):
            info_text = {
                "en": "🏙 <b>Investment in Dubai & UAE:</b>\n\nGuidance on profitable investment opportunities in Dubai's thriving market.\n- Real Estate\n- Business Setup\n- Golden Visa Services",
                "fa": "🏙 <b>سرمایه‌گذاری در دبی و امارات:</b>\n\nمشاوره تخصصی برای فرصت‌های سرمایه‌گذاری سودآور در بازار دبی.\n- املاک و مستغلات\n- ثبت شرکت و راه‌اندازی بیزینس\n- خدمات ویزای طلایی",
                "ar": "🏙 <b>الاستثمار في دبي والإمارات:</b>\n\nتوجيه حول فرص الاستثمار المربحة في سوق دبي المزدهر.\n- العقارات\n- تأسيس الشركات\n- خدمات الإقامة الذهبية",
                "ru": "🏙 <b>Инвестиции в Дубай и ОАЭ:</b>\n\nКонсультации по выгодным инвестиционным возможностям.\n- Недвижимость\n- Регистрация бизнеса\n- Золотая виза"
            }.get(lang, "")
            await responder_func(info_text, options=get_main_menu_options(lang))

        # --- OPTION 3: ABOUT MEHRSA ---
        elif any(x in text for x in ["About", "درباره", "عن", "О Mehrsa"]):
            title = CONSULTANT_TITLE.get(lang, CONSULTANT_TITLE["en"])
            about_text = (
                f"👤 <b>{CONSULTANT_NAME}</b>\n"
                f"<i>{title}</i>\n\n"
                f"📍 <b>Base:</b> {LOCATION}\n\n"
                f"🌐 <b>Website:</b> <a href='{WEBSITE_URL}'>mehrsasharoleslam.com</a>\n"
                f"📸 <b>Instagram:</b> <a href='{INSTAGRAM_URL}'>@mehrsasharoleslam</a>\n"
                f"🎥 <b>YouTube:</b> <a href='{YOUTUBE_URL}'>Channel</a>\n\n"
                "Helping you step into your power and build a global business."
            )
            await responder_func(about_text, options=get_main_menu_options(lang))

        # --- OPTION 4: BOOKING (CALENDLY) ---
        elif any(x in text for x in ["Book", "رزرو", "حجز", "Забронировать", "Calendly"]):
            msg = {
                "en": f"📅 <b>Book a VIP Consultation:</b>\n\nSelect a time that works for you directly via Calendly:\n👉 <a href='{BOOKING_URL}'>Click here to Book Appointment</a>",
                "fa": f"📅 <b>رزرو وقت مشاوره اختصاصی:</b>\n\nبرای تنظیم زمان جلسه آنلاین، از لینک زیر استفاده کنید:\n👉 <a href='{BOOKING_URL}'>کلیک برای رزرو در Calendly</a>",
                "ar": f"📅 <b>حجز استشارة VIP:</b>\n\nاختر الوقت المناسب لك مباشرة عبر Calendly:\n👉 <a href='{BOOKING_URL}'>اضغط هنا لحجز موعد</a>",
                "ru": f"📅 <b>Забронировать VIP-консультацию:</b>\n\nВыберите удобное время через Calendly:\n👉 <a href='{BOOKING_URL}'>Нажмите здесь для записи</a>"
            }.get(lang, "")
            await responder_func(msg, options=get_main_menu_options(lang))

        # --- OPTION 5: CONTACT ---
        elif any(x in text for x in ["Contact", "ارتباط", "اتصل", "Контакты"]):
            msg = {
                "en": f"📞 <b>Contact Us:</b>\n\nWhatsApp: +971565585649\nEmail: mehrsasharoleslam@gmail.com\n\nOur team is available 24/7 to assist global clients.",
                "fa": f"📞 <b>ارتباط با ما:</b>\n\nواتساپ: 971565585649+\nایمیل: mehrsasharoleslam@gmail.com\n\nتیم ما ۲۴ ساعته آماده پاسخگویی به مشتریان بین‌المللی است.",
                "ar": f"📞 <b>اتصل بنا:</b>\n\nواتساب: 971565585649+\nالبريد الإلكتروني: mehrsasharoleslam@gmail.com",
                "ru": f"📞 <b>Контакты:</b>\n\nWhatsApp: +971565585649\nEmail: mehrsasharoleslam@gmail.com"
            }.get(lang, "")
            await responder_func(msg, options=get_main_menu_options(lang))

        else:
            fallback = {
                "en": "Please select an option from the menu.",
                "fa": "لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
                "ar": "الرجاء اختيار خيار من القائمة.",
                "ru": "Пожалуйста, выберите опцию из меню."
            }.get(lang, "Please choose an option.")
            await responder_func(fallback, options=get_main_menu_options(lang))
        return

    # Default Fallback
    await responder_func("Type /start to restart.")

# --- ROUTES ---
@app.get("/")
async def root():
    return {"status": "ok", "message": "Mehrsa Luxury Business Bot is running"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    
    if not chat_id: return {"ok": True}
    
    async def telegram_responder(resp_text, options=None):
        payload = {
            "chat_id": chat_id, 
            "text": resp_text, 
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if options:
            payload["reply_markup"] = {"keyboard": [[{"text": o}] for o in options], "resize_keyboard": True}
        
        async with httpx.AsyncClient() as client:
            try:
                await client.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
            except Exception as e:
                print(f"Error sending message: {e}")
                
    await process_user_input(str(chat_id), text, telegram_responder)
    return {"ok": True}

class WebMessage(BaseModel):
    session_id: str
    message: str

@app.post("/web-chat")
async def web_chat(body: WebMessage):
    responses = []
    async def web_responder(resp_text, options=None):
        responses.append({"text": resp_text, "options": options or []})
    await process_user_input(body.session_id, body.message, web_responder)
    return {"messages": responses}
