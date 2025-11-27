# copy rename to forwad للمعاينة
# await update.message.reply_text("اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:", reply_markup=reply_markup)
# دوال اشاعه الوساءط لا تعمل كلها فقط نصوص 2 عند ضغط زر حذف مراجعه ✍ اضهر جميع المراجعات اولا  بتنسيق مارق دون وبولد وبعده رسالة الوضع وعند الرجوع ان امكن تختفي لسته المراجعات
import sqlite3
import telegram
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ApplicationBuilder, MessageHandler, filters, ContextTypes
import datetime
import pytz
import asyncio

# تعريف التوقيت الخاص ببغداد
baghdad_tz = pytz.timezone('Asia/Baghdad')

# استبدال هذا بالتوكن الخاص بك
BOT_TOKEN = "8018952725:AAHHNmnaSfuG7xBk4hOepUKnuIejH9aOHVg"

# إنشاء أو فتح قاعدة البيانات
conn = sqlite3.connect('reviews.db', check_same_thread=False)
cursor = conn.cursor()

# إنشاء جدول للمراجعات إذا لم يكن موجودًا
cursor.execute('''
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    added_on TEXT NOT NULL,
    next_reviews TEXT NOT NULL
)
''')

# إضافة جدول لتخزين إعدادات التذكير لكل مستخدم
cursor.execute('''
CREATE TABLE IF NOT EXISTS reminders (
    user_id INTEGER PRIMARY KEY,
    reminder_time TEXT
)
''')
conn.commit()


# إنشاء/تحديث جدول الإعدادات
with sqlite3.connect('reviews.db') as conn:
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            sort_order TEXT DEFAULT 'alphabetical',
            color_contrast INTEGER DEFAULT 0
        )
    ''')
    # إضافة العمود إذا لم يكن موجوداً (للتوافق مع الإصدارات القديمة)
    try:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN color_contrast INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()


# متغيرات لتخزين حالة إدخال البيانات
awaiting_review_name = False
awaiting_review_date = False
current_review_name = ""



# جدول لحفظ الفترات المخصصة للمستخدمين
def create_user_intervals_table():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_intervals (
            user_id INTEGER PRIMARY KEY,
            intervals TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

# استدعاء الدالة لإنشاء الجدول
create_user_intervals_table()

# إنشاء جدول لتخزين معلومات الوسائط
def create_media_table():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            media_type TEXT NOT NULL,
            channel_message_id INTEGER NOT NULL,
            added_on TEXT NOT NULL,
            next_reviews TEXT NOT NULL,
            file_id TEXT,
            caption TEXT
        )
    """)
    conn.commit()

# استدعاء الدالة لإنشاء الجدول
create_media_table()
# إضافة عمود start_date إذا لم يكن موجود
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN start_date TEXT")
except sqlite3.OperationalError:
    pass

# إضافة عمود intervals إذا لم يكن موجود
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN intervals TEXT")
except sqlite3.OperationalError:
    pass

# إضافة عمود message_id إذا تحتاجه أيضًا
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN message_id INTEGER")
except sqlite3.OperationalError:
    pass

# إضافة عمود next_reviews (لو تستخدمه للتكرار المتباعد)
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN next_reviews TEXT")
except sqlite3.OperationalError:
    pass

conn.commit()
# الفترات الافتراضية (بالأيام)
default_intervals = [1, 4, 11, 25, 55, 85, 115, 145, 175, 205, 235, 265, 295, 325, 355]



# دالة لتحويل النص إلى دقائق
def parse_time_to_minutes(time_str):
    """تحويل النص مثل '1س 30د 45ث' أو '1h 30m 45s' إلى دقائق"""
    import re
    
    # أنماط للعربية والإنجليزية
    patterns = {
        'hours': [r'(\d+)س', r'(\d+)h'],
        'minutes': [r'(\d+)د', r'(\d+)m'],
        'seconds': [r'(\d+)ث', r'(\d+)s']
    }
    
    total_minutes = 0
    
    # البحث عن الساعات
    for pattern in patterns['hours']:
        match = re.search(pattern, time_str)
        if match:
            total_minutes += int(match.group(1)) * 60
    
    # البحث عن الدقائق
    for pattern in patterns['minutes']:
        match = re.search(pattern, time_str)
        if match:
            total_minutes += int(match.group(1))
    
    # البحث عن الثواني (تحويل إلى دقائق)
    for pattern in patterns['seconds']:
        match = re.search(pattern, time_str)
        if match:
            total_minutes += int(match.group(1)) / 60
    
    return total_minutes
def convert_intervals_to_minutes(intervals_str):
    """تحويل سلسلة الفترات إلى دقائق (محسنة مع معالجة أخطاء أفضل)"""
    intervals = []
    parts = intervals_str.split()
    
    for part in parts:
        try:
            # استخراج الأرقام من الجزء
            value = int(''.join(filter(str.isdigit, part)))
            
            # معالجة الوحدات
            if 'س' in part or 'h' in part.lower():
                intervals.append(value * 60)  # ساعات إلى دقائق
            elif 'د' in part or 'm' in part.lower():
                intervals.append(value)  # دقائق
            elif 'ث' in part or 's' in part.lower():
                intervals.append(value // 60)  # ثواني إلى دقائق
            elif part.isdigit():
                intervals.append(value * 24 * 60)  # أيام إلى دقائق
        except:
            continue
    
    # إذا لم يتم العثور على فترات صالحة، استخدام الفترات الافتراضية
    if not intervals:
        print("⚠️ استخدام الفترات الافتراضية بسبب عدم صحة الإدخال")
        return [1*24*60, 3*24*60, 7*24*60]  # 1, 3, 7 أيام
    
    return intervals
def add_review_with_custom_intervals(context, user_id, name, intervals, start_date=None, message_id=None, review_type='text'):
    import datetime  # تأكد أن المكتبة مستوردة
    print(f"📦 حفظ مراجعة نصية: {name} للمستخدم {user_id}")


    if start_date is None:
        start_date = datetime.datetime.now()

    if not isinstance(start_date, datetime.datetime):
        raise ValueError("start_date يجب أن يكون كائن datetime.datetime")

    # التحقق من صحة اسم المراجعة
    if not name or not isinstance(name, str) or name.strip() == "":
        raise ValueError("❌ اسم المراجعة لا يمكن أن يكون فارغاً")
    
    # تنظيف الاسم
    name = name.strip()
   
    # تحويل الفترات إلى دقائق
    try:
        if isinstance(intervals, str):
            interval_minutes = convert_intervals_to_minutes(intervals)
        else:
            interval_minutes = [interval * 24 * 60 for interval in intervals]
    except Exception as e:
        print(f"⚠️ خطأ في تحويل الفترات: {e}")
        interval_minutes = [1*24*60, 3*24*60, 7*24*60]  # فترات افتراضية

    # حساب أوقات المراجعات القادمة
    next_reviews = []
    for minutes in interval_minutes:
        next_review = start_date + datetime.timedelta(minutes=minutes)
        next_reviews.append(next_review.strftime("%Y-%m-%d %H:%M:%S"))

    next_reviews_str = ','.join(next_reviews)

    # حفظ في قاعدة البيانات
    try:
        added_on = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO reviews (user_id, name, intervals, start_date, message_id, next_reviews, added_on)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, intervals, start_date, message_id, next_reviews_str, added_on))
        conn.commit()

        # جدولة التذكيرات
        schedule_individual_reminders(
            context,
            user_id,
            name,
            next_reviews,
            review_type='media',
            channel_message_id=message_id  # ← هذا المتغير يجب أن يحتوي على رقم رسالة القناة إن كانت وسائط
        )

        print(f"✅ تم إضافة المراجعة بنجاح: {name}")

    except Exception as e:
        print(f"❌ خطأ في إضافة المراجعة إلى قاعدة البيانات: {e}")
        raise



# دالة لحفظ الفترات المخصصة للمستخدم
def save_user_intervals(user_id, intervals_str):
    """حفظ الفترات المخصصة للمستخدم"""
    cursor.execute("""
        INSERT OR REPLACE INTO user_intervals (user_id, intervals) 
        VALUES (?, ?)
    """, (user_id, intervals_str))
    conn.commit()


# دالة لجلب الفترات المخصصة للمستخدم
def get_user_intervals(user_id):
    """جلب الفترات المخصصة للمستخدم"""
    cursor.execute("SELECT intervals FROM user_intervals WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def schedule_individual_reminders(context, user_id, review_name, review_times, review_type='text', channel_message_id=None):
    """جدولة تذكيرات فردية لكل وقت مراجعة"""
    for i, review_time_str in enumerate(review_times):
        try:
            review_time = datetime.datetime.strptime(review_time_str.strip(), "%Y-%m-%d %H:%M:%S")
            current_time = datetime.datetime.now()
            
            # التحقق إذا كان الوقت في المستقبل
            if review_time > current_time:
                time_diff = review_time - current_time
                job_name = f"reminder_{user_id}_{review_name}_{i}"
                
                context.job_queue.run_once(
                    send_individual_reminder,
                    when=time_diff,
                    name=job_name,
                    chat_id=user_id,
                    data={
                        'review_name': review_name,
                        'review_time': review_time_str,
                        'review_type': review_type,
                        'channel_message_id': channel_message_id
                    }
                )
        except ValueError:
            continue



# دالة لإرسال التذكير الفردي
# دالة مُحدثة للتذكير الفردي مع دعم الوسائط
async def send_individual_reminder(context):
    """إرسال تذكير فردي مع دعم الوسائط"""
    job = context.job
    chat_id = job.chat_id
    data = job.data

    try:
        review_name = data['review_name']
        review_type = data.get('review_type', 'text')
        
        if review_type == 'media':
            channel_message_id = data.get('channel_message_id')
            if channel_message_id:
                # إرسال الوسائط من القناة
                success = await send_media_from_channel(context, chat_id, channel_message_id)
                if success:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"↑↑🔔 حان وقت المراجعة"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"↑↑🔔 حان وقت المراجعة\n❌ تعذر جلب الوسائط"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"↑↑🔔 حان وقت المراجعة"
                )
        else:
            # التذكير العادي للنص
            await context.bot.send_message(
                chat_id=chat_id,
                text="↑↑🔔 حان وقت المراجعة"
            )
    except Exception as e:
        print(f"Error sending individual reminder: {str(e)}")


# دالة لإظهار أزرار ضبط الفترات بالكيبورد العادي
async def show_interval_settings_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أزرار ضبط الفترات بالكيبورد العادي"""
    user_id = update.message.chat_id
    user_intervals = get_user_intervals(user_id)
    
    keyboard = [
        [KeyboardButton("رجوع للبداية"), KeyboardButton("رِجوع")],
        [KeyboardButton("الفترات الافتراضية")]
    ]
    
    if user_intervals:
        keyboard.append([KeyboardButton("فتراتي المخصصة")])
    
    keyboard.append([KeyboardButton("تخصيص جديد")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("اختر نوع الفترات:", reply_markup=reply_markup)

# دالة لإنشاء أزرار ضبط الفترات
async def show_interval_settings_buttons(update: Update):
    """عرض أزرار ضبط الفترات"""
    user_id = update.message.chat_id
    user_intervals = get_user_intervals(user_id)
    
    keyboard = [
        [InlineKeyboardButton("الفترات الافتراضية", callback_data="default_intervals")]
    ]
    
    if user_intervals:
        keyboard.append([InlineKeyboardButton("فتراتي المخصصة", callback_data="my_intervals")])
    
    keyboard.append([InlineKeyboardButton("تخصيص جديد", callback_data="customize_intervals")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


# دالة مساعدة لعرض أمثلة الاستخدام
async def show_usage_examples(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أمثلة الاستخدام للفترات الزمنية"""
    examples_text = """
🕐 أمثلة للفترات الزمنية:

**للأيام:**
`1 3 7 14 30`

**للساعات (عربي):**
`1س 6س 12س 24س`

**للساعات (إنجليزي):**
`1h 6h 12h 24h`

**للدقائق (عربي):**
`30د 60د 120د`

**للدقائق (إنجليزي):**
`30m 60m 120m`

**للثواني (عربي):**
`30ث 60ث 120ث`

**للثواني (إنجليزي):**
`30s 60s 120s`

**مختلط:**
`1س 3د 7 14 30`
`1h 30m 7 14 30`

📝 **ملاحظة:** يمكنك خلط الوحدات الزمنية في نفس الفترة!
    """
    
    await update.message.reply_text(examples_text, parse_mode='Markdown')
    """عرض أزرار ضبط الفترات"""
    user_id = update.message.chat_id
    user_intervals = get_user_intervals(user_id)
    
    keyboard = [
        [InlineKeyboardButton("الفترات الافتراضية", callback_data="default_intervals")]
    ]
    
    if user_intervals:
        keyboard.append([InlineKeyboardButton("فتراتي المخصصة", callback_data="my_intervals")])
    
    keyboard.append([InlineKeyboardButton("تخصيص جديد", callback_data="customize_intervals")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup



# الفترات الزمنية لنظام التكرار المتباعد (بالأيام)
spaced_repetition_intervals = [1, 4, 11, 25, 55, 85, 115, 145, 175, 205, 235, 265, 295, 325, 355]
# دالة الإيموجيات المُصححة
def get_review_emoji(added_on):
    """دالة تحديد الإيموجي حسب تاريخ الإضافة - مُصححة"""
    today = datetime.date.today()
    
    if isinstance(added_on, str):
        try:
            # محاولة تحويل التاريخ مع الوقت أولاً
            added_date = datetime.datetime.strptime(added_on, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            try:
                # إذا فشل، محاولة تحويل التاريخ فقط
                added_date = datetime.datetime.strptime(added_on, "%Y-%m-%d").date()
            except ValueError:
                # في حالة فشل التحويل، استخدام اليوم الحالي
                added_date = today
    else:
        added_date = added_on
    
    diff_days = (today - added_date).days
    
    # تحديد الفترة الحالية بدقة
    if diff_days < 1:  # لم يمر يوم بعد الإضافة
        return '🔴'  # دائرة خضراء (حالة خاصة)
    elif diff_days == 1:
        return '🔴'  # الفترة 1
    elif 2 <= diff_days <= 4:
        return '🟡'  # الفترة 4
    else:
        return '🟢'  # بقية الفترات


def get_yesterday_date():
    now = datetime.datetime.now(baghdad_tz)
    yesterday = now - datetime.timedelta(days=1)
    return yesterday.strftime("%d/%m/%Y")


async def show_back_button(update: Update):
    keyboard = [[KeyboardButton("رجوع")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return reply_markup

async def show_delete_all_buttons(update: Update):
    keyboard = [
        [KeyboardButton("نعم")],
        [KeyboardButton("رجوع للبداية"), KeyboardButton("رِجوع")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('هل أنت متأكد من حذف كل المراجعات؟', reply_markup=reply_markup)

# دالة لإضافة المراجعة إلى قاعدة البيانات
def add_review_to_spaced_repetition(user_id, review_name, review_date):
    next_reviews = [review_date + datetime.timedelta(days=interval) for interval in spaced_repetition_intervals]
    next_reviews_str = ','.join([str(date) for date in next_reviews])

    # إدراج المراجعة في قاعدة البيانات
    cursor.execute("INSERT INTO reviews (user_id, name, added_on, next_reviews) VALUES (?, ?, ?, ?)",
    (user_id, review_name, review_date, next_reviews_str))
    conn.commit()

# دالة لتخزين وقت التذكير لكل مستخدم
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    reminder_time = update.message.text  # الصيغة المتوقعة HH:MM
    cursor.execute("REPLACE INTO reminders (user_id, reminder_time) VALUES (?, ?)", (user_id, reminder_time))
    conn.commit()
    await update.message.reply_text(f"تم ضبط التذكير اليومي على {reminder_time}")




# دالة لإنشاء جدول الوسائط إذا لم يكن موجود
def create_media_reviews_table():
    """إنشاء جدول الوسائط إذا لم يكن موجود"""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                file_id TEXT NOT NULL,
                caption TEXT,
                channel_message_id INTEGER,
                added_on TEXT NOT NULL,
                next_reviews TEXT NOT NULL
            )
        """)
        conn.commit()
        print("✅ تم إنشاء جدول الوسائط بنجاح")
    except Exception as e:
        print(f"❌ خطأ في إنشاء جدول الوسائط: {e}")

# استدعاء الدالة لإنشاء الجدول
create_media_reviews_table()

# دالة لإلغاء العملية والعودة للوضع الطبيعي
async def cancel_operation(update: Update):
    await start(update, None)  # العودة إلى القائمة الرئيسية

# دالة لتقسيم الرسالة إلى أجزاء إذا كانت طويلة
def split_message(message, max_length=4000):
    return [message[i:i + max_length] for i in range(0, len(message), max_length)]

# دالة لعرض المراجعات مقسمة حسب الفترات الزمنية
async def show_revبعدiews(update: Update):
    user_id = update.message.chat_id
    cursor.execute("SELECT name, next_reviews FROM reviews WHERE user_id = ?", (user_id,))
    all_reviews = cursor.fetchall()

    if all_reviews:
        reviews_within_week = []
        reviews_within_month = []
        reviews_after_month = []
        today = datetime.date.today()

        for review in all_reviews:
            review_name, next_reviews_str = review
            next_reviews = next_reviews_str.split(',')
            for date_str in next_reviews:
                review_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                days_difference = (review_date - today).days

                if 0 <= days_difference <= 7:
                    reviews_within_week.append(f"{review_name} ({review_date})")
                elif 8 <= days_difference <= 30:
                    reviews_within_month.append(f"{review_name} ({review_date})")
                elif days_difference > 30:
                    reviews_after_month.append(f"{review_name} ({review_date})")

        message = ""
        if reviews_within_week:
            message += "مراجعات خلال الأسبوع القادم:\n" + "\n".join(reviews_within_week) + "\n\n"
        if reviews_within_month:
            message += "مراجعات خلال الشهر القادم:\n" + "\n".join(reviews_within_month) + "\n\n"
        if reviews_after_month:
            message += "مراجعات بعد أكثر من شهر:\n" + "\n".join(reviews_after_month)

        if message.strip():
            messages = split_message(message)
            for msg in messages:
                await update.message.reply_text(msg)
        else:
            await update.message.reply_text("لا توجد مراجعات مسجلة.")
    else:
        await update.message.reply_text("لا توجد مراجعات مسجلة.")

#مشكلة ازرار الادمن في البوت deepseek
async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جميع مراجعات المستخدم"""
    user_id = update.message.chat_id
    
    try:
        # الحصول على إعدادات المستخدم
        cursor.execute("SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?", (user_id,))
        settings = cursor.fetchone()
        
        if settings:
            order = settings[0]  # الترتيب: أبجدي أو زمني
            color_contrast = settings[1]  # تباين الألوان
        else:
            order = 'alphabetical'
            color_contrast = 0
        
        # جلب جميع المراجعات للمستخدم
        cursor.execute("""
            SELECT name, added_on, next_reviews 
            FROM reviews 
            WHERE user_id = ?
        """, (user_id,))
        
        all_reviews = cursor.fetchall()
        
        if all_reviews:
            # تحضير قائمة المراجعات
            reviews_list = []
            for review in all_reviews:
                name = review[0]
                
                # تنظيف الاسم من الرموز الخاصة
                clean_name = name.replace('<', '&lt;').replace('>', '&gt;')
                
                # معالجة تاريخ الإضافة
                try:
                    added_date = datetime.datetime.strptime(review[1], "%Y-%m-%d").strftime("%Y-%m-%d")
                except:
                    try:
                        added_date = datetime.datetime.strptime(review[1], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
                    except:
                        added_date = review[1]  # استخدام القيمة الأصلية
                
                # معالجة مواعيد المراجعات القادمة
                next_reviews = []
                for review_time_str in review[2].split(','):
                    stripped = review_time_str.strip()
                    try:
                        # محاولة تحويل للصياغة الزمنية الكاملة
                        dt = datetime.datetime.strptime(stripped, "%Y-%m-%d %H:%M:%S")
                        next_reviews.append(dt.strftime("%Y-%m-%d %H:%M"))
                    except ValueError:
                        try:
                            # محاولة الصيغة التاريخية فقط
                            dt = datetime.datetime.strptime(stripped, "%Y-%m-%d")
                            next_reviews.append(dt.strftime("%Y-%m-%d"))
                        except:
                            # استخدام القيمة الأصلية إذا فشل التحويل
                            next_reviews.append(stripped)
                
                reviews_list.append({
                    'name': clean_name,  # استخدام الاسم النظيف
                    'added_on': added_date,
                    'next_reviews': ", ".join(next_reviews)
                })
            
            # ترتيب المراجعات حسب الإعدادات
            if order == 'alphabetical':
                reviews_list.sort(key=lambda x: x['name'])
            else:  # الترتيب حسب تاريخ الإضافة
                reviews_list.sort(key=lambda x: x['added_on'], reverse=True)
            
            # تنسيق الرسالة بشكل أبسط
            message_lines = []
            for i, review in enumerate(reviews_list, 1):
                # استخدام تنسيق أبسط بدون علامات HTML معقدة
                message_lines.append(
                    f"{i}. {review['name']}"
                )
            
            message_text = "\n".join(message_lines)
            header = "📚 جميع مراجعاتك:\n\n"
            footer = f"\n📊 إجمالي المراجعات: {len(reviews_list)}"
            
            # تقسيم الرسالة إذا كانت طويلة
            full_message = header + message_text + footer
            if len(full_message) > 4096:
                parts = [full_message[i:i+4096] for i in range(0, len(full_message), 4096)]
                for part in parts:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_text(full_message)
        else:
            await update.message.reply_text("❌ لم تقم بإضافة أي مراجعات بعد.")
            
    except Exception as e:
        print(f"Error in show_reviews: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء جلب المراجعات. يرجى المحاولة لاحقاً.")


# دالة مُحدثة لعرض مراجعات اليوم مع دعم الوسائط
async def show_today_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    today = datetime.date.today()

    # الحصول على إعدادات المستخدم
    cursor.execute("SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?", (user_id,))
    settings = cursor.fetchone()

    if settings:
        order = settings[0]
        color_contrast = settings[1]
    else:
        order = 'alphabetical'
        color_contrast = 0

    # جلب المراجعات النصية
    base_query = "SELECT name, added_on FROM reviews WHERE user_id = ? AND next_reviews LIKE ?"
    if order == 'alphabetical':
        query = base_query + " ORDER BY name"
    else:
        query = base_query + " ORDER BY added_on DESC"

    cursor.execute(query, (user_id, f"%{today}%"))
    text_reviews = cursor.fetchall()

    # جلب المراجعات مع الوسائط
    media_query = "SELECT name, added_on, channel_message_id FROM media_reviews WHERE user_id = ? AND next_reviews LIKE ?"
    if order == 'alphabetical':
        media_query += " ORDER BY name"
    else:
        media_query += " ORDER BY added_on DESC"

    cursor.execute(media_query, (user_id, f"%{today}%"))
    media_reviews = cursor.fetchall()

    # دمج جميع المراجعات
    all_reviews = []

    for review in text_reviews:
        all_reviews.append({
            'name': review[0],
            'added_on': review[1],
            'type': 'text'
        })

    for review in media_reviews:
        all_reviews.append({
            'name': review[0],
            'added_on': review[1],
            'type': 'media',
            'channel_message_id': review[2]
        })

    if all_reviews:
        # ترتيب المراجعات
        if order == 'alphabetical':
            all_reviews.sort(key=lambda x: x['name'])
        else:
            all_reviews.sort(key=lambda x: x['added_on'], reverse=True)

        # تنسيق النص
        review_list = []
        for review in all_reviews:
            if color_contrast:
                emoji = get_review_emoji(review['added_on'])
                if review['type'] == 'media':
                    review_list.append(f"{emoji} {review['name']} 📎")
                else:
                    review_list.append(f"{emoji} {review['name']}")
            else:
                if review['type'] == 'media':
                    review_list.append(f"📎 {review['name']}")
                else:
                    review_list.append(f"• {review['name']}")

        review_text = "\n".join(review_list)
        await update.message.reply_text(f"مراجعات اليوم:\n{review_text}")

        # إرسال الوسائط مع رسالة توضيحية لكل مراجعة
        for review in media_reviews:
            await context.bot.send_message(chat_id=user_id, text=f"📎 إرسال مراجعة الوسائط: {review[0]}")
            await send_media_from_channel(context, user_id, review[2])
    else:
        await update.message.reply_text("لا توجد مراجعات مجدولة لهذا اليوم.")


async def show_delete_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    cursor.execute("SELECT name FROM reviews WHERE user_id = ?", (user_id,))
    reviews = cursor.fetchall()

    if reviews:
        buttons = [[InlineKeyboardButton(r[0], callback_data=f'delete_review_{r[0]}')] for r in reviews]
        split_button_groups = split_buttons(buttons)  # تقسيم الأزرار إلى مجموعات

        for group in split_button_groups:
            reply_markup = InlineKeyboardMarkup(group)
            await update.message.reply_text("اختر المراجعة التي تريد حذفها:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("لا توجد مراجعات لحذفها.")

def split_buttons(buttons, max_buttons_per_message=10):
    return [buttons[i:i + max_buttons_per_message] for i in range(0, len(buttons), max_buttons_per_message)]

def delete_text_review_from_db(review_name, user_id):
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.execute("DELETE FROM reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
        conn.commit()
        return True
    return False


def delete_media_review_from_db(review_name, user_id):
    cursor.execute("SELECT COUNT(*) FROM media_reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.execute("DELETE FROM media_reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
        conn.commit()
        return True
    return False


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [

        [KeyboardButton("حولَ"), KeyboardButton("رجوع")],
        [KeyboardButton("ترتيب مراجعات اليوم")],
        [KeyboardButton("ضبط تذكير المراجعة")],
        [KeyboardButton("ضبط الفترات الافتراضية")],
        [KeyboardButton("حذف كل المراجعات")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(':⚙ الأعدادات', reply_markup=reply_markup)


# دالة لعرض قائمة الإعدادات
async def how_show(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None):
    user_id = update.message.chat_id
    default_message = '⚙ إعدادات عرض المراجعات:'
    
    # جلب إعدادات المستخدم
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
    
    # تحديد الإعدادات الحالية
    if result:
        sort_order = result[0]
        color_contrast = result[1]
    else:
        sort_order = 'alphabetical'
        color_contrast = 0
    
    # بناء أزرار الفرز مع علامات الاختيار
    sort_buttons = []
    if sort_order == 'alphabetical':
        sort_buttons = [
            KeyboardButton("حسب الترتيب الابجدي ✅"),
            KeyboardButton("حسب الاحدث"),
        ]
        # بناء أزرار الفرز مع علامات الاختيار
    sort_buttons = []
    if sort_order == 'alphabetical':
        sort_buttons = [
            KeyboardButton("حسب الترتيب الابجدي\n✅"),
            KeyboardButton("حسب الاحدث"),
        ]
    else:
        sort_buttons = [
            KeyboardButton("حسب الترتيب الابجدي"),
            KeyboardButton("حسب الاحدث\n✅"),
        ]
    
    # بناء أزرار التباين مع علامات الاختيار
    contrast_buttons = []
    if color_contrast == 0:
        contrast_buttons = [
            KeyboardButton("الغاء التباين\n✅"),
            KeyboardButton("تباين المهمات بالالوان"),
        ]
    else:
        contrast_buttons = [
            KeyboardButton("الغاء التباين"),
            KeyboardButton("تباين المهمات بالالوان\n✅"),
        ]

    # بناء لوحة المفاتيح
    keyboard = [
        sort_buttons,
        contrast_buttons,
        [KeyboardButton("رجوع للبداية"), KeyboardButton("رِجوع")]
    ]
    
    # دمج الرسالة المخصصة مع الرسالة الافتراضية
    final_message = f"{message_text}\n\n{default_message}" if message_text else default_message
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(final_message, reply_markup=reply_markup)
# دالة لتحديث طريقة العرض

# 2. تعديل دالة update_sort_order
async def update_sort_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    text = update.message.text
    
    # إزالة علامة الاختيار إذا كانت موجودة في النص
    clean_text = text.replace(" ✅", "")
    
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        
        # تحديد الترتيب الجديد بناءً على النص
        new_sort_order = 'alphabetical' if clean_text == "حسب الترتيب الابجدي" else 'newest'
        
        # التحقق من وجود إعدادات سابقة
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # تحديث الترتيب مع الحفاظ على التباين
            cursor.execute('''
                UPDATE user_settings 
                SET sort_order = ? 
                WHERE user_id = ?
            ''', (new_sort_order, user_id))
        else:
            # إدراج جديد مع القيم الافتراضية
            cursor.execute('''
                INSERT INTO user_settings (user_id, sort_order, color_contrast)
                VALUES (?, ?, 0)
            ''', (user_id, new_sort_order))
        
        conn.commit()
    
    # إضافة علامة الاختيار إلى الزر المختار
    confirmation_text = f"✅ تم التحديث إلى: {clean_text}"
    await how_show(update, context, confirmation_text)

async def enable_color_contrast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_settings 
            SET color_contrast = 1 
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
    
    response_text = (
        "تم الأمر. سيظهر لون بجانب مراجعاتك حسب كل فترة:\n"
        "🔴 (يجب مراجعته«بعد يوم من إضافة المراجعة»)\n"
        "🟡 (مهم «بعد ٣ ايام»)\n"
        "🟢 (متوسط أو غير مهم «بعد اسبوع/كل شهر/كل سنه»)"
    )
    await how_show(update, context, response_text)

async def disable_color_contrast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_settings 
            SET color_contrast = 0 
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
    await how_show(update, context, "تم إلغاء التباين والعودة للنقاط العادية.")

async def send_media_reminder(context):
    """إرسال تذكير الوسائط مع إعادة التوجيه من القناة"""
    try:
        job_data = context.job.data
        user_id = job_data['user_id']
        review_name = job_data['review_name']
        channel_message_id = job_data['channel_message_id']
        review_number = job_data['review_number']

        # إرسال رسالة نصية أولاً كتذكير
        reminder_text = f"🔔 تذكير رقم {review_number} لمراجعة: {review_name}"
        await context.bot.send_message(chat_id=user_id, text=reminder_text)

        # إعادة توجيه الوسائط من القناة
        CHANNEL_ID = "@hsisig8757"  # ← تأكد أنه نفس القناة
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=CHANNEL_ID,
            message_id=channel_message_id
        )

        print(f"✅ تم إرسال الوسائط من القناة (رسالة #{channel_message_id}) للمستخدم {user_id}")

    except Exception as e:
        print(f"❌ خطأ في إرسال تذكير الوسائط: {e}")
        import traceback
        traceback.print_exc()



# دالة لعرض المراجعات أو العمليات مع زر /start
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.chat_id
    user_data = context.user_data
    
    user = update.message.from_user

    # تسجيل الدخول
    print(f"📩 رسالة واردة من: {user_id}")
    if text in ["رجوع", "رِجوع", "رجوع للبداية"]:
        # إعادة تعيين جميع الحالات
        awaiting_flags = [
            'awaiting_review_name',
            'awaiting_delete_review',
            'awaiting_manual_review_name',
            'awaiting_manual_intervals',
            'awaiting_review_name_with_date',
            'awaiting_reminder_time',
            'awaiting_review_date',
            'awaiting_custom_intervals'
        ]
        for flag in awaiting_flags:
            user_data[flag] = False
        
        # حذف البيانات المؤقتة
        temp_data_keys = ['current_review', 'current_review_name_with_date']
        for key in temp_data_keys:
            if key in user_data:
                del user_data[key]
        
        await start(update, context)
        return
       
    if user_data.get("awaiting_review_name"):
        file_message = update.message
        message_id = None

        # إعادة التوجيه للقناة
        try:
            forwarded = await context.bot.forward_message(
                chat_id=CHANNEL_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            message_id = forwarded.message_id
        except Exception as e:
            print(f"❌ خطأ في نسخ الوسائط إلى القناة: {e}")
 
        user_data['awaiting_review_name'] = False
        review_name = file_message.caption if file_message.caption else "."
        today = datetime.datetime.now()
        user_intervals = get_user_intervals(user_id)
        intervals_str = user_intervals if user_intervals else " ".join(map(str, default_intervals))
 
        # ⬇️ تسجيلها في قاعدة البيانات
        add_review_with_custom_intervals(context, user_id, review_name, intervals_str, today, message_id)
 
        # ✅ إرسال تأكيد للمستخدم
        await update.message.reply_text(f".تم تسجيل المراجعة بنظام التكرار المتباعد{review_name}")
 
        return

    
    # معالجة الرسائل النصية
    if update.message.text:
        text = update.message.text
        

    if text == "الاعدادات":
        await show_settings(update, context)
    elif text == "ترتيب مراجعات اليوم":
        await how_show(update, context)
    elif text in ["حسب الترتيب الابجدي", "حسب الاحدث"]:
        await update_sort_order(update, context)
    elif text == "تباين المهمات بالالوان":
        await enable_color_contrast(update, context)
    elif text == "الغاء التباين":
        await disable_color_contrast(update, context)

    # زر مراجعة (تلقائي)
    if text == "تكرار (متباعد)":
        user_data['awaiting_review_name'] = True
        user_data['current_mode'] = 'auto'
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:\n"
            "⚠ [أحذر تنشر أشياء خاصة](https://t.me/C4R4C/15826)",
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    
    # استقبال اسم المراجعة أو الوسائط
    elif user_data.get('awaiting_review_name', False):
        if text == "رجوع":
            user_data['awaiting_review_name'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        # التحقق من الفترات
        user_intervals = get_user_intervals(user_id)
        if user_intervals:
            intervals = user_intervals
        else:
            intervals = " ".join(map(str, default_intervals))
    
        today = datetime.datetime.now()
        mode = user_data.get('current_mode', 'auto')
    
        try:
            if update.message.photo or update.message.video or update.message.document or update.message.audio or update.message.voice:
                # 👇 نحدد نوع الوسائط
                file_id = None
                media_type = None
                if update.message.photo:
                    media_type = 'photo'
                    file_id = update.message.photo[-1].file_id
                elif update.message.video:
                    media_type = 'video'
                    file_id = update.message.video.file_id
                elif update.message.document:
                    media_type = 'document'
                    file_id = update.message.document.file_id
                elif update.message.audio:
                    media_type = 'audio'
                    file_id = update.message.audio.file_id
                elif update.message.voice:
                    media_type = 'voice'
                    file_id = update.message.voice.file_id
    
                review_name = update.message.caption or f"مراجعة {media_type} {today.strftime('%H:%M')}"
                review_name = review_name.strip()
    
                # تسجيل مراجعة الوسائط
                success = await add_media_review_with_custom_intervals(
                    context=context,
                    user_id=user_id,
                    review_name=review_name,
                    media_type=media_type,
                    file_id=file_id,
                    caption=review_name,
                    intervals=intervals,
                    start_date=today
                )
    
                if success:
                    await update.message.reply_text(f"✅ تم تسجيل مراجعة الوسائط: {review_name}")
                else:
                    await update.message.reply_text("❌ فشل تسجيل مراجعة الوسائط.")
            
            else:
                # مراجعة نصية
                if not text or text.strip() == "":
                    await update.message.reply_text("❌ اسم المراجعة لا يمكن أن يكون فارغاً.")
                    return
    
                review_name = text.strip()
                add_review_with_custom_intervals(context, user_id, review_name, intervals, today)
                await update.message.reply_text(f"✅ تم تسجيل مراجعة نصية: {review_name}")
    
            user_data['awaiting_review_name'] = False
            user_data['current_mode'] = None
    
        except Exception as e:
            print(f"❌ خطأ في مراجعة تلقائي: {e}")
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
    

    elif text == "حذف مراجعة":
        reply_markup = await show_back_button(update)
        await show_delete_buttons(update, context)

    elif text == "حذف مراجعة✍":
        user_data['awaiting_delete_review'] = True
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "✍️ وضع حذف المراجعات\n\n"
            "اكتب اسم المراجعة التي تريد حذفها:\n\n"
            "💡 يمكنك حذف عدة مراجعات متتالية\n"
            "❌ اضغط 'رجوع' للخروج من وضع الحذف",
            reply_markup=reply_markup
        )

    elif user_data.get('awaiting_delete_review', False):
        if text == "رجوع":
            user_data['awaiting_delete_review'] = False
            if is_admin(user):
                reply_markup = await show_admin_main_menu(update)
            else:
                reply_markup = await show_user_main_menu(update)
            await update.message.reply_text("تم الخروج من وضع حذف المراجعات.", reply_markup=reply_markup)
        else:
            if not text or text.strip() == "":
                await update.message.reply_text("❌ اسم المراجعة لا يمكن أن يكون فارغاً. الرجاء إدخال اسم صحيح:")
                return
    
            review_name = text.strip()
            user_id = update.message.chat_id
    
            # حذف من جدول المراجعات النصية
            deleted_text = delete_text_review_from_db(review_name, user_id)
    
            # حذف من جدول الوسائط
            deleted_media = delete_media_review_from_db(review_name, user_id)
    
            if deleted_text or deleted_media:
                await update.message.reply_text(f"✅ تم حذف المراجعة: {review_name}")
            else:
                await update.message.reply_text(f"❌ لا توجد مراجعة بهذا الاسم: {review_name}")

    # معالجة زر الرجوع
    elif text == "رجوع":
        # إعادة تعيين جميع الحالات
        user_data.clear()
        await start(update, context)

    elif user_data.get('awaiting_delete_review', False):
        user_data['awaiting_delete_review'] = False
        review_name = text
        delete_media_review_from_db(review_name, user_id)
        await update.message.reply_text(f"تم حذف المراجعة: {review_name}")

    # معالجة زر ضبط الفترات الافتراضية
    elif text == "ضبط الفترات الافتراضية":
        await show_interval_settings_keyboard(update, context)
# معالجة المراجعة اليدوية
    elif text == "مراجعة (يدوي)":
        user_data['awaiting_manual_review_name'] = True
        user_data['current_mode'] = 'manual'
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:\n"
            "⚠ [أحذر تنشر أشياء خاصة](https://t.me/C4R4C/15826)",
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    elif user_data.get('awaiting_manual_review_name', False):
        if text == "رجوع":
            user_data['awaiting_manual_review_name'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        message = update.message
    
        # إن كانت وسائط
        if message.photo or message.video or message.audio or message.voice or message.document:
            # استخراج نوع الوسائط وملفها
            if message.photo:
                media_type = 'photo'
                file_id = message.photo[-1].file_id
            elif message.video:
                media_type = 'video'
                file_id = message.video.file_id
            elif message.audio:
                media_type = 'audio'
                file_id = message.audio.file_id
            elif message.voice:
                media_type = 'voice'
                file_id = message.voice.file_id
            elif message.document:
                media_type = 'document'
                file_id = message.document.file_id
            else:
                await update.message.reply_text("❌ نوع الوسائط غير مدعوم.")
                return
    
            # إعادة توجيه الوسائط للقناة
            try:
                forwarded = await context.bot.copy_message(
                    chat_id=CHANNEL_ID,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                user_data['attached_message_id'] = forwarded.message_id
                user_data['attached_media_type'] = media_type
                user_data['attached_file_id'] = file_id
                user_data['current_review'] = message.caption or "مراجعة بدون اسم"
            except Exception as e:
                print(f"خطأ أثناء إعادة التوجيه: {e}")
                await update.message.reply_text("❌ فشل إرسال الوسائط إلى القناة.")
                return
    
        # إن كانت نص فقط
        else:
            user_data['current_review'] = text
    
        user_data['awaiting_manual_review_name'] = False
        user_data['awaiting_manual_intervals'] = True
        await update.message.reply_text("""
    اكتب الفترات الزمنية مفصولة بمسافات.
    
    أمثلة:
    • للأيام: `1 3 7 14 30`
    • للساعات: `1س 6س 12س 24س`
    • للدقائق: `30د 60د 120د`
    • للثواني: `30ث 60ث 120ث`
    • مختلط: `1س 3د 7 14 30`
    
    (يمكنك استخدام h/m/s بدلاً من س/د/ث)
        """, parse_mode='Markdown')
    
    elif user_data.get('awaiting_manual_intervals', False):
        if text == "رجوع":
            user_data['awaiting_manual_intervals'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        user_data['awaiting_manual_intervals'] = False
        intervals_str = text
        review_name = user_data.get('current_review', "مراجعة بدون اسم")
        channel_message_id = user_data.get('attached_message_id')
        media_type = user_data.get('attached_media_type')
        file_id = user_data.get('attached_file_id')
    
        try:
            # تسجيل مراجعة وسائط إن وجدت
            if channel_message_id and media_type and file_id:
                await add_media_review_with_custom_intervals(
                    context=context,
                    user_id=user_id,
                    review_name=review_name,
                    media_type=media_type,
                    file_id=file_id,
                    caption=review_name,
                    intervals=intervals_str,
                    start_date=datetime.datetime.now(),
                    channel_message_id=channel_message_id
                )
                cursor.execute("SELECT next_reviews FROM media_reviews WHERE user_id = ? AND name = ? ORDER BY id DESC LIMIT 1", (user_id, review_name))
            else:
                # مراجعة نصية
                add_review_with_custom_intervals(context, user_id, review_name, intervals_str)
                cursor.execute("SELECT next_reviews FROM reviews WHERE user_id = ? AND name = ? ORDER BY rowid DESC LIMIT 1", (user_id, review_name))
    
            result = cursor.fetchone()
            if result:
                review_times = result[0].split(',')
                schedule_individual_reminders(context, user_id, review_name, review_times,
                                            review_type='media' if channel_message_id else 'text',
                                            channel_message_id=channel_message_id)
    
            await update.message.reply_text(f"✅ تم تسجيل المراجعة بنظام يدوي: {review_name}")
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ أثناء تسجيل المراجعة: {e}")
        finally:
            user_data['current_mode'] = None
            user_data.pop('attached_message_id', None)
            user_data.pop('attached_media_type', None)
            user_data.pop('attached_file_id', None)
# زر مراجعة (بالتاريخ)
    elif text == "تكرار (تاريخ)":
        user_data['awaiting_review_name_with_date'] = True
        user_data['current_mode'] = 'date'
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:\n"
            "⚠ [أحذر تنشر أشياء خاصة](https://t.me/C4R4C/15826)",
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    elif user_data.get('awaiting_review_name_with_date', False):
        if text == "رجوع":
            user_data['awaiting_review_name_with_date'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        message = update.message
    
        if message.photo or message.video or message.audio or message.voice or message.document:
            # استخرج الوسائط
            if message.photo:
                media_type = 'photo'
                file_id = message.photo[-1].file_id
            elif message.video:
                media_type = 'video'
                file_id = message.video.file_id
            elif message.audio:
                media_type = 'audio'
                file_id = message.audio.file_id
            elif message.voice:
                media_type = 'voice'
                file_id = message.voice.file_id
            elif message.document:
                media_type = 'document'
                file_id = message.document.file_id
            else:
                await update.message.reply_text("❌ نوع الوسائط غير مدعوم.")
                return
    
            try:
                forwarded = await context.bot.copy_message(
                    chat_id=CHANNEL_ID,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                user_data['attached_message_id'] = forwarded.message_id
                user_data['attached_media_type'] = media_type
                user_data['attached_file_id'] = file_id
                user_data['current_review_name_with_date'] = message.caption or "مراجعة بدون اسم"
            except Exception as e:
                print(f"خطأ في التوجيه: {e}")
                await update.message.reply_text("❌ فشل إرسال الوسائط إلى القناة.")
                return
        else:
            user_data['current_review_name_with_date'] = text
    
        user_data['awaiting_review_name_with_date'] = False
        user_data['awaiting_review_date'] = True
        example_date = get_yesterday_date() if 'get_yesterday_date' in globals() else "10/07/2025"
        await update.message.reply_text(f"اكتب تاريخ المراجعة بالتنسيق (مثال: `{example_date}`):", parse_mode='Markdown')
    
    elif user_data.get('awaiting_review_date', False):
        if text == "رجوع":
            user_data['awaiting_review_date'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        try:
            selected_date = datetime.datetime.strptime(text, "%d/%m/%Y")
            review_name = user_data.get('current_review_name_with_date', "مراجعة بدون اسم")
            intervals_str = get_user_intervals(user_id) or " ".join(map(str, default_intervals))
            channel_message_id = user_data.get('attached_message_id')
            media_type = user_data.get('attached_media_type')
            file_id = user_data.get('attached_file_id')
    
            if channel_message_id and media_type and file_id:
                await add_media_review_with_custom_intervals(
                    context=context,
                    user_id=user_id,
                    review_name=review_name,
                    media_type=media_type,
                    file_id=file_id,
                    caption=review_name,
                    intervals=intervals_str,
                    start_date=selected_date,
                    channel_message_id=channel_message_id
                )
                cursor.execute("SELECT next_reviews FROM media_reviews WHERE user_id = ? AND name = ? ORDER BY id DESC LIMIT 1", (user_id, review_name))
            else:
                add_review_with_custom_intervals(context, user_id, review_name, intervals_str, selected_date)
                cursor.execute("SELECT next_reviews FROM reviews WHERE user_id = ? AND name = ? ORDER BY rowid DESC LIMIT 1", (user_id, review_name))
    
            result = cursor.fetchone()
            if result:
                review_times = result[0].split(',')
                schedule_individual_reminders(context, user_id, review_name, review_times,
                                              review_type='media' if channel_message_id else 'text',
                                              channel_message_id=channel_message_id)
    
            await update.message.reply_text(f"✅ تم تسجيل المراجعة: {review_name} بتاريخ {selected_date.strftime('%d/%m/%Y')}")
        except ValueError:
            await update.message.reply_text("❌ تنسيق التاريخ غير صحيح. استخدم التنسيق: يوم/شهر/سنة")
        finally:
            user_data['awaiting_review_date'] = False
            user_data['current_mode'] = None
            user_data.pop('attached_message_id', None)
            user_data.pop('attached_media_type', None)
            user_data.pop('attached_file_id', None)
    
        
    elif text == "حولَ":
        # إعادة تعيين كل الحالات المتعلقة بإدخال المراجعة
        user_data['awaiting_review_name_with_date'] = False
        user_data['awaiting_review_date'] = False
        user_data['current_review_name_with_date'] = ""
        await update.message.reply_text("أي مشكلة تواجهك بالبوت، تواصل هنا @REPETIHELPEBOT")

    # معالجة زر ضبط الفترات الافتراضية
    elif text == "ضبط الفترات الافتراضية":
        await show_interval_settings_keyboard(update, context)
    
    # معالجة أزرار الفترات
    elif text == "الفترات الافتراضية":
        intervals_text = " ".join(map(str, default_intervals))
        await update.message.reply_text(f"الفترات الافتراضية (بالأيام):\n\n`{intervals_text}`", parse_mode='Markdown')
    
    elif text == "فتراتي المخصصة":
        user_intervals = get_user_intervals(user_id)
        if user_intervals:
            await update.message.reply_text(f"فتراتك المخصصة:\n\n`{user_intervals}`", parse_mode='Markdown')
        else:
            await update.message.reply_text("لا توجد فترات مخصصة محفوظة.")
    
    elif text == "تخصيص جديد":
        user_data['awaiting_custom_intervals'] = True
        await update.message.reply_text("""
أدخل الفترات الزمنية الجديدة مفصولة بمسافات:

أمثلة:
• للأيام: `1 3 7 14 30`
• للساعات: `1س 6س 12س 24س`
• للدقائق: `30د 60د 120د`
• للثواني: `30ث 60ث 120ث`
• مختلط: `1س 3د 7 14 30`

(يمكنك استخدام h/m/s بدلاً من س/د/ث)
        """, parse_mode='Markdown')
    
    elif user_data.get('awaiting_custom_intervals', False):
        if text == "رجوع":
            user_data['awaiting_custom_intervals'] = False
            await start(update, context)
            return
        
        user_data['awaiting_custom_intervals'] = False
        intervals_str = text
        
        try:
            # التحقق من صحة الفترات
            convert_intervals_to_minutes(intervals_str)
            save_user_intervals(user_id, intervals_str)
            await update.message.reply_text(f"✅ تم حفظ فتراتك المخصصة: {intervals_str}")
            
            # إعادة عرض قائمة الفترات المحدثة
            await show_interval_settings_keyboard(update, context)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في تنسيق الفترات: {str(e)}")

    elif user_data.get('awaiting_custom_intervals', False):
        if text == "رجوع":
            user_data['awaiting_custom_intervals'] = False
            await start(update, context)
            return
        
        user_data['awaiting_custom_intervals'] = False
        intervals_str = text
        
        try:
            # التحقق من صحة الفترات
            convert_intervals_to_minutes(intervals_str)
            save_user_intervals(user_id, intervals_str)
            await update.message.reply_text(f"✅ تم حفظ فتراتك المخصصة: {intervals_str}")
            
            # إعادة عرض قائمة الفترات المحدثة
            await show_interval_settings_keyboard(update, context)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في تنسيق الفترات: {str(e)}")

    # معالجة زر مراجعات اليوم
    elif text == "مراجعات اليوم":
        await show_today_reviews(update, context)

    elif text == "ضبط تذكير المراجعة":
        user_data['awaiting_reminder_time'] = True
        reply_markup = await show_back_button(update)
        await update.message.reply_text(f"يرجى إدخال الوقت بالتنسيق HH:MM (مثال: `7:30`)",parse_mode='Markdown' ,reply_markup=reply_markup)
# استبدل الجزء الخاص بـ elif user_data.get('awaiting_reminder_time', False) بهذا الكود:
    elif user_data.get('awaiting_reminder_time', False):
        user_data['awaiting_reminder_time'] = False
        try:
            # إزالة أي تذكيرات سابقة للمستخدم
            current_jobs = context.job_queue.get_jobs_by_name(str(update.message.chat_id))
            for job in current_jobs:
                job.schedule_removal()

            # تحويل الوقت إلى توقيت بغداد
            reminder_time = datetime.datetime.strptime(text, '%H:%M').time()
            reminder_datetime = datetime.datetime.combine(datetime.date.today(), reminder_time)
            reminder_baghdad_time = baghdad_tz.localize(reminder_datetime).timetz()

            # تحديث قاعدة البيانات
            cursor.execute("""
                INSERT OR REPLACE INTO reminders (user_id, reminder_time) 
                VALUES (?, ?)
            """, (update.message.chat_id, text))
            conn.commit()

            # حذف التذكير القديم من قاعدة البيانات قبل إضافة الجديد
            cursor.execute("DELETE FROM reminders WHERE user_id = ?", (update.message.chat_id,))
            conn.commit()

            # إضافة التذكير الجديد
            cursor.execute("""
                INSERT INTO reminders (user_id, reminder_time) 
                VALUES (?, ?)
            """, (update.message.chat_id, text))
            conn.commit()

            # إضافة تذكير جديد
            context.job_queue.run_daily(
                send_daily_reminder,
                time=reminder_baghdad_time,
                name=str(update.message.chat_id),
                chat_id=update.message.chat_id,
                data={'user_id': update.message.chat_id}
            )

            await update.message.reply_text(f"تم ضبط التذكير اليومي عند الساعة {text}")
        except ValueError:
            await update.message.reply_text(f"الرجاء إدخال الوقت بالتنسيق الصحيح وبنظام 24 ساعه HH:MM (مثال: `7:30` بالصباح و`13:00` يعني بال1ظهراً)",parse_mode='Markdown')


    if text == "حذف كل المراجعات":
        await show_delete_all_buttons(update)
        return

    if text == "نعم":
        cursor.execute("DELETE FROM reviews WHERE user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text("تم حذف كل المراجعات.")
        await start(update, context)
        return

    elif text == "عرض المراجعات":
        await show_reviews(update, context)
    elif text == "حذف مراجعة":
        await show_delete_buttons(update, context)



    # معالجة أزرار الأدمن
    if is_admin(user):
        if text == "📢 إشاعة":
            await start_broadcast(update, context)
            return
        
        elif text == "👥 إحصائيات المستخدمين":
            await show_users_stats(update, context)
            return
        
        # الخروج من وضع الإشاعة
        elif text == "رجوع" and user_data.get('broadcast_mode', False):
            user_data['broadcast_mode'] = False
            reply_markup = await show_admin_main_menu(update)
            await update.message.reply_text("تم إلغاء وضع الإشاعة.", reply_markup=reply_markup)
            return
        
        # معالجة الرسائل في وضع الإشاعة
        elif user_data.get('broadcast_mode', False):
            # إشاعة النص
            if text:
                await broadcast_text(context, text, user_id)
                user_data['broadcast_mode'] = False
                reply_markup = await show_admin_main_menu(update)
                await update.message.reply_text("تم إنجاز الإشاعة!", reply_markup=reply_markup)
                return
    
    # هنا يتم استدعاء دالة معالجة الرسائل الأصلية

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"🔥 خطأ غير متوقع: {context.error}")
    import traceback
    traceback.print_exc()
    
    if update and hasattr(update, 'message'):
        await update.message.reply_text("❌ حدث خطأ غير متوقع، يرجى المحاولة لاحقاً")

# معالجة الأزرار المضمنة
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = context.user_data
    
    if query.data == "default_intervals":
        intervals_text = " ".join(map(str, default_intervals))
        await query.edit_message_text(f"الفترات الافتراضية (بالأيام):\n\n`{intervals_text}`", parse_mode='Markdown')
    
    elif query.data == "my_intervals":
        user_intervals = get_user_intervals(user_id)
        if user_intervals:
            await query.edit_message_text(f"فتراتك المخصصة:\n\n`{user_intervals}`", parse_mode='Markdown')
        else:
            await query.edit_message_text("لا توجد فترات مخصصة محفوظة.")
    
    elif query.data == "customize_intervals":
        user_data['awaiting_custom_intervals'] = True
        await query.edit_message_text("""
أدخل الفترات الزمنية الجديدة مفصولة بمسافات:

أمثلة:
• للأيام: `1 3 7 14 30`
• للساعات: `1س 6س 12س 24س`
• للدقائق: `30د 60د 120د`
• للثواني: `30ث 60ث 120ث`
• مختلط: `1س 3د 7 14 30`

(يمكنك استخدام h/m/s بدلاً من س/د/ث)
        """, parse_mode='Markdown')

# دالة محدثة لإضافة المراجعة التلقائية
def add_review_to_spaced_repetition_updated(context, user_id, review_name, review_date):
    """إضافة مراجعة بالنظام التلقائي مع الفترات المخصصة أو الافتراضية"""
    # محاولة الحصول على الفترات المخصصة للمستخدم
    user_intervals = get_user_intervals(user_id)
    
    if user_intervals:
        # استخدام الفترات المخصصة
        add_review_with_custom_intervals(context, user_id, review_name, user_intervals, review_date)
    else:
        # استخدام الفترات الافتراضية
        intervals_str = " ".join(map(str, default_intervals))
        add_review_with_custom_intervals(context, user_id, review_name, intervals_str, review_date)

# دالة محدثة لإضافة المراجعة بالتاريخ
def add_review_with_date_updated(context, user_id, review_name, review_date):
    """إضافة مراجعة بتاريخ محدد مع الفترات المخصصة أو الافتراضية"""
    add_review_to_spaced_repetition_updated(context, user_id, review_name, review_date)

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    print(f"🔔 Daily reminder triggered for user {chat_id}")

    try:
        with sqlite3.connect('reviews.db') as temp_conn:
            temp_cursor = temp_conn.cursor()
            current_time = datetime.datetime.now()

            temp_cursor.execute("""
                SELECT name, added_on, next_reviews, 'text' as type, NULL as channel_message_id
                FROM reviews
                WHERE user_id = ?
            """, (chat_id,))
            text_reviews = temp_cursor.fetchall()

            temp_cursor.execute("""
                SELECT name, added_on, next_reviews, 'media' as type, channel_message_id
                FROM media_reviews
                WHERE user_id = ?
            """, (chat_id,))
            media_reviews = temp_cursor.fetchall()

            all_reviews = list(text_reviews) + list(media_reviews)
            today_reviews = []

            for review in all_reviews:
                review_times = review[2].split(',')
                print(f"📋 مراجعة: {review[0]}، نوع: {review[3]}, channel_message_id: {review[4]}, أوقات المراجعة: {review_times}")
                for review_time_str in review_times:
                    try:
                        review_time = datetime.datetime.strptime(review_time_str.strip(), "%Y-%m-%d %H:%M:%S")
                        if review_time.date() == current_time.date():
                            print(f"✅ تمت مطابقة تاريخ اليوم للمراجعة: {review[0]} في {review_time}")
                            today_reviews.append({
                                'name': review[0],
                                'added_on': review[1],
                                'time': review_time,
                                'type': review[3],
                                'channel_message_id': review[4]
                            })
                            break
                    except ValueError:
                        if current_time.strftime("%Y-%m-%d") in review_time_str:
                            print(f"✅ تمت مطابقة تاريخ اليوم (بواسطة نص) للمراجعة: {review[0]} في {review_time_str}")
                            today_reviews.append({
                                'name': review[0],
                                'added_on': review[1],
                                'time': None,
                                'type': review[3],
                                'channel_message_id': review[4]
                            })
                            break
                    except ValueError:
                        if current_time.strftime("%Y-%m-%d") in review_time_str:
                            today_reviews.append({
                                'name': review[0],
                                'added_on': review[1],
                                'time': None,
                                'type': review[3],
                                'channel_message_id': review[4]
                            })
                            break

            if today_reviews:
                temp_cursor.execute("SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?", (chat_id,))
                settings = temp_cursor.fetchone()
                order = settings[0] if settings else 'alphabetical'
                color_contrast = settings[1] if settings else 0

                if order == 'alphabetical':
                    today_reviews.sort(key=lambda x: x['name'])
                else:
                    today_reviews.sort(key=lambda x: x['time'] or datetime.datetime.min)

                review_list = []
                media_to_send = []  # قائمة تحتوي على dict يحتوي اسم المراجعة و message_id
                for review in today_reviews:
                    emoji = get_review_emoji(review['added_on']) if color_contrast else ''
                    time_str = review['time'].strftime("%H:%M") if review['time'] else ''
                    
                    if review['type'] == 'media':
                        review_list.append(f"{emoji} {review['name']} 📎 {('- ' + time_str) if time_str else ''}")
                        
                        if review['channel_message_id']:
                            media_to_send.append({
                                'name': review['name'],
                                'message_id': review['channel_message_id']
                            })
                        else:
                            print(f"⚠️ ملاحظة: مراجعة وسائط بدون channel_message_id: {review['name']}")
                    
                    else:
                        review_list.append(f"{emoji} {review['name']} {('- ' + time_str) if time_str else ''}")
                
                review_text = "\n".join(review_list)
                await context.bot.send_message(chat_id=chat_id, text=f"تذكير اليوم هاي مراجعاتك :\n\n{review_text}")

                for media in media_to_send:
                    try:
                        print(f"🔔 إرسال وسائط '{media['name']}' من القناة (message_id: {media['message_id']}) إلى المستخدم {chat_id}")
                        await context.bot.copy_message(
                            chat_id=chat_id,
                            from_chat_id=CHANNEL_ID,
                            message_id=int(media['message_id'])
                        )
                    except Exception as e:
                        print(f"❌ فشل إرسال الوسائط '{media['name']}' إلى {chat_id}: {e}")


    except Exception as e:
        print(f"Error in daily reminder: {str(e)}")


# دالة استعادة التذكيرات المُصححة
async def restore_reminders(context: ContextTypes.DEFAULT_TYPE):
    """استعادة التذكيرات عند بدء التشغيل"""
    try:
        with sqlite3.connect('reviews.db') as temp_conn:
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("SELECT user_id, reminder_time FROM reminders")
            reminders = temp_cursor.fetchall()
        
        print(f"🔄 Restoring {len(reminders)} reminders...")
        
        for user_id, reminder_time in reminders:
            try:
                # إزالة أي تذكيرات موجودة مسبقاً
                current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
                for job in current_jobs:
                    job.schedule_removal()
                
                # تحويل وقت التذكير إلى كائن time
                time_obj = datetime.datetime.strptime(reminder_time, '%H:%M').time()
                
                # إنشاء تذكير يومي جديد
                job = context.job_queue.run_daily(
                    send_daily_reminder,
                    time=time_obj,
                    name=str(user_id),
                    chat_id=user_id,
                    data={'user_id': user_id}
                )
                
                print(f"✅ Restored reminder for user {user_id} at {reminder_time}")
                
            except Exception as e:
                print(f"❌ Error restoring reminder for user {user_id}: {str(e)}")
        
        print(f"🎯 Total active jobs: {len(context.job_queue.jobs())}")
        
    except Exception as e:
        print(f"❌ Error in restore_reminders: {str(e)}")


# دالة اختبار للتحقق من عمل التذكيرات
async def test_reminder_system(context: ContextTypes.DEFAULT_TYPE):
    """اختبار نظام التذكيرات"""
    try:
        with sqlite3.connect('reviews.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, reminder_time FROM reminders")
            reminders = cursor.fetchall()
            
            print(f"📊 Found {len(reminders)} reminders in database:")
            for user_id, reminder_time in reminders:
                print(f"   User {user_id}: {reminder_time}")
                
            # فحص الـ jobs النشطة
            active_jobs = context.job_queue.jobs()
            print(f"🔄 Active jobs: {len(active_jobs)}")
            for job in active_jobs:
                print(f"   Job: {job.name}, Next run: {job.next_t}")
                
    except Exception as e:
        print(f"❌ Error in test_reminder_system: {str(e)}")

# دالة لمعالجة التفاعل مع الأزرار (CallbackQueryHandler)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # معالجة حذف المراجعة
    if query.data.startswith('delete_review_'):
        review_name = query.data.replace('delete_review_', '')
        user_id = query.message.chat_id
        cursor.execute("DELETE FROM reviews WHERE user_id = ? AND name = ?", (user_id, review_name))
        conn.commit()
        await query.edit_message_text(f"تم حذف المراجعة: {review_name}")




# إعدادات القناة
CHANNEL_ID = "@hsisig8757"  # ضع معرف القناة هنا
async def send_media_to_channel(context, media_type, file_id, caption=None):
    print(f"📤 إرسال وسائط إلى القناة: {CHANNEL_ID}")
    """إرسال الوسائط إلى القناة (مُحسنة مع تصحيح الأخطاء)"""
    try:
        # تسجيل محاولة الإرسال
        print(f"🚀 محاولة إرسال {media_type} إلى القناة {CHANNEL_ID}")
        
        if media_type == 'photo':
            message = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=file_id,
                caption=caption
            )
        elif media_type == 'video':
            message = await context.bot.send_video(
                chat_id=CHANNEL_ID,
                video=file_id,
                caption=caption
            )
        elif media_type == 'audio':
            message = await context.bot.send_audio(
                chat_id=CHANNEL_ID,
                audio=file_id,
                caption=caption
            )
        elif media_type == 'voice':
            message = await context.bot.send_voice(
                chat_id=CHANNEL_ID,
                voice=file_id,
                caption=caption
            )
        elif media_type == 'document':
            message = await context.bot.send_document(
                chat_id=CHANNEL_ID,
                document=file_id,
                caption=caption
            )
        else:
            print(f"❌ نوع الوسائط غير مدعوم: {media_type}")
            return None
        
        # تسجيل النجاح
        print(f"✅ تم إرسال الوسائط إلى القناة! معرف الرسالة: {message.message_id}")
        return message.message_id
    
    except telegram.error.BadRequest as e:
        print(f"❌ خطأ في طلب التلغرام: {str(e)}")
        print(f"تفاصيل: {e.message}")
    except telegram.error.TimedOut:
        print("❌ انتهت مهلة الإرسال")
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {str(e)}")
    
    return None


# دالة لإضافة مراجعة الوسائط مع رفعها للقناة
async def add_media_review_with_custom_intervals(context, user_id, review_name, media_type, file_id, caption, intervals, start_date=None, channel_message_id=None):
    print(f"📦 حفظ مراجعة الوسائط: {review_name} للمستخدم {user_id} في {start_date.strftime('%Y-%m-%d %H:%M:%S')}")

    """إضافة مراجعة وسائط مع رفعها للقناة وحفظ رقم الرسالة"""
    try:
        if start_date is None:
            start_date = datetime.datetime.now()
        
        # التحقق من صحة اسم المراجعة
        if not review_name or review_name.strip() == "":
            review_name = f"مراجعة {media_type} {start_date.strftime('%H:%M')}"
        
        review_name = review_name.strip()
        
        # تحويل الفترات إلى دقائق
        try:
            if isinstance(intervals, str):
                interval_minutes = convert_intervals_to_minutes(intervals)
            else:
                interval_minutes = [interval * 24 * 60 for interval in intervals]
        except Exception as e:
            print(f"خطأ في تحويل الفترات: {e}")
            interval_minutes = [1*24*60, 3*24*60, 7*24*60]  # 1, 3, 7 أيام
        
        # حساب أوقات المراجعات القادمة
        next_reviews = []
        for minutes in interval_minutes:
            next_review = start_date + datetime.timedelta(minutes=minutes)
            next_reviews.append(next_review.strftime("%Y-%m-%d %H:%M:%S"))
        
        next_reviews_str = ','.join(next_reviews)
        
        # رفع الوسائط للقناة
        print(f"📤 رفع الوسائط للقناة: {media_type}")
        channel_message = None
        
        # تحديد معرف القناة (يجب أن يكون موجود في الكود الأصلي)
        CHANNEL_ID = "@hsisig8757"  # استبدل بمعرف قناتك
        
        try:
            # إرسال الوسائط حسب نوعها
            if media_type == 'photo':
                channel_message = await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'video':
                channel_message = await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'audio':
                channel_message = await context.bot.send_audio(
                    chat_id=CHANNEL_ID,
                    audio=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'voice':
                channel_message = await context.bot.send_voice(
                    chat_id=CHANNEL_ID,
                    voice=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'document':
                channel_message = await context.bot.send_document(
                    chat_id=CHANNEL_ID,
                    document=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'video_note':
                channel_message = await context.bot.send_video_note(
                    chat_id=CHANNEL_ID,
                    video_note=file_id
                )
            elif media_type == 'sticker':
                channel_message = await context.bot.send_sticker(
                    chat_id=CHANNEL_ID,
                    sticker=file_id
                )
            
            if channel_message:
                channel_message_id = channel_message.message_id
                print(f"✅ تم رفع الوسائط للقناة برقم: {channel_message_id}")
                
                # حفظ في قاعدة البيانات
                cursor.execute("""
                    INSERT INTO media_reviews (user_id, name, media_type, file_id, caption, channel_message_id, added_on, next_reviews)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, review_name, media_type, file_id, caption, channel_message_id, start_date.strftime("%Y-%m-%d %H:%M:%S"), next_reviews_str))
                conn.commit()
                
                return True
            else:
                print(f"❌ فشل في رفع الوسائط للقناة")
                return False
                
        except Exception as e:
            print(f"❌ خطأ في رفع الوسائط للقناة: {e}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ عام في إضافة مراجعة الوسائط: {e}")
        return False


async def send_media_from_channel(context, user_id, channel_message_id):
    try:
        print(f"إرسال وسائط من القناة {CHANNEL_ID} إلى المستخدم {user_id}، معرف الرسالة: {channel_message_id}")
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=CHANNEL_ID,
            message_id=channel_message_id,
            disable_notification=False
        )
        print("تم الإرسال بنجاح")
        return True
    except Exception as e:
        print(f"❌ خطأ في جلب الوسائط من القناة: {e}")
        return False


# دالة لجدولة تذكيرات الوسائط
def schedule_media_reminders(job_queue, user_id, review_name, review_times, channel_message_id):
    """جدولة تذكيرات الوسائط"""
    try:
        for i, time_str in enumerate(review_times):
            review_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            
            # التحقق من أن الوقت في المستقبل
            if review_time > datetime.datetime.now():
                job_queue.run_once(
                    send_media_reminder,
                    when=review_time,
                    data={
                        'user_id': user_id,
                        'review_name': review_name,
                        'channel_message_id': channel_message_id,
                        'review_number': i + 1
                    },
                    name=f"media_reminder_{user_id}_{review_name}_{i}"
                )
                print(f"📅 تم جدولة تذكير الوسائط: {review_name} في {time_str}")
    except Exception as e:
        print(f"❌ خطأ في جدولة تذكيرات الوسائط: {e}")







#إعدادات الأدمن
ADMIN_USERNAME = "Y_HOH0"  # ضع هنا اسم المستخدم الخاص بك بدون @

# جدول لحفظ جميع المستخدمين
def create_users_table():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()

# استدعاء إنشاء جدول المستخدمين
create_users_table()

# دالة لإضافة مستخدم جديد
def add_user(user_id, username=None, first_name=None, last_name=None):
    """إضافة مستخدم جديد أو تحديث بياناته"""
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, last_name))
    conn.commit()

# دالة للحصول على جميع المستخدمين النشطين
def get_all_active_users():
    """الحصول على جميع المستخدمين النشطين"""
    cursor.execute("SELECT user_id FROM users WHERE is_active = 1")
    return [row[0] for row in cursor.fetchall()]

# دالة لتعيين حالة المستخدم (نشط/غير نشط)
def set_user_status(user_id, is_active):
    """تحديث حالة المستخدم"""
    cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
    conn.commit()

# دالة للتحقق من الأدمن
def is_admin(user):
    """التحقق من صلاحيات الأدمن"""
    if hasattr(user, 'username') and user.username:
        return user.username.lower() == ADMIN_USERNAME.lower()
    return False

# دالة لعرض القائمة الرئيسية للأدمن
async def show_admin_main_menu(update: Update):
    """عرض القائمة الرئيسية للأدمن"""
    keyboard = [
        [KeyboardButton("تكرار (متباعد)"), KeyboardButton("مراجعة (يدوي)")],
        [KeyboardButton("عرض المراجعات"), KeyboardButton("مراجعات اليوم")],
        [KeyboardButton("تكرار (تاريخ)"), KeyboardButton("حذف مراجعة✍")],
        [KeyboardButton("ضبط تذكير المراجعة")],
        [KeyboardButton("الاعدادات")],
        [KeyboardButton("📢 إشاعة"), KeyboardButton("👥 إحصائيات المستخدمين")]  # أزرار الأدمن
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return reply_markup

# دالة لعرض القائمة الرئيسية للمستخدمين العاديين
async def show_user_main_menu(update: Update):
    """عرض القائمة الرئيسية للمستخدمين العاديين"""
    keyboard = [
        [KeyboardButton("تكرار (متباعد)"), KeyboardButton("مراجعة (يدوي)")],
        [KeyboardButton("عرض المراجعات"), KeyboardButton("مراجعات اليوم")],
        [KeyboardButton("تكرار (تاريخ)"), KeyboardButton("حذف مراجعة✍")],
        [KeyboardButton("الاعدادات")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return reply_markup

# دالة البداية المحدثة والموحدة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة البداية الموحدة مع التحقق من الأدمن"""
    global awaiting_review_name
    awaiting_review_name = False
    
    user_id = update.message.chat_id
    user = update.message.from_user
    
    # إضافة المستخدم إلى قاعدة البيانات
    add_user(user_id, user.username, user.first_name, user.last_name)
    
    # عرض القائمة المناسبة حسب نوع المستخدم
    if is_admin(user):
        reply_markup = await show_admin_main_menu(update)
        welcome_text = f"🔑 مرحباً بك أيها الأدمن @{user.username if user.username else 'Admin'}!\n\nنظام المراجعة المطور مع لوحة الإدارة\n\nاختر ما تريد فعله:"
    else:
        reply_markup = await show_user_main_menu(update)
        welcome_text = "مرحباً بك في نظام المراجعة المطور!\n\nاختر ما تريد فعله:"
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# دالة لبدء الإشاعة
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الإشاعة"""
    if not is_admin(update.message.from_user):
        await update.message.reply_text("❌ ليس لديك صلاحية للوصول لهذه الميزة.")
        return
    
    context.user_data['broadcast_mode'] = True
    
    keyboard = [
        [KeyboardButton("رجوع")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "📢 **وضع الإشاعة مفعل**\n\n"
        "أرسل الآن أي محتوى تريد إشاعته:\n\n"
        "• 📝 **نص عادي**\n"
        "• 🖼️ **صورة** (مع نص اختياري)\n"
        "• 🎬 **فيديو** (مع نص اختياري)\n"
        "• 🎵 **صوت/تسجيل صوتي** (مع نص اختياري)\n"
        "• 📄 **ملف** (مع نص اختياري)\n\n"
        "💡 **تلميح:** يمكنك استخدام تنسيق Markdown في النصوص",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# دالة لإرسال النص لجميع المستخدمين
async def broadcast_text(context: ContextTypes.DEFAULT_TYPE, message_text, admin_id):
    """إرسال نص لجميع المستخدمين"""
    users = get_all_active_users()
    sent_count = 0
    failed_count = 0
    blocked_users = []
    
    # إرسال رسالة بداية الإشاعة للأدمن
    await context.bot.send_message(
        chat_id=admin_id,
        text=f"🚀 بدء الإشاعة...\n👥 عدد المستخدمين: {len(users)}"
    )
    
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode='Markdown'
            )
            sent_count += 1
            
            # تأخير صغير لتجنب حدود التلجرام
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            
            # إذا كان المستخدم قد حظر البوت
            if "bot was blocked" in error_msg.lower() or "user is deactivated" in error_msg.lower():
                blocked_users.append(user_id)
                set_user_status(user_id, 0)  # تعيين المستخدم كغير نشط
    
    # إرسال تقرير الإشاعة للأدمن
    report = f"""
✅ **تم إنجاز الإشاعة!**

📊 **إحصائيات الإرسال:**
• ✅ تم الإرسال: {sent_count}
• ❌ فشل الإرسال: {failed_count}
• 🚫 المستخدمون الذين حظروا البوت: {len(blocked_users)}

📝 **المحتوى المرسل:**
{message_text[:100]}{'...' if len(message_text) > 100 else ''}
    """
    
    await context.bot.send_message(
        chat_id=admin_id,
        text=report,
        parse_mode='Markdown'
    )

# دالة لإرسال الوسائط لجميع المستخدمين
async def broadcast_media(context: ContextTypes.DEFAULT_TYPE, media_type, file_id, caption, admin_id):
    """إرسال وسائط لجميع المستخدمين"""
    users = get_all_active_users()
    sent_count = 0
    failed_count = 0
    blocked_users = []
    
    # إرسال رسالة بداية الإشاعة للأدمن
    await context.bot.send_message(
        chat_id=admin_id,
        text=f"🚀 بدء إشاعة {media_type}...\n👥 عدد المستخدمين: {len(users)}"
    )
    
    for user_id in users:
        try:
            if media_type == "photo":
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "video":
                await context.bot.send_video(
                    chat_id=user_id,
                    video=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "audio":
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "document":
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "voice":
                await context.bot.send_voice(
                    chat_id=user_id,
                    voice=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "video_note":
                await context.bot.send_video_note(
                    chat_id=user_id,
                    video_note=file_id
                )
            elif media_type == "sticker":
                await context.bot.send_sticker(
                    chat_id=user_id,
                    sticker=file_id
                )
            
            sent_count += 1
            
            # تأخير صغير لتجنب حدود التلجرام
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            
            # إذا كان المستخدم قد حظر البوت
            if "bot was blocked" in error_msg.lower() or "user is deactivated" in error_msg.lower():
                blocked_users.append(user_id)
                set_user_status(user_id, 0)  # تعيين المستخدم كغير نشط
    
    # إرسال تقرير الإشاعة للأدمن
    report = f"""
✅ **تم إنجاز إشاعة {media_type}!**

📊 **إحصائيات الإرسال:**
• ✅ تم الإرسال: {sent_count}
• ❌ فشل الإرسال: {failed_count}
• 🚫 المستخدمون الذين حظروا البوت: {len(blocked_users)}

📝 **النص المرفق:**
{caption[:100] if caption else 'لا يوجد نص'}{'...' if caption and len(caption) > 100 else ''}
    """
    
    await context.bot.send_message(
        chat_id=admin_id,
        text=report,
        parse_mode='Markdown'
    )

# دالة لعرض إحصائيات المستخدمين
async def show_users_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المستخدمين"""
    if not is_admin(update.message.from_user):
        await update.message.reply_text("❌ ليس لديك صلاحية للوصول لهذه الميزة.")
        return
    
    # الحصول على إحصائيات المستخدمين
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    active_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 0")
    inactive_users = cursor.fetchone()[0]
    
    # إحصائيات المراجعات
    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM reviews")
    users_with_reviews = cursor.fetchone()[0]
    
    # المستخدمون الجدد اليوم
    today = datetime.datetime.now().date()
    cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(join_date) = ?", (today,))
    new_users_today = cursor.fetchone()[0]
    
    # المستخدمون الجدد هذا الأسبوع
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (week_ago,))
    new_users_week = cursor.fetchone()[0]
    
    stats_text = f"""
📊 **إحصائيات المستخدمين**

👥 **العدد الإجمالي:** {total_users}
✅ **المستخدمون النشطون:** {active_users}
❌ **المستخدمون غير النشطون:** {inactive_users}

📚 **إحصائيات المراجعات:**
• إجمالي المراجعات: {total_reviews}
• المستخدمون الذين لديهم مراجعات: {users_with_reviews}

📈 **المستخدمون الجدد:**
• اليوم: {new_users_today}
• هذا الأسبوع: {new_users_week}

🗓️ **تاريخ التقرير:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
    """
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    print("🚀 Starting bot...")
    # إضافة استعادة التذكيرات عند بدء التشغيل
    app.job_queue.run_once(restore_reminders, when=2)

    app.add_handler(CommandHandler("start", start))
    
    # فلتر شامل لجميع أنواع الوسائط (متوافق مع جميع الإصدارات)
    media_filter = (
        filters.PHOTO |
        filters.VIDEO |
        filters.AUDIO |
        filters.VOICE |
        filters.Document.ALL |  # للمستندات
        filters.VIDEO_NOTE |
        filters.Sticker.ALL     # للملصقات
    )
    
    # إضافة معالج الأخطاء
    app.add_error_handler(error_handler)
    # فلتر شامل لجميع الرسائل
    app.add_handler(MessageHandler(~filters.COMMAND, handle_message))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🎯 Bot handlers added")
    print("⏰ Starting polling...")
    
    # بدء البوت
    app.run_polling()

if __name__ == "__main__":
    main()# copy rename to forwad للمعاينة
# await update.message.reply_text("اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:", reply_markup=reply_markup)
# دوال اشاعه الوساءط لا تعمل كلها فقط نصوص 2 عند ضغط زر حذف مراجعه ✍ اضهر جميع المراجعات اولا  بتنسيق مارق دون وبولد وبعده رسالة الوضع وعند الرجوع ان امكن تختفي لسته المراجعات
import sqlite3
import telegram
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ApplicationBuilder, MessageHandler, filters, ContextTypes
import datetime
import pytz
import asyncio

# تعريف التوقيت الخاص ببغداد
baghdad_tz = pytz.timezone('Asia/Baghdad')

# استبدال هذا بالتوكن الخاص بك
BOT_TOKEN = "8018952725:AAHHNmnaSfuG7xBk4hOepUKnuIejH9aOHVg"

# إنشاء أو فتح قاعدة البيانات
conn = sqlite3.connect('reviews.db', check_same_thread=False)
cursor = conn.cursor()

# إنشاء جدول للمراجعات إذا لم يكن موجودًا
cursor.execute('''
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    added_on TEXT NOT NULL,
    next_reviews TEXT NOT NULL
)
''')

# إضافة جدول لتخزين إعدادات التذكير لكل مستخدم
cursor.execute('''
CREATE TABLE IF NOT EXISTS reminders (
    user_id INTEGER PRIMARY KEY,
    reminder_time TEXT
)
''')
conn.commit()


# إنشاء/تحديث جدول الإعدادات
with sqlite3.connect('reviews.db') as conn:
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            sort_order TEXT DEFAULT 'alphabetical',
            color_contrast INTEGER DEFAULT 0
        )
    ''')
    # إضافة العمود إذا لم يكن موجوداً (للتوافق مع الإصدارات القديمة)
    try:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN color_contrast INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()


# متغيرات لتخزين حالة إدخال البيانات
awaiting_review_name = False
awaiting_review_date = False
current_review_name = ""



# جدول لحفظ الفترات المخصصة للمستخدمين
def create_user_intervals_table():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_intervals (
            user_id INTEGER PRIMARY KEY,
            intervals TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

# استدعاء الدالة لإنشاء الجدول
create_user_intervals_table()

# إنشاء جدول لتخزين معلومات الوسائط
def create_media_table():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            media_type TEXT NOT NULL,
            channel_message_id INTEGER NOT NULL,
            added_on TEXT NOT NULL,
            next_reviews TEXT NOT NULL,
            file_id TEXT,
            caption TEXT
        )
    """)
    conn.commit()

# استدعاء الدالة لإنشاء الجدول
create_media_table()
# إضافة عمود start_date إذا لم يكن موجود
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN start_date TEXT")
except sqlite3.OperationalError:
    pass

# إضافة عمود intervals إذا لم يكن موجود
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN intervals TEXT")
except sqlite3.OperationalError:
    pass

# إضافة عمود message_id إذا تحتاجه أيضًا
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN message_id INTEGER")
except sqlite3.OperationalError:
    pass

# إضافة عمود next_reviews (لو تستخدمه للتكرار المتباعد)
try:
    cursor.execute("ALTER TABLE reviews ADD COLUMN next_reviews TEXT")
except sqlite3.OperationalError:
    pass

conn.commit()
# الفترات الافتراضية (بالأيام)
default_intervals = [1, 4, 11, 25, 55, 85, 115, 145, 175, 205, 235, 265, 295, 325, 355]



# دالة لتحويل النص إلى دقائق
def parse_time_to_minutes(time_str):
    """تحويل النص مثل '1س 30د 45ث' أو '1h 30m 45s' إلى دقائق"""
    import re
    
    # أنماط للعربية والإنجليزية
    patterns = {
        'hours': [r'(\d+)س', r'(\d+)h'],
        'minutes': [r'(\d+)د', r'(\d+)m'],
        'seconds': [r'(\d+)ث', r'(\d+)s']
    }
    
    total_minutes = 0
    
    # البحث عن الساعات
    for pattern in patterns['hours']:
        match = re.search(pattern, time_str)
        if match:
            total_minutes += int(match.group(1)) * 60
    
    # البحث عن الدقائق
    for pattern in patterns['minutes']:
        match = re.search(pattern, time_str)
        if match:
            total_minutes += int(match.group(1))
    
    # البحث عن الثواني (تحويل إلى دقائق)
    for pattern in patterns['seconds']:
        match = re.search(pattern, time_str)
        if match:
            total_minutes += int(match.group(1)) / 60
    
    return total_minutes
def convert_intervals_to_minutes(intervals_str):
    """تحويل سلسلة الفترات إلى دقائق (محسنة مع معالجة أخطاء أفضل)"""
    intervals = []
    parts = intervals_str.split()
    
    for part in parts:
        try:
            # استخراج الأرقام من الجزء
            value = int(''.join(filter(str.isdigit, part)))
            
            # معالجة الوحدات
            if 'س' in part or 'h' in part.lower():
                intervals.append(value * 60)  # ساعات إلى دقائق
            elif 'د' in part or 'm' in part.lower():
                intervals.append(value)  # دقائق
            elif 'ث' in part or 's' in part.lower():
                intervals.append(value // 60)  # ثواني إلى دقائق
            elif part.isdigit():
                intervals.append(value * 24 * 60)  # أيام إلى دقائق
        except:
            continue
    
    # إذا لم يتم العثور على فترات صالحة، استخدام الفترات الافتراضية
    if not intervals:
        print("⚠️ استخدام الفترات الافتراضية بسبب عدم صحة الإدخال")
        return [1*24*60, 3*24*60, 7*24*60]  # 1, 3, 7 أيام
    
    return intervals
def add_review_with_custom_intervals(context, user_id, name, intervals, start_date=None, message_id=None, review_type='text'):
    import datetime  # تأكد أن المكتبة مستوردة
    print(f"📦 حفظ مراجعة نصية: {name} للمستخدم {user_id}")


    if start_date is None:
        start_date = datetime.datetime.now()

    if not isinstance(start_date, datetime.datetime):
        raise ValueError("start_date يجب أن يكون كائن datetime.datetime")

    # التحقق من صحة اسم المراجعة
    if not name or not isinstance(name, str) or name.strip() == "":
        raise ValueError("❌ اسم المراجعة لا يمكن أن يكون فارغاً")
    
    # تنظيف الاسم
    name = name.strip()
   
    # تحويل الفترات إلى دقائق
    try:
        if isinstance(intervals, str):
            interval_minutes = convert_intervals_to_minutes(intervals)
        else:
            interval_minutes = [interval * 24 * 60 for interval in intervals]
    except Exception as e:
        print(f"⚠️ خطأ في تحويل الفترات: {e}")
        interval_minutes = [1*24*60, 3*24*60, 7*24*60]  # فترات افتراضية

    # حساب أوقات المراجعات القادمة
    next_reviews = []
    for minutes in interval_minutes:
        next_review = start_date + datetime.timedelta(minutes=minutes)
        next_reviews.append(next_review.strftime("%Y-%m-%d %H:%M:%S"))

    next_reviews_str = ','.join(next_reviews)

    # حفظ في قاعدة البيانات
    try:
        added_on = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO reviews (user_id, name, intervals, start_date, message_id, next_reviews, added_on)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, intervals, start_date, message_id, next_reviews_str, added_on))
        conn.commit()

        # جدولة التذكيرات
        schedule_individual_reminders(
            context,
            user_id,
            name,
            next_reviews,
            review_type='media',
            channel_message_id=message_id  # ← هذا المتغير يجب أن يحتوي على رقم رسالة القناة إن كانت وسائط
        )

        print(f"✅ تم إضافة المراجعة بنجاح: {name}")

    except Exception as e:
        print(f"❌ خطأ في إضافة المراجعة إلى قاعدة البيانات: {e}")
        raise



# دالة لحفظ الفترات المخصصة للمستخدم
def save_user_intervals(user_id, intervals_str):
    """حفظ الفترات المخصصة للمستخدم"""
    cursor.execute("""
        INSERT OR REPLACE INTO user_intervals (user_id, intervals) 
        VALUES (?, ?)
    """, (user_id, intervals_str))
    conn.commit()


# دالة لجلب الفترات المخصصة للمستخدم
def get_user_intervals(user_id):
    """جلب الفترات المخصصة للمستخدم"""
    cursor.execute("SELECT intervals FROM user_intervals WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def schedule_individual_reminders(context, user_id, review_name, review_times, review_type='text', channel_message_id=None):
    """جدولة تذكيرات فردية لكل وقت مراجعة"""
    for i, review_time_str in enumerate(review_times):
        try:
            review_time = datetime.datetime.strptime(review_time_str.strip(), "%Y-%m-%d %H:%M:%S")
            current_time = datetime.datetime.now()
            
            # التحقق إذا كان الوقت في المستقبل
            if review_time > current_time:
                time_diff = review_time - current_time
                job_name = f"reminder_{user_id}_{review_name}_{i}"
                
                context.job_queue.run_once(
                    send_individual_reminder,
                    when=time_diff,
                    name=job_name,
                    chat_id=user_id,
                    data={
                        'review_name': review_name,
                        'review_time': review_time_str,
                        'review_type': review_type,
                        'channel_message_id': channel_message_id
                    }
                )
        except ValueError:
            continue



# دالة لإرسال التذكير الفردي
# دالة مُحدثة للتذكير الفردي مع دعم الوسائط
async def send_individual_reminder(context):
    """إرسال تذكير فردي مع دعم الوسائط"""
    job = context.job
    chat_id = job.chat_id
    data = job.data

    try:
        review_name = data['review_name']
        review_type = data.get('review_type', 'text')
        
        if review_type == 'media':
            channel_message_id = data.get('channel_message_id')
            if channel_message_id:
                # إرسال الوسائط من القناة
                success = await send_media_from_channel(context, chat_id, channel_message_id)
                if success:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"↑↑🔔 حان وقت المراجعة"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"↑↑🔔 حان وقت المراجعة\n❌ تعذر جلب الوسائط"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"↑↑🔔 حان وقت المراجعة"
                )
        else:
            # التذكير العادي للنص
            await context.bot.send_message(
                chat_id=chat_id,
                text="↑↑🔔 حان وقت المراجعة"
            )
    except Exception as e:
        print(f"Error sending individual reminder: {str(e)}")


# دالة لإظهار أزرار ضبط الفترات بالكيبورد العادي
async def show_interval_settings_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أزرار ضبط الفترات بالكيبورد العادي"""
    user_id = update.message.chat_id
    user_intervals = get_user_intervals(user_id)
    
    keyboard = [
        [KeyboardButton("رجوع للبداية"), KeyboardButton("رِجوع")],
        [KeyboardButton("الفترات الافتراضية")]
    ]
    
    if user_intervals:
        keyboard.append([KeyboardButton("فتراتي المخصصة")])
    
    keyboard.append([KeyboardButton("تخصيص جديد")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("اختر نوع الفترات:", reply_markup=reply_markup)

# دالة لإنشاء أزرار ضبط الفترات
async def show_interval_settings_buttons(update: Update):
    """عرض أزرار ضبط الفترات"""
    user_id = update.message.chat_id
    user_intervals = get_user_intervals(user_id)
    
    keyboard = [
        [InlineKeyboardButton("الفترات الافتراضية", callback_data="default_intervals")]
    ]
    
    if user_intervals:
        keyboard.append([InlineKeyboardButton("فتراتي المخصصة", callback_data="my_intervals")])
    
    keyboard.append([InlineKeyboardButton("تخصيص جديد", callback_data="customize_intervals")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


# دالة مساعدة لعرض أمثلة الاستخدام
async def show_usage_examples(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أمثلة الاستخدام للفترات الزمنية"""
    examples_text = """
🕐 أمثلة للفترات الزمنية:

**للأيام:**
`1 3 7 14 30`

**للساعات (عربي):**
`1س 6س 12س 24س`

**للساعات (إنجليزي):**
`1h 6h 12h 24h`

**للدقائق (عربي):**
`30د 60د 120د`

**للدقائق (إنجليزي):**
`30m 60m 120m`

**للثواني (عربي):**
`30ث 60ث 120ث`

**للثواني (إنجليزي):**
`30s 60s 120s`

**مختلط:**
`1س 3د 7 14 30`
`1h 30m 7 14 30`

📝 **ملاحظة:** يمكنك خلط الوحدات الزمنية في نفس الفترة!
    """
    
    await update.message.reply_text(examples_text, parse_mode='Markdown')
    """عرض أزرار ضبط الفترات"""
    user_id = update.message.chat_id
    user_intervals = get_user_intervals(user_id)
    
    keyboard = [
        [InlineKeyboardButton("الفترات الافتراضية", callback_data="default_intervals")]
    ]
    
    if user_intervals:
        keyboard.append([InlineKeyboardButton("فتراتي المخصصة", callback_data="my_intervals")])
    
    keyboard.append([InlineKeyboardButton("تخصيص جديد", callback_data="customize_intervals")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup



# الفترات الزمنية لنظام التكرار المتباعد (بالأيام)
spaced_repetition_intervals = [1, 4, 11, 25, 55, 85, 115, 145, 175, 205, 235, 265, 295, 325, 355]
# دالة الإيموجيات المُصححة
def get_review_emoji(added_on):
    """دالة تحديد الإيموجي حسب تاريخ الإضافة - مُصححة"""
    today = datetime.date.today()
    
    if isinstance(added_on, str):
        try:
            # محاولة تحويل التاريخ مع الوقت أولاً
            added_date = datetime.datetime.strptime(added_on, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            try:
                # إذا فشل، محاولة تحويل التاريخ فقط
                added_date = datetime.datetime.strptime(added_on, "%Y-%m-%d").date()
            except ValueError:
                # في حالة فشل التحويل، استخدام اليوم الحالي
                added_date = today
    else:
        added_date = added_on
    
    diff_days = (today - added_date).days
    
    # تحديد الفترة الحالية بدقة
    if diff_days < 1:  # لم يمر يوم بعد الإضافة
        return '🔴'  # دائرة خضراء (حالة خاصة)
    elif diff_days == 1:
        return '🔴'  # الفترة 1
    elif 2 <= diff_days <= 4:
        return '🟡'  # الفترة 4
    else:
        return '🟢'  # بقية الفترات


def get_yesterday_date():
    now = datetime.datetime.now(baghdad_tz)
    yesterday = now - datetime.timedelta(days=1)
    return yesterday.strftime("%d/%m/%Y")


async def show_back_button(update: Update):
    keyboard = [[KeyboardButton("رجوع")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return reply_markup

async def show_delete_all_buttons(update: Update):
    keyboard = [
        [KeyboardButton("نعم")],
        [KeyboardButton("رجوع للبداية"), KeyboardButton("رِجوع")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('هل أنت متأكد من حذف كل المراجعات؟', reply_markup=reply_markup)

# دالة لإضافة المراجعة إلى قاعدة البيانات
def add_review_to_spaced_repetition(user_id, review_name, review_date):
    next_reviews = [review_date + datetime.timedelta(days=interval) for interval in spaced_repetition_intervals]
    next_reviews_str = ','.join([str(date) for date in next_reviews])

    # إدراج المراجعة في قاعدة البيانات
    cursor.execute("INSERT INTO reviews (user_id, name, added_on, next_reviews) VALUES (?, ?, ?, ?)",
    (user_id, review_name, review_date, next_reviews_str))
    conn.commit()

# دالة لتخزين وقت التذكير لكل مستخدم
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    reminder_time = update.message.text  # الصيغة المتوقعة HH:MM
    cursor.execute("REPLACE INTO reminders (user_id, reminder_time) VALUES (?, ?)", (user_id, reminder_time))
    conn.commit()
    await update.message.reply_text(f"تم ضبط التذكير اليومي على {reminder_time}")




# دالة لإنشاء جدول الوسائط إذا لم يكن موجود
def create_media_reviews_table():
    """إنشاء جدول الوسائط إذا لم يكن موجود"""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                file_id TEXT NOT NULL,
                caption TEXT,
                channel_message_id INTEGER,
                added_on TEXT NOT NULL,
                next_reviews TEXT NOT NULL
            )
        """)
        conn.commit()
        print("✅ تم إنشاء جدول الوسائط بنجاح")
    except Exception as e:
        print(f"❌ خطأ في إنشاء جدول الوسائط: {e}")

# استدعاء الدالة لإنشاء الجدول
create_media_reviews_table()

# دالة لإلغاء العملية والعودة للوضع الطبيعي
async def cancel_operation(update: Update):
    await start(update, None)  # العودة إلى القائمة الرئيسية

# دالة لتقسيم الرسالة إلى أجزاء إذا كانت طويلة
def split_message(message, max_length=4000):
    return [message[i:i + max_length] for i in range(0, len(message), max_length)]

# دالة لعرض المراجعات مقسمة حسب الفترات الزمنية
async def show_revبعدiews(update: Update):
    user_id = update.message.chat_id
    cursor.execute("SELECT name, next_reviews FROM reviews WHERE user_id = ?", (user_id,))
    all_reviews = cursor.fetchall()

    if all_reviews:
        reviews_within_week = []
        reviews_within_month = []
        reviews_after_month = []
        today = datetime.date.today()

        for review in all_reviews:
            review_name, next_reviews_str = review
            next_reviews = next_reviews_str.split(',')
            for date_str in next_reviews:
                review_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                days_difference = (review_date - today).days

                if 0 <= days_difference <= 7:
                    reviews_within_week.append(f"{review_name} ({review_date})")
                elif 8 <= days_difference <= 30:
                    reviews_within_month.append(f"{review_name} ({review_date})")
                elif days_difference > 30:
                    reviews_after_month.append(f"{review_name} ({review_date})")

        message = ""
        if reviews_within_week:
            message += "مراجعات خلال الأسبوع القادم:\n" + "\n".join(reviews_within_week) + "\n\n"
        if reviews_within_month:
            message += "مراجعات خلال الشهر القادم:\n" + "\n".join(reviews_within_month) + "\n\n"
        if reviews_after_month:
            message += "مراجعات بعد أكثر من شهر:\n" + "\n".join(reviews_after_month)

        if message.strip():
            messages = split_message(message)
            for msg in messages:
                await update.message.reply_text(msg)
        else:
            await update.message.reply_text("لا توجد مراجعات مسجلة.")
    else:
        await update.message.reply_text("لا توجد مراجعات مسجلة.")

#مشكلة ازرار الادمن في البوت deepseek
async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جميع مراجعات المستخدم"""
    user_id = update.message.chat_id
    
    try:
        # الحصول على إعدادات المستخدم
        cursor.execute("SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?", (user_id,))
        settings = cursor.fetchone()
        
        if settings:
            order = settings[0]  # الترتيب: أبجدي أو زمني
            color_contrast = settings[1]  # تباين الألوان
        else:
            order = 'alphabetical'
            color_contrast = 0
        
        # جلب جميع المراجعات للمستخدم
        cursor.execute("""
            SELECT name, added_on, next_reviews 
            FROM reviews 
            WHERE user_id = ?
        """, (user_id,))
        
        all_reviews = cursor.fetchall()
        
        if all_reviews:
            # تحضير قائمة المراجعات
            reviews_list = []
            for review in all_reviews:
                name = review[0]
                
                # تنظيف الاسم من الرموز الخاصة
                clean_name = name.replace('<', '&lt;').replace('>', '&gt;')
                
                # معالجة تاريخ الإضافة
                try:
                    added_date = datetime.datetime.strptime(review[1], "%Y-%m-%d").strftime("%Y-%m-%d")
                except:
                    try:
                        added_date = datetime.datetime.strptime(review[1], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
                    except:
                        added_date = review[1]  # استخدام القيمة الأصلية
                
                # معالجة مواعيد المراجعات القادمة
                next_reviews = []
                for review_time_str in review[2].split(','):
                    stripped = review_time_str.strip()
                    try:
                        # محاولة تحويل للصياغة الزمنية الكاملة
                        dt = datetime.datetime.strptime(stripped, "%Y-%m-%d %H:%M:%S")
                        next_reviews.append(dt.strftime("%Y-%m-%d %H:%M"))
                    except ValueError:
                        try:
                            # محاولة الصيغة التاريخية فقط
                            dt = datetime.datetime.strptime(stripped, "%Y-%m-%d")
                            next_reviews.append(dt.strftime("%Y-%m-%d"))
                        except:
                            # استخدام القيمة الأصلية إذا فشل التحويل
                            next_reviews.append(stripped)
                
                reviews_list.append({
                    'name': clean_name,  # استخدام الاسم النظيف
                    'added_on': added_date,
                    'next_reviews': ", ".join(next_reviews)
                })
            
            # ترتيب المراجعات حسب الإعدادات
            if order == 'alphabetical':
                reviews_list.sort(key=lambda x: x['name'])
            else:  # الترتيب حسب تاريخ الإضافة
                reviews_list.sort(key=lambda x: x['added_on'], reverse=True)
            
            # تنسيق الرسالة بشكل أبسط
            message_lines = []
            for i, review in enumerate(reviews_list, 1):
                # استخدام تنسيق أبسط بدون علامات HTML معقدة
                message_lines.append(
                    f"{i}. {review['name']}"
                )
            
            message_text = "\n".join(message_lines)
            header = "📚 جميع مراجعاتك:\n\n"
            footer = f"\n📊 إجمالي المراجعات: {len(reviews_list)}"
            
            # تقسيم الرسالة إذا كانت طويلة
            full_message = header + message_text + footer
            if len(full_message) > 4096:
                parts = [full_message[i:i+4096] for i in range(0, len(full_message), 4096)]
                for part in parts:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_text(full_message)
        else:
            await update.message.reply_text("❌ لم تقم بإضافة أي مراجعات بعد.")
            
    except Exception as e:
        print(f"Error in show_reviews: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ أثناء جلب المراجعات. يرجى المحاولة لاحقاً.")


# دالة مُحدثة لعرض مراجعات اليوم مع دعم الوسائط
async def show_today_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    today = datetime.date.today()

    # الحصول على إعدادات المستخدم
    cursor.execute("SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?", (user_id,))
    settings = cursor.fetchone()

    if settings:
        order = settings[0]
        color_contrast = settings[1]
    else:
        order = 'alphabetical'
        color_contrast = 0

    # جلب المراجعات النصية
    base_query = "SELECT name, added_on FROM reviews WHERE user_id = ? AND next_reviews LIKE ?"
    if order == 'alphabetical':
        query = base_query + " ORDER BY name"
    else:
        query = base_query + " ORDER BY added_on DESC"

    cursor.execute(query, (user_id, f"%{today}%"))
    text_reviews = cursor.fetchall()

    # جلب المراجعات مع الوسائط
    media_query = "SELECT name, added_on, channel_message_id FROM media_reviews WHERE user_id = ? AND next_reviews LIKE ?"
    if order == 'alphabetical':
        media_query += " ORDER BY name"
    else:
        media_query += " ORDER BY added_on DESC"

    cursor.execute(media_query, (user_id, f"%{today}%"))
    media_reviews = cursor.fetchall()

    # دمج جميع المراجعات
    all_reviews = []

    for review in text_reviews:
        all_reviews.append({
            'name': review[0],
            'added_on': review[1],
            'type': 'text'
        })

    for review in media_reviews:
        all_reviews.append({
            'name': review[0],
            'added_on': review[1],
            'type': 'media',
            'channel_message_id': review[2]
        })

    if all_reviews:
        # ترتيب المراجعات
        if order == 'alphabetical':
            all_reviews.sort(key=lambda x: x['name'])
        else:
            all_reviews.sort(key=lambda x: x['added_on'], reverse=True)

        # تنسيق النص
        review_list = []
        for review in all_reviews:
            if color_contrast:
                emoji = get_review_emoji(review['added_on'])
                if review['type'] == 'media':
                    review_list.append(f"{emoji} {review['name']} 📎")
                else:
                    review_list.append(f"{emoji} {review['name']}")
            else:
                if review['type'] == 'media':
                    review_list.append(f"📎 {review['name']}")
                else:
                    review_list.append(f"• {review['name']}")

        review_text = "\n".join(review_list)
        await update.message.reply_text(f"مراجعات اليوم:\n{review_text}")

        # إرسال الوسائط مع رسالة توضيحية لكل مراجعة
        for review in media_reviews:
            await context.bot.send_message(chat_id=user_id, text=f"📎 إرسال مراجعة الوسائط: {review[0]}")
            await send_media_from_channel(context, user_id, review[2])
    else:
        await update.message.reply_text("لا توجد مراجعات مجدولة لهذا اليوم.")


async def show_delete_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    cursor.execute("SELECT name FROM reviews WHERE user_id = ?", (user_id,))
    reviews = cursor.fetchall()

    if reviews:
        buttons = [[InlineKeyboardButton(r[0], callback_data=f'delete_review_{r[0]}')] for r in reviews]
        split_button_groups = split_buttons(buttons)  # تقسيم الأزرار إلى مجموعات

        for group in split_button_groups:
            reply_markup = InlineKeyboardMarkup(group)
            await update.message.reply_text("اختر المراجعة التي تريد حذفها:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("لا توجد مراجعات لحذفها.")

def split_buttons(buttons, max_buttons_per_message=10):
    return [buttons[i:i + max_buttons_per_message] for i in range(0, len(buttons), max_buttons_per_message)]

def delete_text_review_from_db(review_name, user_id):
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.execute("DELETE FROM reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
        conn.commit()
        return True
    return False


def delete_media_review_from_db(review_name, user_id):
    cursor.execute("SELECT COUNT(*) FROM media_reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.execute("DELETE FROM media_reviews WHERE name = ? AND user_id = ?", (review_name, user_id))
        conn.commit()
        return True
    return False


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [

        [KeyboardButton("حولَ"), KeyboardButton("رجوع")],
        [KeyboardButton("ترتيب مراجعات اليوم")],
        [KeyboardButton("ضبط تذكير المراجعة")],
        [KeyboardButton("ضبط الفترات الافتراضية")],
        [KeyboardButton("حذف كل المراجعات")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(':⚙ الأعدادات', reply_markup=reply_markup)


# دالة لعرض قائمة الإعدادات
async def how_show(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None):
    user_id = update.message.chat_id
    default_message = '⚙ إعدادات عرض المراجعات:'
    
    # جلب إعدادات المستخدم
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
    
    # تحديد الإعدادات الحالية
    if result:
        sort_order = result[0]
        color_contrast = result[1]
    else:
        sort_order = 'alphabetical'
        color_contrast = 0
    
    # بناء أزرار الفرز مع علامات الاختيار
    sort_buttons = []
    if sort_order == 'alphabetical':
        sort_buttons = [
            KeyboardButton("حسب الترتيب الابجدي ✅"),
            KeyboardButton("حسب الاحدث"),
        ]
        # بناء أزرار الفرز مع علامات الاختيار
    sort_buttons = []
    if sort_order == 'alphabetical':
        sort_buttons = [
            KeyboardButton("حسب الترتيب الابجدي\n✅"),
            KeyboardButton("حسب الاحدث"),
        ]
    else:
        sort_buttons = [
            KeyboardButton("حسب الترتيب الابجدي"),
            KeyboardButton("حسب الاحدث\n✅"),
        ]
    
    # بناء أزرار التباين مع علامات الاختيار
    contrast_buttons = []
    if color_contrast == 0:
        contrast_buttons = [
            KeyboardButton("الغاء التباين\n✅"),
            KeyboardButton("تباين المهمات بالالوان"),
        ]
    else:
        contrast_buttons = [
            KeyboardButton("الغاء التباين"),
            KeyboardButton("تباين المهمات بالالوان\n✅"),
        ]

    # بناء لوحة المفاتيح
    keyboard = [
        sort_buttons,
        contrast_buttons,
        [KeyboardButton("رجوع للبداية"), KeyboardButton("رِجوع")]
    ]
    
    # دمج الرسالة المخصصة مع الرسالة الافتراضية
    final_message = f"{message_text}\n\n{default_message}" if message_text else default_message
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(final_message, reply_markup=reply_markup)
# دالة لتحديث طريقة العرض

# 2. تعديل دالة update_sort_order
async def update_sort_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    text = update.message.text
    
    # إزالة علامة الاختيار إذا كانت موجودة في النص
    clean_text = text.replace(" ✅", "")
    
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        
        # تحديد الترتيب الجديد بناءً على النص
        new_sort_order = 'alphabetical' if clean_text == "حسب الترتيب الابجدي" else 'newest'
        
        # التحقق من وجود إعدادات سابقة
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # تحديث الترتيب مع الحفاظ على التباين
            cursor.execute('''
                UPDATE user_settings 
                SET sort_order = ? 
                WHERE user_id = ?
            ''', (new_sort_order, user_id))
        else:
            # إدراج جديد مع القيم الافتراضية
            cursor.execute('''
                INSERT INTO user_settings (user_id, sort_order, color_contrast)
                VALUES (?, ?, 0)
            ''', (user_id, new_sort_order))
        
        conn.commit()
    
    # إضافة علامة الاختيار إلى الزر المختار
    confirmation_text = f"✅ تم التحديث إلى: {clean_text}"
    await how_show(update, context, confirmation_text)

async def enable_color_contrast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_settings 
            SET color_contrast = 1 
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
    
    response_text = (
        "تم الأمر. سيظهر لون بجانب مراجعاتك حسب كل فترة:\n"
        "🔴 (يجب مراجعته«بعد يوم من إضافة المراجعة»)\n"
        "🟡 (مهم «بعد ٣ ايام»)\n"
        "🟢 (متوسط أو غير مهم «بعد اسبوع/كل شهر/كل سنه»)"
    )
    await how_show(update, context, response_text)

async def disable_color_contrast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    with sqlite3.connect('reviews.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_settings 
            SET color_contrast = 0 
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
    await how_show(update, context, "تم إلغاء التباين والعودة للنقاط العادية.")

async def send_media_reminder(context):
    """إرسال تذكير الوسائط مع إعادة التوجيه من القناة"""
    try:
        job_data = context.job.data
        user_id = job_data['user_id']
        review_name = job_data['review_name']
        channel_message_id = job_data['channel_message_id']
        review_number = job_data['review_number']

        # إرسال رسالة نصية أولاً كتذكير
        reminder_text = f"🔔 تذكير رقم {review_number} لمراجعة: {review_name}"
        await context.bot.send_message(chat_id=user_id, text=reminder_text)

        # إعادة توجيه الوسائط من القناة
        CHANNEL_ID = "@hsisig8757"  # ← تأكد أنه نفس القناة
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=CHANNEL_ID,
            message_id=channel_message_id
        )

        print(f"✅ تم إرسال الوسائط من القناة (رسالة #{channel_message_id}) للمستخدم {user_id}")

    except Exception as e:
        print(f"❌ خطأ في إرسال تذكير الوسائط: {e}")
        import traceback
        traceback.print_exc()



# دالة لعرض المراجعات أو العمليات مع زر /start
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.chat_id
    user_data = context.user_data
    
    user = update.message.from_user

    # تسجيل الدخول
    print(f"📩 رسالة واردة من: {user_id}")
    if text in ["رجوع", "رِجوع", "رجوع للبداية"]:
        # إعادة تعيين جميع الحالات
        awaiting_flags = [
            'awaiting_review_name',
            'awaiting_delete_review',
            'awaiting_manual_review_name',
            'awaiting_manual_intervals',
            'awaiting_review_name_with_date',
            'awaiting_reminder_time',
            'awaiting_review_date',
            'awaiting_custom_intervals'
        ]
        for flag in awaiting_flags:
            user_data[flag] = False
        
        # حذف البيانات المؤقتة
        temp_data_keys = ['current_review', 'current_review_name_with_date']
        for key in temp_data_keys:
            if key in user_data:
                del user_data[key]
        
        await start(update, context)
        return
       
    if user_data.get("awaiting_review_name"):
        file_message = update.message
        message_id = None

        # إعادة التوجيه للقناة
        try:
            forwarded = await context.bot.forward_message(
                chat_id=CHANNEL_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            message_id = forwarded.message_id
        except Exception as e:
            print(f"❌ خطأ في نسخ الوسائط إلى القناة: {e}")
 
        user_data['awaiting_review_name'] = False
        review_name = file_message.caption if file_message.caption else "."
        today = datetime.datetime.now()
        user_intervals = get_user_intervals(user_id)
        intervals_str = user_intervals if user_intervals else " ".join(map(str, default_intervals))
 
        # ⬇️ تسجيلها في قاعدة البيانات
        add_review_with_custom_intervals(context, user_id, review_name, intervals_str, today, message_id)
 
        # ✅ إرسال تأكيد للمستخدم
        await update.message.reply_text(f".تم تسجيل المراجعة بنظام التكرار المتباعد{review_name}")
 
        return

    
    # معالجة الرسائل النصية
    if update.message.text:
        text = update.message.text
        

    if text == "الاعدادات":
        await show_settings(update, context)
    elif text == "ترتيب مراجعات اليوم":
        await how_show(update, context)
    elif text in ["حسب الترتيب الابجدي", "حسب الاحدث"]:
        await update_sort_order(update, context)
    elif text == "تباين المهمات بالالوان":
        await enable_color_contrast(update, context)
    elif text == "الغاء التباين":
        await disable_color_contrast(update, context)

    # زر مراجعة (تلقائي)
    if text == "تكرار (متباعد)":
        user_data['awaiting_review_name'] = True
        user_data['current_mode'] = 'auto'
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:\n"
            "⚠ [أحذر تنشر أشياء خاصة](https://t.me/C4R4C/15826)",
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    
    # استقبال اسم المراجعة أو الوسائط
    elif user_data.get('awaiting_review_name', False):
        if text == "رجوع":
            user_data['awaiting_review_name'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        # التحقق من الفترات
        user_intervals = get_user_intervals(user_id)
        if user_intervals:
            intervals = user_intervals
        else:
            intervals = " ".join(map(str, default_intervals))
    
        today = datetime.datetime.now()
        mode = user_data.get('current_mode', 'auto')
    
        try:
            if update.message.photo or update.message.video or update.message.document or update.message.audio or update.message.voice:
                # 👇 نحدد نوع الوسائط
                file_id = None
                media_type = None
                if update.message.photo:
                    media_type = 'photo'
                    file_id = update.message.photo[-1].file_id
                elif update.message.video:
                    media_type = 'video'
                    file_id = update.message.video.file_id
                elif update.message.document:
                    media_type = 'document'
                    file_id = update.message.document.file_id
                elif update.message.audio:
                    media_type = 'audio'
                    file_id = update.message.audio.file_id
                elif update.message.voice:
                    media_type = 'voice'
                    file_id = update.message.voice.file_id
    
                review_name = update.message.caption or f"مراجعة {media_type} {today.strftime('%H:%M')}"
                review_name = review_name.strip()
    
                # تسجيل مراجعة الوسائط
                success = await add_media_review_with_custom_intervals(
                    context=context,
                    user_id=user_id,
                    review_name=review_name,
                    media_type=media_type,
                    file_id=file_id,
                    caption=review_name,
                    intervals=intervals,
                    start_date=today
                )
    
                if success:
                    await update.message.reply_text(f"✅ تم تسجيل مراجعة الوسائط: {review_name}")
                else:
                    await update.message.reply_text("❌ فشل تسجيل مراجعة الوسائط.")
            
            else:
                # مراجعة نصية
                if not text or text.strip() == "":
                    await update.message.reply_text("❌ اسم المراجعة لا يمكن أن يكون فارغاً.")
                    return
    
                review_name = text.strip()
                add_review_with_custom_intervals(context, user_id, review_name, intervals, today)
                await update.message.reply_text(f"✅ تم تسجيل مراجعة نصية: {review_name}")
    
            user_data['awaiting_review_name'] = False
            user_data['current_mode'] = None
    
        except Exception as e:
            print(f"❌ خطأ في مراجعة تلقائي: {e}")
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
    

    elif text == "حذف مراجعة":
        reply_markup = await show_back_button(update)
        await show_delete_buttons(update, context)

    elif text == "حذف مراجعة✍":
        user_data['awaiting_delete_review'] = True
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "✍️ وضع حذف المراجعات\n\n"
            "اكتب اسم المراجعة التي تريد حذفها:\n\n"
            "💡 يمكنك حذف عدة مراجعات متتالية\n"
            "❌ اضغط 'رجوع' للخروج من وضع الحذف",
            reply_markup=reply_markup
        )

    elif user_data.get('awaiting_delete_review', False):
        if text == "رجوع":
            user_data['awaiting_delete_review'] = False
            if is_admin(user):
                reply_markup = await show_admin_main_menu(update)
            else:
                reply_markup = await show_user_main_menu(update)
            await update.message.reply_text("تم الخروج من وضع حذف المراجعات.", reply_markup=reply_markup)
        else:
            if not text or text.strip() == "":
                await update.message.reply_text("❌ اسم المراجعة لا يمكن أن يكون فارغاً. الرجاء إدخال اسم صحيح:")
                return
    
            review_name = text.strip()
            user_id = update.message.chat_id
    
            # حذف من جدول المراجعات النصية
            deleted_text = delete_text_review_from_db(review_name, user_id)
    
            # حذف من جدول الوسائط
            deleted_media = delete_media_review_from_db(review_name, user_id)
    
            if deleted_text or deleted_media:
                await update.message.reply_text(f"✅ تم حذف المراجعة: {review_name}")
            else:
                await update.message.reply_text(f"❌ لا توجد مراجعة بهذا الاسم: {review_name}")

    # معالجة زر الرجوع
    elif text == "رجوع":
        # إعادة تعيين جميع الحالات
        user_data.clear()
        await start(update, context)

    elif user_data.get('awaiting_delete_review', False):
        user_data['awaiting_delete_review'] = False
        review_name = text
        delete_media_review_from_db(review_name, user_id)
        await update.message.reply_text(f"تم حذف المراجعة: {review_name}")

    # معالجة زر ضبط الفترات الافتراضية
    elif text == "ضبط الفترات الافتراضية":
        await show_interval_settings_keyboard(update, context)
# معالجة المراجعة اليدوية
    elif text == "مراجعة (يدوي)":
        user_data['awaiting_manual_review_name'] = True
        user_data['current_mode'] = 'manual'
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:\n"
            "⚠ [أحذر تنشر أشياء خاصة](https://t.me/C4R4C/15826)",
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    elif user_data.get('awaiting_manual_review_name', False):
        if text == "رجوع":
            user_data['awaiting_manual_review_name'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        message = update.message
    
        # إن كانت وسائط
        if message.photo or message.video or message.audio or message.voice or message.document:
            # استخراج نوع الوسائط وملفها
            if message.photo:
                media_type = 'photo'
                file_id = message.photo[-1].file_id
            elif message.video:
                media_type = 'video'
                file_id = message.video.file_id
            elif message.audio:
                media_type = 'audio'
                file_id = message.audio.file_id
            elif message.voice:
                media_type = 'voice'
                file_id = message.voice.file_id
            elif message.document:
                media_type = 'document'
                file_id = message.document.file_id
            else:
                await update.message.reply_text("❌ نوع الوسائط غير مدعوم.")
                return
    
            # إعادة توجيه الوسائط للقناة
            try:
                forwarded = await context.bot.copy_message(
                    chat_id=CHANNEL_ID,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                user_data['attached_message_id'] = forwarded.message_id
                user_data['attached_media_type'] = media_type
                user_data['attached_file_id'] = file_id
                user_data['current_review'] = message.caption or "مراجعة بدون اسم"
            except Exception as e:
                print(f"خطأ أثناء إعادة التوجيه: {e}")
                await update.message.reply_text("❌ فشل إرسال الوسائط إلى القناة.")
                return
    
        # إن كانت نص فقط
        else:
            user_data['current_review'] = text
    
        user_data['awaiting_manual_review_name'] = False
        user_data['awaiting_manual_intervals'] = True
        await update.message.reply_text("""
    اكتب الفترات الزمنية مفصولة بمسافات.
    
    أمثلة:
    • للأيام: `1 3 7 14 30`
    • للساعات: `1س 6س 12س 24س`
    • للدقائق: `30د 60د 120د`
    • للثواني: `30ث 60ث 120ث`
    • مختلط: `1س 3د 7 14 30`
    
    (يمكنك استخدام h/m/s بدلاً من س/د/ث)
        """, parse_mode='Markdown')
    
    elif user_data.get('awaiting_manual_intervals', False):
        if text == "رجوع":
            user_data['awaiting_manual_intervals'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        user_data['awaiting_manual_intervals'] = False
        intervals_str = text
        review_name = user_data.get('current_review', "مراجعة بدون اسم")
        channel_message_id = user_data.get('attached_message_id')
        media_type = user_data.get('attached_media_type')
        file_id = user_data.get('attached_file_id')
    
        try:
            # تسجيل مراجعة وسائط إن وجدت
            if channel_message_id and media_type and file_id:
                await add_media_review_with_custom_intervals(
                    context=context,
                    user_id=user_id,
                    review_name=review_name,
                    media_type=media_type,
                    file_id=file_id,
                    caption=review_name,
                    intervals=intervals_str,
                    start_date=datetime.datetime.now(),
                    channel_message_id=channel_message_id
                )
                cursor.execute("SELECT next_reviews FROM media_reviews WHERE user_id = ? AND name = ? ORDER BY id DESC LIMIT 1", (user_id, review_name))
            else:
                # مراجعة نصية
                add_review_with_custom_intervals(context, user_id, review_name, intervals_str)
                cursor.execute("SELECT next_reviews FROM reviews WHERE user_id = ? AND name = ? ORDER BY rowid DESC LIMIT 1", (user_id, review_name))
    
            result = cursor.fetchone()
            if result:
                review_times = result[0].split(',')
                schedule_individual_reminders(context, user_id, review_name, review_times,
                                            review_type='media' if channel_message_id else 'text',
                                            channel_message_id=channel_message_id)
    
            await update.message.reply_text(f"✅ تم تسجيل المراجعة بنظام يدوي: {review_name}")
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ أثناء تسجيل المراجعة: {e}")
        finally:
            user_data['current_mode'] = None
            user_data.pop('attached_message_id', None)
            user_data.pop('attached_media_type', None)
            user_data.pop('attached_file_id', None)
# زر مراجعة (بالتاريخ)
    elif text == "تكرار (تاريخ)":
        user_data['awaiting_review_name_with_date'] = True
        user_data['current_mode'] = 'date'
        reply_markup = await show_back_button(update)
        await update.message.reply_text(
            "اكتب اسم المراجعة أو أرسل ملف/صورة/فيديو:\n"
            "⚠ [أحذر تنشر أشياء خاصة](https://t.me/C4R4C/15826)",
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    elif user_data.get('awaiting_review_name_with_date', False):
        if text == "رجوع":
            user_data['awaiting_review_name_with_date'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        message = update.message
    
        if message.photo or message.video or message.audio or message.voice or message.document:
            # استخرج الوسائط
            if message.photo:
                media_type = 'photo'
                file_id = message.photo[-1].file_id
            elif message.video:
                media_type = 'video'
                file_id = message.video.file_id
            elif message.audio:
                media_type = 'audio'
                file_id = message.audio.file_id
            elif message.voice:
                media_type = 'voice'
                file_id = message.voice.file_id
            elif message.document:
                media_type = 'document'
                file_id = message.document.file_id
            else:
                await update.message.reply_text("❌ نوع الوسائط غير مدعوم.")
                return
    
            try:
                forwarded = await context.bot.copy_message(
                    chat_id=CHANNEL_ID,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                user_data['attached_message_id'] = forwarded.message_id
                user_data['attached_media_type'] = media_type
                user_data['attached_file_id'] = file_id
                user_data['current_review_name_with_date'] = message.caption or "مراجعة بدون اسم"
            except Exception as e:
                print(f"خطأ في التوجيه: {e}")
                await update.message.reply_text("❌ فشل إرسال الوسائط إلى القناة.")
                return
        else:
            user_data['current_review_name_with_date'] = text
    
        user_data['awaiting_review_name_with_date'] = False
        user_data['awaiting_review_date'] = True
        example_date = get_yesterday_date() if 'get_yesterday_date' in globals() else "10/07/2025"
        await update.message.reply_text(f"اكتب تاريخ المراجعة بالتنسيق (مثال: `{example_date}`):", parse_mode='Markdown')
    
    elif user_data.get('awaiting_review_date', False):
        if text == "رجوع":
            user_data['awaiting_review_date'] = False
            user_data['current_mode'] = None
            await start(update, context)
            return
    
        try:
            selected_date = datetime.datetime.strptime(text, "%d/%m/%Y")
            review_name = user_data.get('current_review_name_with_date', "مراجعة بدون اسم")
            intervals_str = get_user_intervals(user_id) or " ".join(map(str, default_intervals))
            channel_message_id = user_data.get('attached_message_id')
            media_type = user_data.get('attached_media_type')
            file_id = user_data.get('attached_file_id')
    
            if channel_message_id and media_type and file_id:
                await add_media_review_with_custom_intervals(
                    context=context,
                    user_id=user_id,
                    review_name=review_name,
                    media_type=media_type,
                    file_id=file_id,
                    caption=review_name,
                    intervals=intervals_str,
                    start_date=selected_date,
                    channel_message_id=channel_message_id
                )
                cursor.execute("SELECT next_reviews FROM media_reviews WHERE user_id = ? AND name = ? ORDER BY id DESC LIMIT 1", (user_id, review_name))
            else:
                add_review_with_custom_intervals(context, user_id, review_name, intervals_str, selected_date)
                cursor.execute("SELECT next_reviews FROM reviews WHERE user_id = ? AND name = ? ORDER BY rowid DESC LIMIT 1", (user_id, review_name))
    
            result = cursor.fetchone()
            if result:
                review_times = result[0].split(',')
                schedule_individual_reminders(context, user_id, review_name, review_times,
                                              review_type='media' if channel_message_id else 'text',
                                              channel_message_id=channel_message_id)
    
            await update.message.reply_text(f"✅ تم تسجيل المراجعة: {review_name} بتاريخ {selected_date.strftime('%d/%m/%Y')}")
        except ValueError:
            await update.message.reply_text("❌ تنسيق التاريخ غير صحيح. استخدم التنسيق: يوم/شهر/سنة")
        finally:
            user_data['awaiting_review_date'] = False
            user_data['current_mode'] = None
            user_data.pop('attached_message_id', None)
            user_data.pop('attached_media_type', None)
            user_data.pop('attached_file_id', None)
    
        
    elif text == "حولَ":
        # إعادة تعيين كل الحالات المتعلقة بإدخال المراجعة
        user_data['awaiting_review_name_with_date'] = False
        user_data['awaiting_review_date'] = False
        user_data['current_review_name_with_date'] = ""
        await update.message.reply_text("أي مشكلة تواجهك بالبوت، تواصل هنا @REPETIHELPEBOT")

    # معالجة زر ضبط الفترات الافتراضية
    elif text == "ضبط الفترات الافتراضية":
        await show_interval_settings_keyboard(update, context)
    
    # معالجة أزرار الفترات
    elif text == "الفترات الافتراضية":
        intervals_text = " ".join(map(str, default_intervals))
        await update.message.reply_text(f"الفترات الافتراضية (بالأيام):\n\n`{intervals_text}`", parse_mode='Markdown')
    
    elif text == "فتراتي المخصصة":
        user_intervals = get_user_intervals(user_id)
        if user_intervals:
            await update.message.reply_text(f"فتراتك المخصصة:\n\n`{user_intervals}`", parse_mode='Markdown')
        else:
            await update.message.reply_text("لا توجد فترات مخصصة محفوظة.")
    
    elif text == "تخصيص جديد":
        user_data['awaiting_custom_intervals'] = True
        await update.message.reply_text("""
أدخل الفترات الزمنية الجديدة مفصولة بمسافات:

أمثلة:
• للأيام: `1 3 7 14 30`
• للساعات: `1س 6س 12س 24س`
• للدقائق: `30د 60د 120د`
• للثواني: `30ث 60ث 120ث`
• مختلط: `1س 3د 7 14 30`

(يمكنك استخدام h/m/s بدلاً من س/د/ث)
        """, parse_mode='Markdown')
    
    elif user_data.get('awaiting_custom_intervals', False):
        if text == "رجوع":
            user_data['awaiting_custom_intervals'] = False
            await start(update, context)
            return
        
        user_data['awaiting_custom_intervals'] = False
        intervals_str = text
        
        try:
            # التحقق من صحة الفترات
            convert_intervals_to_minutes(intervals_str)
            save_user_intervals(user_id, intervals_str)
            await update.message.reply_text(f"✅ تم حفظ فتراتك المخصصة: {intervals_str}")
            
            # إعادة عرض قائمة الفترات المحدثة
            await show_interval_settings_keyboard(update, context)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في تنسيق الفترات: {str(e)}")

    elif user_data.get('awaiting_custom_intervals', False):
        if text == "رجوع":
            user_data['awaiting_custom_intervals'] = False
            await start(update, context)
            return
        
        user_data['awaiting_custom_intervals'] = False
        intervals_str = text
        
        try:
            # التحقق من صحة الفترات
            convert_intervals_to_minutes(intervals_str)
            save_user_intervals(user_id, intervals_str)
            await update.message.reply_text(f"✅ تم حفظ فتراتك المخصصة: {intervals_str}")
            
            # إعادة عرض قائمة الفترات المحدثة
            await show_interval_settings_keyboard(update, context)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في تنسيق الفترات: {str(e)}")

    # معالجة زر مراجعات اليوم
    elif text == "مراجعات اليوم":
        await show_today_reviews(update, context)

    elif text == "ضبط تذكير المراجعة":
        user_data['awaiting_reminder_time'] = True
        reply_markup = await show_back_button(update)
        await update.message.reply_text(f"يرجى إدخال الوقت بالتنسيق HH:MM (مثال: `7:30`)",parse_mode='Markdown' ,reply_markup=reply_markup)
# استبدل الجزء الخاص بـ elif user_data.get('awaiting_reminder_time', False) بهذا الكود:
    elif user_data.get('awaiting_reminder_time', False):
        user_data['awaiting_reminder_time'] = False
        try:
            # إزالة أي تذكيرات سابقة للمستخدم
            current_jobs = context.job_queue.get_jobs_by_name(str(update.message.chat_id))
            for job in current_jobs:
                job.schedule_removal()

            # تحويل الوقت إلى توقيت بغداد
            reminder_time = datetime.datetime.strptime(text, '%H:%M').time()
            reminder_datetime = datetime.datetime.combine(datetime.date.today(), reminder_time)
            reminder_baghdad_time = baghdad_tz.localize(reminder_datetime).timetz()

            # تحديث قاعدة البيانات
            cursor.execute("""
                INSERT OR REPLACE INTO reminders (user_id, reminder_time) 
                VALUES (?, ?)
            """, (update.message.chat_id, text))
            conn.commit()

            # حذف التذكير القديم من قاعدة البيانات قبل إضافة الجديد
            cursor.execute("DELETE FROM reminders WHERE user_id = ?", (update.message.chat_id,))
            conn.commit()

            # إضافة التذكير الجديد
            cursor.execute("""
                INSERT INTO reminders (user_id, reminder_time) 
                VALUES (?, ?)
            """, (update.message.chat_id, text))
            conn.commit()

            # إضافة تذكير جديد
            context.job_queue.run_daily(
                send_daily_reminder,
                time=reminder_baghdad_time,
                name=str(update.message.chat_id),
                chat_id=update.message.chat_id,
                data={'user_id': update.message.chat_id}
            )

            await update.message.reply_text(f"تم ضبط التذكير اليومي عند الساعة {text}")
        except ValueError:
            await update.message.reply_text(f"الرجاء إدخال الوقت بالتنسيق الصحيح وبنظام 24 ساعه HH:MM (مثال: `7:30` بالصباح و`13:00` يعني بال1ظهراً)",parse_mode='Markdown')


    if text == "حذف كل المراجعات":
        await show_delete_all_buttons(update)
        return

    if text == "نعم":
        cursor.execute("DELETE FROM reviews WHERE user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text("تم حذف كل المراجعات.")
        await start(update, context)
        return

    elif text == "عرض المراجعات":
        await show_reviews(update, context)
    elif text == "حذف مراجعة":
        await show_delete_buttons(update, context)



    # معالجة أزرار الأدمن
    if is_admin(user):
        if text == "📢 إشاعة":
            await start_broadcast(update, context)
            return
        
        elif text == "👥 إحصائيات المستخدمين":
            await show_users_stats(update, context)
            return
        
        # الخروج من وضع الإشاعة
        elif text == "رجوع" and user_data.get('broadcast_mode', False):
            user_data['broadcast_mode'] = False
            reply_markup = await show_admin_main_menu(update)
            await update.message.reply_text("تم إلغاء وضع الإشاعة.", reply_markup=reply_markup)
            return
        
        # معالجة الرسائل في وضع الإشاعة
        elif user_data.get('broadcast_mode', False):
            # إشاعة النص
            if text:
                await broadcast_text(context, text, user_id)
                user_data['broadcast_mode'] = False
                reply_markup = await show_admin_main_menu(update)
                await update.message.reply_text("تم إنجاز الإشاعة!", reply_markup=reply_markup)
                return
    
    # هنا يتم استدعاء دالة معالجة الرسائل الأصلية

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"🔥 خطأ غير متوقع: {context.error}")
    import traceback
    traceback.print_exc()
    
    if update and hasattr(update, 'message'):
        await update.message.reply_text("❌ حدث خطأ غير متوقع، يرجى المحاولة لاحقاً")

# معالجة الأزرار المضمنة
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = context.user_data
    
    if query.data == "default_intervals":
        intervals_text = " ".join(map(str, default_intervals))
        await query.edit_message_text(f"الفترات الافتراضية (بالأيام):\n\n`{intervals_text}`", parse_mode='Markdown')
    
    elif query.data == "my_intervals":
        user_intervals = get_user_intervals(user_id)
        if user_intervals:
            await query.edit_message_text(f"فتراتك المخصصة:\n\n`{user_intervals}`", parse_mode='Markdown')
        else:
            await query.edit_message_text("لا توجد فترات مخصصة محفوظة.")
    
    elif query.data == "customize_intervals":
        user_data['awaiting_custom_intervals'] = True
        await query.edit_message_text("""
أدخل الفترات الزمنية الجديدة مفصولة بمسافات:

أمثلة:
• للأيام: `1 3 7 14 30`
• للساعات: `1س 6س 12س 24س`
• للدقائق: `30د 60د 120د`
• للثواني: `30ث 60ث 120ث`
• مختلط: `1س 3د 7 14 30`

(يمكنك استخدام h/m/s بدلاً من س/د/ث)
        """, parse_mode='Markdown')

# دالة محدثة لإضافة المراجعة التلقائية
def add_review_to_spaced_repetition_updated(context, user_id, review_name, review_date):
    """إضافة مراجعة بالنظام التلقائي مع الفترات المخصصة أو الافتراضية"""
    # محاولة الحصول على الفترات المخصصة للمستخدم
    user_intervals = get_user_intervals(user_id)
    
    if user_intervals:
        # استخدام الفترات المخصصة
        add_review_with_custom_intervals(context, user_id, review_name, user_intervals, review_date)
    else:
        # استخدام الفترات الافتراضية
        intervals_str = " ".join(map(str, default_intervals))
        add_review_with_custom_intervals(context, user_id, review_name, intervals_str, review_date)

# دالة محدثة لإضافة المراجعة بالتاريخ
def add_review_with_date_updated(context, user_id, review_name, review_date):
    """إضافة مراجعة بتاريخ محدد مع الفترات المخصصة أو الافتراضية"""
    add_review_to_spaced_repetition_updated(context, user_id, review_name, review_date)

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    print(f"🔔 Daily reminder triggered for user {chat_id}")

    try:
        with sqlite3.connect('reviews.db') as temp_conn:
            temp_cursor = temp_conn.cursor()
            current_time = datetime.datetime.now()

            temp_cursor.execute("""
                SELECT name, added_on, next_reviews, 'text' as type, NULL as channel_message_id
                FROM reviews
                WHERE user_id = ?
            """, (chat_id,))
            text_reviews = temp_cursor.fetchall()

            temp_cursor.execute("""
                SELECT name, added_on, next_reviews, 'media' as type, channel_message_id
                FROM media_reviews
                WHERE user_id = ?
            """, (chat_id,))
            media_reviews = temp_cursor.fetchall()

            all_reviews = list(text_reviews) + list(media_reviews)
            today_reviews = []

            for review in all_reviews:
                review_times = review[2].split(',')
                print(f"📋 مراجعة: {review[0]}، نوع: {review[3]}, channel_message_id: {review[4]}, أوقات المراجعة: {review_times}")
                for review_time_str in review_times:
                    try:
                        review_time = datetime.datetime.strptime(review_time_str.strip(), "%Y-%m-%d %H:%M:%S")
                        if review_time.date() == current_time.date():
                            print(f"✅ تمت مطابقة تاريخ اليوم للمراجعة: {review[0]} في {review_time}")
                            today_reviews.append({
                                'name': review[0],
                                'added_on': review[1],
                                'time': review_time,
                                'type': review[3],
                                'channel_message_id': review[4]
                            })
                            break
                    except ValueError:
                        if current_time.strftime("%Y-%m-%d") in review_time_str:
                            print(f"✅ تمت مطابقة تاريخ اليوم (بواسطة نص) للمراجعة: {review[0]} في {review_time_str}")
                            today_reviews.append({
                                'name': review[0],
                                'added_on': review[1],
                                'time': None,
                                'type': review[3],
                                'channel_message_id': review[4]
                            })
                            break
                    except ValueError:
                        if current_time.strftime("%Y-%m-%d") in review_time_str:
                            today_reviews.append({
                                'name': review[0],
                                'added_on': review[1],
                                'time': None,
                                'type': review[3],
                                'channel_message_id': review[4]
                            })
                            break

            if today_reviews:
                temp_cursor.execute("SELECT sort_order, color_contrast FROM user_settings WHERE user_id = ?", (chat_id,))
                settings = temp_cursor.fetchone()
                order = settings[0] if settings else 'alphabetical'
                color_contrast = settings[1] if settings else 0

                if order == 'alphabetical':
                    today_reviews.sort(key=lambda x: x['name'])
                else:
                    today_reviews.sort(key=lambda x: x['time'] or datetime.datetime.min)

                review_list = []
                media_to_send = []  # قائمة تحتوي على dict يحتوي اسم المراجعة و message_id
                for review in today_reviews:
                    emoji = get_review_emoji(review['added_on']) if color_contrast else ''
                    time_str = review['time'].strftime("%H:%M") if review['time'] else ''
                    
                    if review['type'] == 'media':
                        review_list.append(f"{emoji} {review['name']} 📎 {('- ' + time_str) if time_str else ''}")
                        
                        if review['channel_message_id']:
                            media_to_send.append({
                                'name': review['name'],
                                'message_id': review['channel_message_id']
                            })
                        else:
                            print(f"⚠️ ملاحظة: مراجعة وسائط بدون channel_message_id: {review['name']}")
                    
                    else:
                        review_list.append(f"{emoji} {review['name']} {('- ' + time_str) if time_str else ''}")
                
                review_text = "\n".join(review_list)
                await context.bot.send_message(chat_id=chat_id, text=f"تذكير اليوم هاي مراجعاتك :\n\n{review_text}")

                for media in media_to_send:
                    try:
                        print(f"🔔 إرسال وسائط '{media['name']}' من القناة (message_id: {media['message_id']}) إلى المستخدم {chat_id}")
                        await context.bot.copy_message(
                            chat_id=chat_id,
                            from_chat_id=CHANNEL_ID,
                            message_id=int(media['message_id'])
                        )
                    except Exception as e:
                        print(f"❌ فشل إرسال الوسائط '{media['name']}' إلى {chat_id}: {e}")


    except Exception as e:
        print(f"Error in daily reminder: {str(e)}")


# دالة استعادة التذكيرات المُصححة
async def restore_reminders(context: ContextTypes.DEFAULT_TYPE):
    """استعادة التذكيرات عند بدء التشغيل"""
    try:
        with sqlite3.connect('reviews.db') as temp_conn:
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("SELECT user_id, reminder_time FROM reminders")
            reminders = temp_cursor.fetchall()
        
        print(f"🔄 Restoring {len(reminders)} reminders...")
        
        for user_id, reminder_time in reminders:
            try:
                # إزالة أي تذكيرات موجودة مسبقاً
                current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
                for job in current_jobs:
                    job.schedule_removal()
                
                # تحويل وقت التذكير إلى كائن time
                time_obj = datetime.datetime.strptime(reminder_time, '%H:%M').time()
                
                # إنشاء تذكير يومي جديد
                job = context.job_queue.run_daily(
                    send_daily_reminder,
                    time=time_obj,
                    name=str(user_id),
                    chat_id=user_id,
                    data={'user_id': user_id}
                )
                
                print(f"✅ Restored reminder for user {user_id} at {reminder_time}")
                
            except Exception as e:
                print(f"❌ Error restoring reminder for user {user_id}: {str(e)}")
        
        print(f"🎯 Total active jobs: {len(context.job_queue.jobs())}")
        
    except Exception as e:
        print(f"❌ Error in restore_reminders: {str(e)}")


# دالة اختبار للتحقق من عمل التذكيرات
async def test_reminder_system(context: ContextTypes.DEFAULT_TYPE):
    """اختبار نظام التذكيرات"""
    try:
        with sqlite3.connect('reviews.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, reminder_time FROM reminders")
            reminders = cursor.fetchall()
            
            print(f"📊 Found {len(reminders)} reminders in database:")
            for user_id, reminder_time in reminders:
                print(f"   User {user_id}: {reminder_time}")
                
            # فحص الـ jobs النشطة
            active_jobs = context.job_queue.jobs()
            print(f"🔄 Active jobs: {len(active_jobs)}")
            for job in active_jobs:
                print(f"   Job: {job.name}, Next run: {job.next_t}")
                
    except Exception as e:
        print(f"❌ Error in test_reminder_system: {str(e)}")

# دالة لمعالجة التفاعل مع الأزرار (CallbackQueryHandler)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # معالجة حذف المراجعة
    if query.data.startswith('delete_review_'):
        review_name = query.data.replace('delete_review_', '')
        user_id = query.message.chat_id
        cursor.execute("DELETE FROM reviews WHERE user_id = ? AND name = ?", (user_id, review_name))
        conn.commit()
        await query.edit_message_text(f"تم حذف المراجعة: {review_name}")




# إعدادات القناة
CHANNEL_ID = "@hsisig8757"  # ضع معرف القناة هنا
async def send_media_to_channel(context, media_type, file_id, caption=None):
    print(f"📤 إرسال وسائط إلى القناة: {CHANNEL_ID}")
    """إرسال الوسائط إلى القناة (مُحسنة مع تصحيح الأخطاء)"""
    try:
        # تسجيل محاولة الإرسال
        print(f"🚀 محاولة إرسال {media_type} إلى القناة {CHANNEL_ID}")
        
        if media_type == 'photo':
            message = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=file_id,
                caption=caption
            )
        elif media_type == 'video':
            message = await context.bot.send_video(
                chat_id=CHANNEL_ID,
                video=file_id,
                caption=caption
            )
        elif media_type == 'audio':
            message = await context.bot.send_audio(
                chat_id=CHANNEL_ID,
                audio=file_id,
                caption=caption
            )
        elif media_type == 'voice':
            message = await context.bot.send_voice(
                chat_id=CHANNEL_ID,
                voice=file_id,
                caption=caption
            )
        elif media_type == 'document':
            message = await context.bot.send_document(
                chat_id=CHANNEL_ID,
                document=file_id,
                caption=caption
            )
        else:
            print(f"❌ نوع الوسائط غير مدعوم: {media_type}")
            return None
        
        # تسجيل النجاح
        print(f"✅ تم إرسال الوسائط إلى القناة! معرف الرسالة: {message.message_id}")
        return message.message_id
    
    except telegram.error.BadRequest as e:
        print(f"❌ خطأ في طلب التلغرام: {str(e)}")
        print(f"تفاصيل: {e.message}")
    except telegram.error.TimedOut:
        print("❌ انتهت مهلة الإرسال")
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {str(e)}")
    
    return None


# دالة لإضافة مراجعة الوسائط مع رفعها للقناة
async def add_media_review_with_custom_intervals(context, user_id, review_name, media_type, file_id, caption, intervals, start_date=None, channel_message_id=None):
    print(f"📦 حفظ مراجعة الوسائط: {review_name} للمستخدم {user_id} في {start_date.strftime('%Y-%m-%d %H:%M:%S')}")

    """إضافة مراجعة وسائط مع رفعها للقناة وحفظ رقم الرسالة"""
    try:
        if start_date is None:
            start_date = datetime.datetime.now()
        
        # التحقق من صحة اسم المراجعة
        if not review_name or review_name.strip() == "":
            review_name = f"مراجعة {media_type} {start_date.strftime('%H:%M')}"
        
        review_name = review_name.strip()
        
        # تحويل الفترات إلى دقائق
        try:
            if isinstance(intervals, str):
                interval_minutes = convert_intervals_to_minutes(intervals)
            else:
                interval_minutes = [interval * 24 * 60 for interval in intervals]
        except Exception as e:
            print(f"خطأ في تحويل الفترات: {e}")
            interval_minutes = [1*24*60, 3*24*60, 7*24*60]  # 1, 3, 7 أيام
        
        # حساب أوقات المراجعات القادمة
        next_reviews = []
        for minutes in interval_minutes:
            next_review = start_date + datetime.timedelta(minutes=minutes)
            next_reviews.append(next_review.strftime("%Y-%m-%d %H:%M:%S"))
        
        next_reviews_str = ','.join(next_reviews)
        
        # رفع الوسائط للقناة
        print(f"📤 رفع الوسائط للقناة: {media_type}")
        channel_message = None
        
        # تحديد معرف القناة (يجب أن يكون موجود في الكود الأصلي)
        CHANNEL_ID = "@hsisig8757"  # استبدل بمعرف قناتك
        
        try:
            # إرسال الوسائط حسب نوعها
            if media_type == 'photo':
                channel_message = await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'video':
                channel_message = await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'audio':
                channel_message = await context.bot.send_audio(
                    chat_id=CHANNEL_ID,
                    audio=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'voice':
                channel_message = await context.bot.send_voice(
                    chat_id=CHANNEL_ID,
                    voice=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'document':
                channel_message = await context.bot.send_document(
                    chat_id=CHANNEL_ID,
                    document=file_id,
                    caption=f"📚 {review_name}\n👤 المستخدم: {user_id}\n📅 {start_date.strftime('%Y-%m-%d %H:%M')}"
                )
            elif media_type == 'video_note':
                channel_message = await context.bot.send_video_note(
                    chat_id=CHANNEL_ID,
                    video_note=file_id
                )
            elif media_type == 'sticker':
                channel_message = await context.bot.send_sticker(
                    chat_id=CHANNEL_ID,
                    sticker=file_id
                )
            
            if channel_message:
                channel_message_id = channel_message.message_id
                print(f"✅ تم رفع الوسائط للقناة برقم: {channel_message_id}")
                
                # حفظ في قاعدة البيانات
                cursor.execute("""
                    INSERT INTO media_reviews (user_id, name, media_type, file_id, caption, channel_message_id, added_on, next_reviews)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, review_name, media_type, file_id, caption, channel_message_id, start_date.strftime("%Y-%m-%d %H:%M:%S"), next_reviews_str))
                conn.commit()
                
                return True
            else:
                print(f"❌ فشل في رفع الوسائط للقناة")
                return False
                
        except Exception as e:
            print(f"❌ خطأ في رفع الوسائط للقناة: {e}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ عام في إضافة مراجعة الوسائط: {e}")
        return False


async def send_media_from_channel(context, user_id, channel_message_id):
    try:
        print(f"إرسال وسائط من القناة {CHANNEL_ID} إلى المستخدم {user_id}، معرف الرسالة: {channel_message_id}")
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=CHANNEL_ID,
            message_id=channel_message_id,
            disable_notification=False
        )
        print("تم الإرسال بنجاح")
        return True
    except Exception as e:
        print(f"❌ خطأ في جلب الوسائط من القناة: {e}")
        return False


# دالة لجدولة تذكيرات الوسائط
def schedule_media_reminders(job_queue, user_id, review_name, review_times, channel_message_id):
    """جدولة تذكيرات الوسائط"""
    try:
        for i, time_str in enumerate(review_times):
            review_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            
            # التحقق من أن الوقت في المستقبل
            if review_time > datetime.datetime.now():
                job_queue.run_once(
                    send_media_reminder,
                    when=review_time,
                    data={
                        'user_id': user_id,
                        'review_name': review_name,
                        'channel_message_id': channel_message_id,
                        'review_number': i + 1
                    },
                    name=f"media_reminder_{user_id}_{review_name}_{i}"
                )
                print(f"📅 تم جدولة تذكير الوسائط: {review_name} في {time_str}")
    except Exception as e:
        print(f"❌ خطأ في جدولة تذكيرات الوسائط: {e}")







#إعدادات الأدمن
ADMIN_USERNAME = "Y_HOH0"  # ضع هنا اسم المستخدم الخاص بك بدون @

# جدول لحفظ جميع المستخدمين
def create_users_table():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()

# استدعاء إنشاء جدول المستخدمين
create_users_table()

# دالة لإضافة مستخدم جديد
def add_user(user_id, username=None, first_name=None, last_name=None):
    """إضافة مستخدم جديد أو تحديث بياناته"""
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, last_name))
    conn.commit()

# دالة للحصول على جميع المستخدمين النشطين
def get_all_active_users():
    """الحصول على جميع المستخدمين النشطين"""
    cursor.execute("SELECT user_id FROM users WHERE is_active = 1")
    return [row[0] for row in cursor.fetchall()]

# دالة لتعيين حالة المستخدم (نشط/غير نشط)
def set_user_status(user_id, is_active):
    """تحديث حالة المستخدم"""
    cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
    conn.commit()

# دالة للتحقق من الأدمن
def is_admin(user):
    """التحقق من صلاحيات الأدمن"""
    if hasattr(user, 'username') and user.username:
        return user.username.lower() == ADMIN_USERNAME.lower()
    return False

# دالة لعرض القائمة الرئيسية للأدمن
async def show_admin_main_menu(update: Update):
    """عرض القائمة الرئيسية للأدمن"""
    keyboard = [
        [KeyboardButton("تكرار (متباعد)"), KeyboardButton("مراجعة (يدوي)")],
        [KeyboardButton("عرض المراجعات"), KeyboardButton("مراجعات اليوم")],
        [KeyboardButton("تكرار (تاريخ)"), KeyboardButton("حذف مراجعة✍")],
        [KeyboardButton("ضبط تذكير المراجعة")],
        [KeyboardButton("الاعدادات")],
        [KeyboardButton("📢 إشاعة"), KeyboardButton("👥 إحصائيات المستخدمين")]  # أزرار الأدمن
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return reply_markup

# دالة لعرض القائمة الرئيسية للمستخدمين العاديين
async def show_user_main_menu(update: Update):
    """عرض القائمة الرئيسية للمستخدمين العاديين"""
    keyboard = [
        [KeyboardButton("تكرار (متباعد)"), KeyboardButton("مراجعة (يدوي)")],
        [KeyboardButton("عرض المراجعات"), KeyboardButton("مراجعات اليوم")],
        [KeyboardButton("تكرار (تاريخ)"), KeyboardButton("حذف مراجعة✍")],
        [KeyboardButton("الاعدادات")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return reply_markup

# دالة البداية المحدثة والموحدة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة البداية الموحدة مع التحقق من الأدمن"""
    global awaiting_review_name
    awaiting_review_name = False
    
    user_id = update.message.chat_id
    user = update.message.from_user
    
    # إضافة المستخدم إلى قاعدة البيانات
    add_user(user_id, user.username, user.first_name, user.last_name)
    
    # عرض القائمة المناسبة حسب نوع المستخدم
    if is_admin(user):
        reply_markup = await show_admin_main_menu(update)
        welcome_text = f"🔑 مرحباً بك أيها الأدمن @{user.username if user.username else 'Admin'}!\n\nنظام المراجعة المطور مع لوحة الإدارة\n\nاختر ما تريد فعله:"
    else:
        reply_markup = await show_user_main_menu(update)
        welcome_text = "مرحباً بك في نظام المراجعة المطور!\n\nاختر ما تريد فعله:"
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# دالة لبدء الإشاعة
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الإشاعة"""
    if not is_admin(update.message.from_user):
        await update.message.reply_text("❌ ليس لديك صلاحية للوصول لهذه الميزة.")
        return
    
    context.user_data['broadcast_mode'] = True
    
    keyboard = [
        [KeyboardButton("رجوع")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "📢 **وضع الإشاعة مفعل**\n\n"
        "أرسل الآن أي محتوى تريد إشاعته:\n\n"
        "• 📝 **نص عادي**\n"
        "• 🖼️ **صورة** (مع نص اختياري)\n"
        "• 🎬 **فيديو** (مع نص اختياري)\n"
        "• 🎵 **صوت/تسجيل صوتي** (مع نص اختياري)\n"
        "• 📄 **ملف** (مع نص اختياري)\n\n"
        "💡 **تلميح:** يمكنك استخدام تنسيق Markdown في النصوص",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# دالة لإرسال النص لجميع المستخدمين
async def broadcast_text(context: ContextTypes.DEFAULT_TYPE, message_text, admin_id):
    """إرسال نص لجميع المستخدمين"""
    users = get_all_active_users()
    sent_count = 0
    failed_count = 0
    blocked_users = []
    
    # إرسال رسالة بداية الإشاعة للأدمن
    await context.bot.send_message(
        chat_id=admin_id,
        text=f"🚀 بدء الإشاعة...\n👥 عدد المستخدمين: {len(users)}"
    )
    
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode='Markdown'
            )
            sent_count += 1
            
            # تأخير صغير لتجنب حدود التلجرام
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            
            # إذا كان المستخدم قد حظر البوت
            if "bot was blocked" in error_msg.lower() or "user is deactivated" in error_msg.lower():
                blocked_users.append(user_id)
                set_user_status(user_id, 0)  # تعيين المستخدم كغير نشط
    
    # إرسال تقرير الإشاعة للأدمن
    report = f"""
✅ **تم إنجاز الإشاعة!**

📊 **إحصائيات الإرسال:**
• ✅ تم الإرسال: {sent_count}
• ❌ فشل الإرسال: {failed_count}
• 🚫 المستخدمون الذين حظروا البوت: {len(blocked_users)}

📝 **المحتوى المرسل:**
{message_text[:100]}{'...' if len(message_text) > 100 else ''}
    """
    
    await context.bot.send_message(
        chat_id=admin_id,
        text=report,
        parse_mode='Markdown'
    )

# دالة لإرسال الوسائط لجميع المستخدمين
async def broadcast_media(context: ContextTypes.DEFAULT_TYPE, media_type, file_id, caption, admin_id):
    """إرسال وسائط لجميع المستخدمين"""
    users = get_all_active_users()
    sent_count = 0
    failed_count = 0
    blocked_users = []
    
    # إرسال رسالة بداية الإشاعة للأدمن
    await context.bot.send_message(
        chat_id=admin_id,
        text=f"🚀 بدء إشاعة {media_type}...\n👥 عدد المستخدمين: {len(users)}"
    )
    
    for user_id in users:
        try:
            if media_type == "photo":
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "video":
                await context.bot.send_video(
                    chat_id=user_id,
                    video=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "audio":
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "document":
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "voice":
                await context.bot.send_voice(
                    chat_id=user_id,
                    voice=file_id,
                    caption=caption,
                    parse_mode='Markdown'
                )
            elif media_type == "video_note":
                await context.bot.send_video_note(
                    chat_id=user_id,
                    video_note=file_id
                )
            elif media_type == "sticker":
                await context.bot.send_sticker(
                    chat_id=user_id,
                    sticker=file_id
                )
            
            sent_count += 1
            
            # تأخير صغير لتجنب حدود التلجرام
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            
            # إذا كان المستخدم قد حظر البوت
            if "bot was blocked" in error_msg.lower() or "user is deactivated" in error_msg.lower():
                blocked_users.append(user_id)
                set_user_status(user_id, 0)  # تعيين المستخدم كغير نشط
    
    # إرسال تقرير الإشاعة للأدمن
    report = f"""
✅ **تم إنجاز إشاعة {media_type}!**

📊 **إحصائيات الإرسال:**
• ✅ تم الإرسال: {sent_count}
• ❌ فشل الإرسال: {failed_count}
• 🚫 المستخدمون الذين حظروا البوت: {len(blocked_users)}

📝 **النص المرفق:**
{caption[:100] if caption else 'لا يوجد نص'}{'...' if caption and len(caption) > 100 else ''}
    """
    
    await context.bot.send_message(
        chat_id=admin_id,
        text=report,
        parse_mode='Markdown'
    )

# دالة لعرض إحصائيات المستخدمين
async def show_users_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المستخدمين"""
    if not is_admin(update.message.from_user):
        await update.message.reply_text("❌ ليس لديك صلاحية للوصول لهذه الميزة.")
        return
    
    # الحصول على إحصائيات المستخدمين
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    active_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 0")
    inactive_users = cursor.fetchone()[0]
    
    # إحصائيات المراجعات
    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM reviews")
    users_with_reviews = cursor.fetchone()[0]
    
    # المستخدمون الجدد اليوم
    today = datetime.datetime.now().date()
    cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(join_date) = ?", (today,))
    new_users_today = cursor.fetchone()[0]
    
    # المستخدمون الجدد هذا الأسبوع
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (week_ago,))
    new_users_week = cursor.fetchone()[0]
    
    stats_text = f"""
📊 **إحصائيات المستخدمين**

👥 **العدد الإجمالي:** {total_users}
✅ **المستخدمون النشطون:** {active_users}
❌ **المستخدمون غير النشطون:** {inactive_users}

📚 **إحصائيات المراجعات:**
• إجمالي المراجعات: {total_reviews}
• المستخدمون الذين لديهم مراجعات: {users_with_reviews}

📈 **المستخدمون الجدد:**
• اليوم: {new_users_today}
• هذا الأسبوع: {new_users_week}

🗓️ **تاريخ التقرير:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
    """
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    print("🚀 Starting bot...")
    # إضافة استعادة التذكيرات عند بدء التشغيل
    app.job_queue.run_once(restore_reminders, when=2)

    app.add_handler(CommandHandler("start", start))
    
    # فلتر شامل لجميع أنواع الوسائط (متوافق مع جميع الإصدارات)
    media_filter = (
        filters.PHOTO |
        filters.VIDEO |
        filters.AUDIO |
        filters.VOICE |
        filters.Document.ALL |  # للمستندات
        filters.VIDEO_NOTE |
        filters.Sticker.ALL     # للملصقات
    )
    
    # إضافة معالج الأخطاء
    app.add_error_handler(error_handler)
    # فلتر شامل لجميع الرسائل
    app.add_handler(MessageHandler(~filters.COMMAND, handle_message))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🎯 Bot handlers added")
    print("⏰ Starting polling...")
    
    # بدء البوت
    app.run_polling()

if __name__ == "__main__":
    main()
