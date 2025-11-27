#لا يضيف او يعمل امر اضافه جلسات بسبب تغيير ال min من الكوبلت جات الثاني الملف القديم يعمل اضافه جلسات

#المشكلة حتى بالاستراحات تنرسل 
#تطول 10 دفايق حتى تنرسل للكل اي واحد واحد بطيئة
#سويها تحويل وليس ارسال او طريقه تنرسل دفعه واحده مثل الاشاعه ولو اعتقد ما يصير زر بالاشاعه
#اضف اذا بدات الاستراحه الرسالة تنحذف للكل
###قبل ان اضف ارسال الجلسات نعم لا للجميع بالبوت

from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import sqlite3
import pytz
import datetime
from pytz import timezone
import pytz
import random
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

baghdad_tz = pytz.timezone('Asia/Baghdad')
def get_baghdad_time():
    baghdad_tz = timezone("Asia/Baghdad")
    return datetime.datetime.now(baghdad_tz)

MAIN_LOOP = None

BOT_INSTANCE = None

# إعدادات البوت
BOT_TOKEN = "7391001946:AAEHj9LL2ek_J-OCwTJji9mX7zHv3QfaEjA"
# إعدادات القناة
#CHANNEL_USERNAME = "@STUDYWITHELAHMED"  # أو CHANNEL_ID = "-1001234567890"
# الدوال المساعد

connection = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = connection.cursor()

# ...existing code...
# filepath: c:\Users\PC بغداد للحاسبات\Downloads\bot (37) لا تعمل اضافة جلسات خلل بدالة البداية بالاخير.py

# دالة جلب اسم المستخدم الحقيقي أو الاسم من قاعدة البيانات أو الـ ID
async def get_real_user_name(context, user_id):
    # جلب الاسم من قاعدة البيانات إذا كان موجود
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        return result[0]
    # إذا لم يوجد، جلب الاسم من تيليجرام
    try:
        user = await context.bot.get_chat(user_id)
        if user.first_name:
            return user.first_name
        elif user.username:
            return user.username
    except Exception:
        pass
    return str(user_id)
# ...existing code...

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        referrer_id INTEGER,
        points INTEGER DEFAULT 0,
        FOREIGN KEY (referrer_id) REFERENCES users (user_id)
    )
''')

# إنشاء جدول المستخدمين إذا لم يكن موجودًا
cursor.execute('''CREATE TABLE IF NOT EXISTS user_daily_points (
                    user_id INTEGER,
                    points INTEGER DEFAULT 0,
                    date DATE,
                    referrer_id INTEGER,
                    PRIMARY KEY (user_id, date),
                    FOREIGN KEY (referrer_id) REFERENCES users(user_id)
                )''')
connection.commit()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_weekly_points (
        user_id INTEGER,
        points REAL DEFAULT 0,
        week INTEGER,
        year INTEGER,
        PRIMARY KEY (user_id, week, year),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
''')
connection.commit()

cursor.execute('''CREATE TABLE IF NOT EXISTS user_monthly_points (
                    user_id INTEGER,
                    points INTEGER DEFAULT 0,
                    month INTEGER,
                    year INTEGER,
                    PRIMARY KEY (user_id, month, year),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS user_yearly_points (
                    user_id INTEGER,
                    points INTEGER DEFAULT 0,
                    year INTEGER,
                    PRIMARY KEY (user_id, year),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
)''')


# First, create a new table to track study sessions
cursor.execute('''CREATE TABLE IF NOT EXISTS study_sessions (
    user_id INTEGER,
    session_date DATE,
    session_start TIME,
    session_end TIME,
    duration_minutes INTEGER,
    completed BOOLEAN,
    PRIMARY KEY (user_id, session_date, session_start)
)''')
connection.commit()


cursor.execute('''CREATE TABLE IF NOT EXISTS challenges (
                    user_id INTEGER PRIMARY KEY,
                    last_challenge_date DATE
                )''')
connection.commit()

# في قسم إنشاء الجداول
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_points (
        user_id INTEGER,
        points REAL,
        source TEXT, -- 'manual' أو 'session'
        date DATE,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
''')
connection.commit()

# notify_all_users_new_session إنشاء جدول لتخزين رسائل الدعوة إذا لم يكن موجودًا
cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_invites (
        user_id INTEGER,
        session_number INTEGER,
        message_id INTEGER,
        PRIMARY KEY (user_id, session_number)
    )
""")
connection.commit()

# في بداية الكود بعد الاتصال بقاعدة البيانات
cursor.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cursor.fetchall()]

if 'username' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    connection.commit()


def add_manual_points(user_id, points):
    now = get_baghdad_time()
    today = now.date()
    
    # إضافة النقاط مع تحديد المصدر
    cursor.execute("""
        INSERT INTO user_points (user_id, points, source, date)
        VALUES (?, ?, ?, ?)
    """, (user_id, points, 'manual', today))
    
    # تحديث النقاط الإجمالية في جدول users
    cursor.execute("""
        UPDATE users 
        SET points = points + ? 
        WHERE user_id = ?
    """, (points, user_id))
    connection.commit()

def add_session_points(user_id, session_time, points):
    cursor.execute("""
        INSERT INTO session_points (user_id, session_time, points)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, session_time) DO UPDATE SET points = points + excluded.points
    """, (user_id, session_time, points))
    connection.commit()

    # تحديث النقاط اليومية
    add_daily_points(user_id, points)

def get_user_study_hours(user_id):
    today = get_baghdad_time().date()
    now = get_baghdad_time()
    week_number = now.isocalendar()[1]
    
    # Get today's hours from study_sessions
    cursor.execute("""
        SELECT COALESCE(SUM(duration_minutes) / 60.0, 0) 
        FROM study_sessions 
        WHERE user_id = ? AND session_date = ?
    """, (user_id, today))
    today_hours = cursor.fetchone()[0]
    
    # Get week's hours from study_sessions
    cursor.execute("""
        SELECT COALESCE(SUM(duration_minutes) / 60.0, 0) 
        FROM study_sessions 
        WHERE user_id = ? AND session_date >= ?
    """, (user_id, week_number))
    week_hours = cursor.fetchone()[0]
    
    return today_hours, week_hours

def reset_daily_points():
    cursor.execute("DELETE FROM user_daily_points")
    connection.commit()
    print("✅ تم تصفير النقاط اليومية!")

def reset_weekly_points():
    last_monday = get_baghdad_time().date() - timedelta(days=get_baghdad_time().weekday())
    cursor.execute("DELETE FROM user_daily_points WHERE date <= ?", (last_monday,))
    connection.commit()
    print("✅ تم تصفير النقاط الأسبوعية!")

def reset_monthly_points():
    now = get_baghdad_time()
    cursor.execute("DELETE FROM user_monthly_points WHERE month = ? AND year = ?", (now.month, now.year))
    connection.commit()
    print("✅ تم تصفير النقاط الشهرية!")

def reset_yearly_points():
    now = get_baghdad_time()
    cursor.execute("DELETE FROM user_yearly_points WHERE year = ?", (now.year,))
    connection.commit()
    print("✅ تم تصفير النقاط السنوية!")



def get_top_hours(period):
    today = get_baghdad_time().date()
    now = get_baghdad_time()
    week_number = now.isocalendar()[1]
    
    if period == 'daily':
        cursor.execute("""
            SELECT user_id, SUM(duration_minutes) / 60.0 AS hours
            FROM study_sessions
            WHERE session_date = ?
            GROUP BY user_id
            ORDER BY hours DESC
            LIMIT 60
        """, (today,))
    elif period == 'weekly':
        week_number = now.isocalendar()[1]
        cursor.execute("""
            SELECT user_id, SUM(duration_minutes) / 60.0 AS hours
            FROM study_sessions
            WHERE session_date >= ?
            GROUP BY user_id
            ORDER BY hours DESC
            LIMIT 60
        """, (week_number,))
    elif period == 'monthly':
        cursor.execute("""
            SELECT user_id, SUM(duration_minutes) / 60.0 AS hours
            FROM study_sessions
            WHERE strftime('%Y-%m', session_date) = strftime('%Y-%m', ?)
            GROUP BY user_id
            ORDER BY hours DESC
            LIMIT 60
        """, (today,))
    elif period == 'yearly':
        cursor.execute("""
            SELECT user_id, SUM(duration_minutes) / 60.0 AS hours
            FROM study_sessions
            WHERE strftime('%Y', session_date) = strftime('%Y', ?)
            GROUP BY user_id
            ORDER BY hours DESC
            LIMIT 60
        """)
    
    return cursor.fetchall()
def update_user_title(user_id, new_title):
    cursor.execute("""
        UPDATE users 
        SET title = ? 
        WHERE user_id = ?
    """, (new_title, user_id))
    connection.commit()

# التحقق من الأعمدة الحالية في الجدول users
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]  # استخراج أسماء الأعمدة

# إضافة العمود فقط إذا لم يكن موجودًا
if 'title' not in column_names:
    cursor.execute("ALTER TABLE users ADD COLUMN title TEXT")  # بدون قيمة افتراضية
    connection.commit()

# إضافة العمود فقط إذا لم يكن موجودًا
if 'referrer_id' not in column_names:
    cursor.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER")
    connection.commit()


# إضافة جدول جديد لتخزين حالة التايمر
cursor.execute('''CREATE TABLE IF NOT EXISTS active_timers (
    channel_id TEXT,
    message_id INTEGER,
    session_type TEXT,
    start_time DATETIME,
    end_time DATETIME,
    duration INTEGER,
    PRIMARY KEY (channel_id, message_id)
)''')

# إضافة جدول لتخزين القنوات
cursor.execute('''CREATE TABLE IF NOT EXISTS user_channels (
    channel_id TEXT PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    added_date DATETIME
)''')
connection.commit()

def is_user_registered_today(user_id):
    today = get_baghdad_time().date()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM challenges 
        WHERE user_id = ? AND last_challenge_date = ?
    """, (user_id, today))
    count = cursor.fetchone()[0]
    return count > 0

# دالة لتسجيل المستخدم للتحدي
def register_user_for_challenge(user_id):
    today = get_baghdad_time().date()
    cursor.execute("""
        INSERT OR REPLACE INTO challenges (user_id, last_challenge_date)
        VALUES (?, ?)
    """, (user_id, today))
    connection.commit()


# تحديث دالة get_user_study_hours لتحسين حساب الساعات
def get_user_study_hours(user_id):
    today = get_baghdad_time().date()
    now = get_baghdad_time()
    week_number = now.isocalendar()[1]
    
    cursor.execute("""
        SELECT 
            COALESCE((SELECT points FROM user_daily_points WHERE user_id = ? AND date = ?), 0) as today_points,
            COALESCE((SELECT SUM(points) FROM user_daily_points WHERE user_id = ? AND date >= ?), 0) as week_points
    """, (user_id, today, user_id, week_number))
    
    result = cursor.fetchone()
    
    # Convert to float with safe default of 0.0 if None
    today_hours = float(result[0] if result[0] is not None else 0)
    week_hours = float(result[1] if result[1] is not None else 0)
    
    return today_hours, week_hours

# إنشاء جدول لتسجيل جلسات المستخدمين إذا لم يكن موجودًا
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        user_id INTEGER,
        session_time DATETIME,
        PRIMARY KEY (user_id, session_time)
    )
""")
connection.commit()

# دالة للتحقق من تسجيل التحدي اليوم
def check_challenge_today(user_id):
    today = get_baghdad_time().date()
    cursor.execute("SELECT last_challenge_date FROM challenges WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        last_date = datetime.datetime.strptime(row[0], '%Y-%m-%d').date()
        return last_date == today  # تحقق مما إذا كان التاريخ هو نفسه اليوم
    return False

# دالة لتحديث تاريخ الضغط الأخير
def update_challenge_date(user_id):
    today = get_baghdad_time().date()
    cursor.execute("REPLACE INTO challenges (user_id, last_challenge_date) VALUES (?, ?)", (user_id, today))
    connection.commit()

# إنشاء جدول القنوات
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    admin_id INTEGER,
    username TEXT,
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
)''')
connection.commit()


# الحل الثالث: إنشاء أمر start خاص للجلسات
async def sessions_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختصار سريع للجلسات من خلال /s"""
    await manage_personal_sessions(update, context)

# إضافة اختصارات متعددة في main()
def add_session_commands(application):
    """إضافة أوامر متعددة للجلسات"""
    
    # الأمر العربي باستخدام MessageHandler
    application.add_handler(MessageHandler(
        filters.Regex("^/جلساتي$"), 
        manage_personal_sessions
    ))
    
    # أوامر إنجليزية
    application.add_handler(CommandHandler("mysessions", manage_personal_sessions))
    application.add_handler(CommandHandler("sessions", manage_personal_sessions))
    application.add_handler(CommandHandler("s", sessions_shortcut))  # اختصار سريع
    
    print("✅ تم إضافة أوامر الجلسات:")
    print("   /جلساتي (عربي)")
    print("   /mysessions (إنجليزي)")
    print("   /sessions (إنجليزي)")
    print("   /s (اختصار)")


def check_user(user_id, username=None, referrer_id=None):
    # البحث عن المستخدم في قاعدة البيانات
    cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:  # ✅ المستخدم جديد تمامًا
        cursor.execute(
            "INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)",
            (user_id, username, referrer_id)
        )
        connection.commit()

        # ✅ تأكيد أن المحيل ليس نفسه المستخدم وأنه موجود
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id=?", (referrer_id,))
            referrer = cursor.fetchone()

            if referrer:  # ✅ فقط إذا كان المحيل موجودًا، أضف له النقاط
                add_points(referrer_id, 3, source="referral")
                return "new_user_with_referrer"
        
        return "new_user_no_referrer"  # ✅ المستخدم جديد لكن بدون محيل

    else:
        # ✅ المستخدم موجود، فقط حدّث اسمه إذا تغيّر
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        connection.commit()
        return "existing_user"


def add_points(user_id, points, source="general"):
    now = get_baghdad_time()
    today = now.date()
    week_number = now.isocalendar()[1]  # رقم الأسبوع حسب ISO

    # إضافة النقاط إلى جدول users
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id=?", (points, user_id))

    # إضافة النقاط إلى جدول user_daily_points
    cursor.execute("""
        INSERT INTO user_daily_points (user_id, points, date)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) 
        DO UPDATE SET points = user_daily_points.points + excluded.points
    """, (user_id, points, today))


    # تحديث النقاط الأسبوعية
    cursor.execute("""
        INSERT INTO user_weekly_points (user_id, points, week, year)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, week, year) DO UPDATE SET points = user_weekly_points.points + excluded.points
    """, (user_id, points, week_number, now.year))


    # إضافة النقاط إلى جدول user_monthly_points
    cursor.execute("""
        INSERT INTO user_monthly_points (user_id, points, month, year)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, month, year) 
        DO UPDATE SET points = user_monthly_points.points + excluded.points
    """, (user_id, points, now.month, now.year))

    # إضافة النقاط إلى جدول user_yearly_points
    cursor.execute("""
        INSERT INTO user_yearly_points (user_id, points, year)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, year) 
        DO UPDATE SET points = user_yearly_points.points + excluded.points
    """, (user_id, points, now.year))

    connection.commit()


# دالة للحصول على عدد النقاط واللقب
def get_points_and_title(user_id):
    cursor.execute("SELECT points, title FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        points, title = result
        title = title if title else ""  # إذا كان اللقب فارغًا، اعرض "بدون لقب"
        return points, title
    return 0, ""  # إذا لم يكن المستخدم موجودًا

def get_daily_points(limit=60):
    today = get_baghdad_time().date()
    cursor.execute("""
        SELECT user_id, points  -- ✅ جلب user_id أيضًا
        FROM user_daily_points 
        WHERE date = ? 
        ORDER BY points DESC 
        LIMIT ?
    """, (today, limit))
    return cursor.fetchall()  # ✅ الآن ستعيد [(user_id, points), (user_id, points), ...]


def get_monthly_points(limit=60):
    now = get_baghdad_time()
    cursor.execute("""
        SELECT user_id, points 
        FROM user_monthly_points 
        WHERE month = ? AND year = ? 
        ORDER BY points DESC 
        LIMIT ?
    """, (now.month, now.year, limit))
    return cursor.fetchall()

def get_yearly_points_top():  # Renamed to avoid conflict
    now = get_baghdad_time()
    cursor.execute("""
        SELECT user_id, points 
        FROM user_yearly_points 
        WHERE year = ? 
        ORDER BY points DESC 
        LIMIT 60
    """, (now.year,))
    return cursor.fetchall()

def get_participation_points(limit=30):
    cursor.execute("""
        SELECT user_id, 
            (SELECT COUNT(*) FROM users u2 WHERE u2.referrer_id = users.user_id) as referral_count
        FROM users 
        ORDER BY referral_count DESC 
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def get_user_rank(user_id, category):
    now = get_baghdad_time()
    print(f"Category: {category}, User ID: {user_id}, Now: {now}")
    # بقية الدالة كما هي
    try:
        if category == 'monthly':
            cursor.execute("""
                SELECT COUNT(*) + 1 
                FROM user_monthly_points 
                WHERE points > (
                    SELECT points FROM user_monthly_points 
                    WHERE user_id = ? AND month = ? AND year = ?
                ) AND month = ? AND year = ?
            """, (user_id, now.month, now.year, now.month, now.year))
        elif category == 'daily':
            cursor.execute("""
                SELECT COUNT(*) + 1 
                FROM user_daily_points 
                WHERE points > (
                    SELECT points FROM user_daily_points 
                    WHERE user_id = ? AND date = ?
                ) AND date = ?
            """, (user_id, now.date(), now.date()))
        elif category == 'yearly':
            cursor.execute("""
                SELECT COUNT(*) + 1 
                FROM user_yearly_points 
                WHERE points > (
                    SELECT points FROM user_yearly_points 
                    WHERE user_id = ? AND year = ?
                ) AND year = ?
            """, (user_id, now.year, now.year))

        # التحقق من النتيجة وإرجاع القيمة الافتراضية إذا لم يتم العثور على نقاط
        result = cursor.fetchone()
        return result[0] if result else "خارج الترتيب"
    except Exception as e:
        print(f"خطأ أثناء حساب ترتيب المستخدم: {e}")
        return "خطأ"

def add_daily_points(user_id, points):
    today = get_baghdad_time().date()
    cursor.execute("""
        INSERT INTO user_daily_points (user_id, date, points)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET points = points + excluded.points
    """, (user_id, today, points))
    connection.commit()

def get_yearly_points(user_id):
    now = get_baghdad_time()
    cursor.execute("""
        SELECT points 
        FROM user_yearly_points 
        WHERE user_id = ? AND year = ?
    """, (user_id, now.year))
    result = cursor.fetchone()
    return result[0] if result else 0

def add_monthly_points(user_id, points):
    now = get_baghdad_time()
    cursor.execute("""
        INSERT INTO user_monthly_points (user_id, points, month, year) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, month, year) 
        DO UPDATE SET points = points + excluded.points
    """, (user_id, points, now.month, now.year))
    connection.commit()

def add_yearly_points(user_id, points):
    now = get_baghdad_time()
    cursor.execute("""
        INSERT INTO user_yearly_points (user_id, points, year) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, year) 
        DO UPDATE SET points = user_yearly_points.points + excluded.points
    """, (user_id, points, now.year))
    connection.commit()


# تحديث دالة التهيئة
def initialize_personal_sessions():
    """تهيئة شاملة لنظام الجلسات الشخصية"""
    try:
        # إنشاء قواعد البيانات
        init_personal_sessions_db()
        init_session_control_db()
        
        print("✅ تم تهيئة نظام الجلسات الشخصية بنجاح")
        
    except Exception as e:
        print(f"❌ خطأ في التهيئة: {e}")

######################للمستخدم الشخصي##################

# إنشاء جدول الجلسات الشخصية
def init_personal_sessions_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_sessions (
            user_id INTEGER,
            session_number INTEGER,
            start_hour INTEGER,
            start_minute INTEGER,
            duration INTEGER,
            ref_code TEXT,
            PRIMARY KEY (user_id, session_number)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_session_states (
            user_id INTEGER PRIMARY KEY,
            state TEXT,
            selected_time TEXT,
            editing_session INTEGER
        )
    """)
    connection.commit()

# تهيئة قاعدة البيانات
init_personal_sessions_db()


# إنشاء جدول الجلسات الشخصية
def init_personal_sessions_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_sessions (
            user_id INTEGER,
            session_number INTEGER,
            start_hour INTEGER,
            start_minute INTEGER,
            duration INTEGER,
            ref_code TEXT,
            PRIMARY KEY (user_id, session_number)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_session_states (
            user_id INTEGER PRIMARY KEY,
            state TEXT,
            selected_time TEXT,
            editing_session INTEGER
        )
    """)
    connection.commit()

# جلب أو إنشاء رمز الإحالة للمستخدم
def get_or_create_user_ref_code(user_id):
    cursor.execute("SELECT ref_code FROM personal_sessions WHERE user_id = ? LIMIT 1", (user_id,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        # إنشاء رمز إحالة جديد
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM personal_sessions")
        count = cursor.fetchone()[0]
        new_ref_code = f"ref_{count + 1}"  # بدء من ref_1 للمستخدمين
        return new_ref_code

# جلب الجلسات الشخصية للمستخدم
def get_user_personal_sessions(user_id):
    cursor.execute("""
        SELECT session_number, start_hour, start_minute, duration
        FROM personal_sessions 
        WHERE user_id = ? 
        ORDER BY session_number
    """, (user_id,))
    return cursor.fetchall()

# إضافة جلسة شخصية
def add_personal_session(user_id, start_hour, start_minute, duration, context=None):
    ref_code = get_or_create_user_ref_code(user_id)
    cursor.execute("""
        SELECT MAX(session_number) FROM personal_sessions WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    next_session_number = (result[0] or 0) + 1
    cursor.execute("""
        INSERT OR REPLACE INTO personal_sessions 
        (user_id, session_number, start_hour, start_minute, duration, ref_code)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, next_session_number, start_hour, start_minute, duration, ref_code))
    connection.commit()

    # إعادة جدولة جميع قنوات المستخدم (والخاص)
    cursor.execute("SELECT channel_id FROM user_channels WHERE user_id = ?", (user_id,))
    channels = cursor.fetchall()
    if context:
        for (channel_id,) in channels:
            schedule_channel_messages(context, channel_id, user_id)
        # إعادة جدولة الخاص
        schedule_channel_messages(context, user_id, user_id)

    return next_session_number

def delete_personal_session(user_id, session_number, context=None):
    cursor.execute("""
        DELETE FROM personal_sessions 
        WHERE user_id = ? AND session_number = ?
    """, (user_id, session_number))
    connection.commit()

    # إذا لم يعد هناك جلسات شخصية، أعد جدولة القنوات والخاص للجلسات العامة
    if not get_user_personal_sessions(user_id) and context:
        cursor.execute("SELECT channel_id FROM user_channels WHERE user_id = ?", (user_id,))
        channels = cursor.fetchall()
        for (channel_id,) in channels:
            schedule_channel_messages(context, channel_id, user_id)
        schedule_channel_messages(context, user_id, user_id)

# تحديث حالة المستخدم
def update_user_state(user_id, state, selected_time=None, editing_session=None):
    cursor.execute("""
        INSERT OR REPLACE INTO user_session_states 
        (user_id, state, selected_time, editing_session)
        VALUES (?, ?, ?, ?)
    """, (user_id, state, selected_time, editing_session))
    connection.commit()

# جلب حالة المستخدم
def get_user_state(user_id):
    cursor.execute("""
        SELECT state, selected_time, editing_session 
        FROM user_session_states WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    return result if result else (None, None, None)

# تحويل الوقت من 24 ساعة إلى 12 ساعة
def format_12_hour(hour, minute):
    period = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {period}"

# حساب الوقت المتبقي في اليوم
def calculate_remaining_time(sessions):
    total_study_minutes = sum(duration for _, _, _, duration in sessions)
    remaining_minutes = 24 * 60 - total_study_minutes
    remaining_hours = remaining_minutes // 60
    remaining_mins = remaining_minutes % 60
    return remaining_hours, remaining_mins





# دالة جلب الجلسات الشخصية للمستخدم بدلاً من العامة
def get_user_study_sessions(context, channel_id, user_id):
    sessions = get_user_personal_sessions(user_id)
    user_sessions = {}
    jobs = context.job_queue.get_jobs_by_name(f"session_{channel_id}_{user_id or 0}")
    for job in jobs:
        job.schedule_removal()

    for _, start_hour, start_minute, duration in sessions:  # تجاهل session_number
        end_hour = (start_hour + (start_minute + duration) // 60) % 24
        end_minute = (start_minute + duration) % 60
        
        user_sessions[(start_hour, start_minute)] = {
            "end_hour": end_hour,
            "end_minute": end_minute,
            "duration": duration,
            "type": f"📕 جلسة دراسية من {format_12_hour(start_hour, start_minute)} إلى {format_12_hour(end_hour, end_minute)}\n\n🕸️{get_combined_quotes()}🕸️\n\n"
        }
    
    return user_sessions
###############################################################
#اذاعه

# إنشاء قواعد البيانات المطلوبة
def init_broadcast_custom_db():
    # جدول الأوامر المخصصة
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT UNIQUE,
            points INTEGER,
            description TEXT,
            created_by INTEGER,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # جدول تتبع استخدام الأوامر
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_usage (
            user_id INTEGER,
            command TEXT,
            used_at TEXT,
            PRIMARY KEY (user_id, command)
        )
    """)
    
    # جدول حالة الإذاعة
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_states (
            admin_id INTEGER PRIMARY KEY,
            state TEXT,
            message_data TEXT
        )
    """)
    
    connection.commit()

# نظام الإذاعة
BROADCAST_WAITING = "broadcast_waiting"

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر الإذاعة للإدمن"""
    user_id = update.effective_user.id
    
    # حفظ حالة الانتظار
    cursor.execute("""
        INSERT OR REPLACE INTO broadcast_states (admin_id, state)
        VALUES (?, ?)
    """, (user_id, BROADCAST_WAITING))
    connection.commit()
    
    await update.callback_query.edit_message_text(
        "📢 **نظام الإذاعة**\n\n"
        "أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين.\n\n"
        "يمكنك إرسال:\n"
        "• نص عادي\n"
        "• صورة مع نص\n"
        "• فيديو مع نص\n"
        "• ملف مع نص\n"
        "• أي نوع من المحتوى\n\n"
        "اكتب /cancel للإلغاء"
    )

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج رسائل الإذاعة"""
    try:
        # نعمل فقط عندما التحديث هو رسالة (ليست CallbackQuery من زر)
        if getattr(update, "message", None) is None:
            return False

        msg = update.message
        user_id = update.effective_user.id

        # التحقق من حالة الإذاعة
        cursor.execute("""
            SELECT state FROM broadcast_states WHERE admin_id = ?
        """, (user_id,))
        result = cursor.fetchone()

        if not (result and result[0] == BROADCAST_WAITING):
            return False  # ليس في وضع الإذاعة

        # حذف حالة الإذاعة فور بدء المعالجة
        cursor.execute("DELETE FROM broadcast_states WHERE admin_id = ?", (user_id,))
        connection.commit()

        # جلب جميع المستخدمين
        cursor.execute("SELECT DISTINCT user_id FROM users")
        all_users = cursor.fetchall()

        success_count = 0
        fail_count = 0

        await msg.reply_text(
            f"🚀 بدء الإذاعة...\n"
            f"📊 إجمالي المستخدمين: {len(all_users)}"
        )

        # إذاعة الرسالة (نستخدم الدالة المساعدة forward_message_to_user)
        for (target_user_id,) in all_users:
            if target_user_id == user_id:  # تجاهل الإدمن نفسه
                continue

            try:
                await forward_message_to_user(context.bot, target_user_id, msg)
                success_count += 1

                # انتظار قصير لتجنب حدود التليجرام
                if success_count % 20 == 0:
                    await asyncio.sleep(1)

            except Exception as e:
                fail_count += 1
                print(f"فشل في الإرسال للمستخدم {target_user_id}: {e}")

        # إرسال تقرير النتائج
        await msg.reply_text(
            f"✅ **تم الانتهاء من الإذاعة**\n\n"
            f"📤 تم الإرسال بنجاح: {success_count}\n"
            f"❌ فشل الإرسال: {fail_count}\n"
            f"📊 إجمالي المحاولات: {success_count + fail_count}"
        )

        return True

    except Exception as e:
        print(f"Error in handle_broadcast_message: {e}")
        return False


async def forward_message_to_user(bot, user_id, message):
    """إعادة توجيه الرسالة للمستخدم حسب نوعها"""
    try:
        if message.text:
            await bot.send_message(chat_id=user_id, text=message.text)
        elif message.photo:
            await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=message.caption
            )
        elif message.video:
            await bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=message.caption
            )
        elif message.document:
            await bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=message.caption
            )
        elif message.audio:
            await bot.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=message.caption
            )
        elif message.voice:
            await bot.send_voice(
                chat_id=user_id,
                voice=message.voice.file_id,
                caption=message.caption
            )
        elif message.animation:
            await bot.send_animation(
                chat_id=user_id,
                animation=message.animation.file_id,
                caption=message.caption
            )
        else:
            # محاولة نسخ الرسالة كما هي
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
    except Exception as e:
        raise e

# نظام الأوامر المخصصة
async def custom_commands_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إدارة الأوامر المخصصة"""
    user_id = update.effective_user.id
    
    # جلب الأوامر الموجودة
    cursor.execute("""
        SELECT id, command, points, description, is_active
        FROM custom_commands
        ORDER BY created_at DESC
    """)
    commands = cursor.fetchall()
    
    message = "🛠️ **إدارة الأوامر المخصصة**\n\n"
    
    if commands:
        message += "📋 **الأوامر الحالية:**\n\n"
        for cmd_id, command, points, description, is_active in commands:
            status = "🟢 نشط" if is_active else "🔴 معطل"
            message += f"• `/{command}` - {points} نقطة {status}\n"
            if description:
                message += f"  📝 {description}\n"
            message += "\n"
    else:
        message += "📭 لا توجد أوامر مخصصة حتى الآن\n\n"
    
    message += "اختر إجراءً من الأزرار أدناه:"
    
    buttons = [
        [InlineKeyboardButton("➕ إضافة أمر جديد", callback_data="add_custom_command")],
        [InlineKeyboardButton("📊 إحصائيات الأوامر", callback_data="command_stats")],
        [InlineKeyboardButton("🔄 تبديل حالة أمر", callback_data="toggle_command")],
        [InlineKeyboardButton("🗑️ حذف أمر", callback_data="delete_command")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    
    await update.callback_query.edit_message_text(message, reply_markup=markup, parse_mode='Markdown')

# معالج إضافة أمر مخصص
WAITING_COMMAND_NAME = "waiting_command_name"
WAITING_COMMAND_POINTS = "waiting_command_points"
WAITING_COMMAND_DESC = "waiting_command_desc"

async def add_custom_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إضافة أمر مخصص"""
    user_id = update.effective_user.id
    logging.info(f"add_custom_command_handler called by {user_id}")
    cursor.execute("""
        INSERT OR REPLACE INTO broadcast_states (admin_id, state)
        VALUES (?, ?)
    """, (user_id, WAITING_COMMAND_NAME))
    connection.commit()
    
    await update.callback_query.edit_message_text(
        "➕ **إضافة أمر مخصص جديد**\n\n"
        "🔤 اكتب اسم الأمر (بدون /)\n"
        "مثال: `هدية` أو `مكافأة`\n\n"
        "📝 ملاحظة: الأمر يجب أن يكون كلمة واحدة\n\n"
        "اكتب /cancel للإلغاء",
        parse_mode='Markdown'
    )


async def handle_custom_command_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إنشاء الأوامر المخصصة"""
    try:
        # logging لسهولة تتبع المشكلة
        msg = getattr(update, "message", None) or getattr(update, "edited_message", None)
        logging.info(f"handle_custom_command_creation invoked. has_msg={msg is not None} user={getattr(update.effective_user,'id',None)} text={getattr(msg,'text',None) if msg else None}")
        if msg is None:
            return False

        text = (msg.text or "").strip()
        user_id = update.effective_user.id

        # إلغاء سريع إذا كتب المستخدم /cancel
        if text == "/cancel":
            cursor.execute("DELETE FROM broadcast_states WHERE admin_id = ?", (user_id,))
            connection.commit()
            await msg.reply_text("تم إلغاء إضافة الأمر.")
            return True

        # جلب الحالة الحالية
        cursor.execute("""
            SELECT state, message_data FROM broadcast_states WHERE admin_id = ?
        """, (user_id,))
        result = cursor.fetchone()

        if not result:
            return False

        state, message_data = result

        # قبول أسماء تحتوي حروف عربية/لاتينية/أرقام و _ بدون مسافات، طول بين 2-20
        name_pattern = re.compile(r'^[\w\u0600-\u06FF]{2,20}$', re.UNICODE)

        if state == WAITING_COMMAND_NAME:
            # التحقق من صحة اسم الأمر (كلمة واحدة فقط)
            if not text or " " in text or not name_pattern.match(text):
                await msg.reply_text(
                    "❌ اسم الأمر يجب أن يكون:\n"
                    "• كلمة واحدة فقط (بدون مسافات)\n"
                    "• بين 2-20 حرف/رقم/_\n\n"
                    "جرب مرة أخرى أو اكتب /cancel للإلغاء"
                )
                return True

            # التحقق من عدم وجود الأمر مسبقاً
            cursor.execute("SELECT command FROM custom_commands WHERE command = ?", (text,))
            if cursor.fetchone():
                await msg.reply_text(
                    f"❌ الأمر `/{text}` موجود مسبقاً!\n"
                    "اختر اسماً آخر:",
                    parse_mode='Markdown'
                )
                return True

            # حفظ اسم الأمر والانتقال للمرحلة التالية
            cursor.execute("""
                UPDATE broadcast_states 
                SET state = ?, message_data = ?
                WHERE admin_id = ?
            """, (WAITING_COMMAND_POINTS, text, user_id))
            connection.commit()

            await msg.reply_text(
                f"✅ اسم الأمر: `/{text}`\n\n"
                f"💰 الآن اكتب عدد النقاط التي سيحصل عليها المستخدم:\n"
                f"مثال: `10` أو `50`\n\nاكتب /cancel للإلغاء",
                parse_mode='Markdown'
            )
            return True

        elif state == WAITING_COMMAND_POINTS:
            # التحقق من صحة النقاط
            try:
                points = int(text)
                if points < 1 or points > 1000:
                    raise ValueError()
            except Exception:
                await msg.reply_text(
                    "❌ عدد النقاط يجب أن يكون:\n"
                    "• رقم صحيح\n"
                    "• بين 1 و 1000\n\n"
                    "جرب مرة أخرى أو اكتب /cancel للإلغاء"
                )
                return True

            # message_data يجب أن يحتوي اسم الأمر هنا
            command_name = message_data or ""
            # الانتقال للمرحلة النهائية مع تخزين الاسم والنقاط
            cursor.execute("""
                UPDATE broadcast_states 
                SET state = ?, message_data = ?
                WHERE admin_id = ?
            """, (WAITING_COMMAND_DESC, f"{command_name}|{points}", user_id))
            connection.commit()

            await msg.reply_text(
                f"💰 النقاط: {points}\n\n"
                f"📝 اكتب وصفاً للأمر (اختياري):\n"
                f"أو اكتب `تخطي` للتخطي\n\nاكتب /cancel للإلغاء",
                parse_mode='Markdown'
            )
            return True

        elif state == WAITING_COMMAND_DESC:
            # إنشاء الأمر
            if not message_data:
                await msg.reply_text("❌ حدث خطأ داخلي، حاول من جديد.")
                # تنظيف الحالة
                cursor.execute("DELETE FROM broadcast_states WHERE admin_id = ?", (user_id,))
                connection.commit()
                return True

            command_name, points_str = message_data.split("|")
            points = int(points_str)
            description = text if text != "تخطي" else None

            # إضافة الأمر لقاعدة البيانات
            now = get_baghdad_time().isoformat()
            cursor.execute("""
                INSERT INTO custom_commands 
                (command, points, description, created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (command_name, points, description, user_id, now))
            connection.commit()

            # حذف الحالة
            cursor.execute("DELETE FROM broadcast_states WHERE admin_id = ?", (user_id,))
            connection.commit()

            await msg.reply_text(
                f"🎉 **تم إنشاء الأمر بنجاح!**\n\n"
                f"📋 **تفاصيل الأمر:**\n"
                f"• الأمر: `/{command_name}`\n"
                f"• النقاط: {points}\n"
                f"• الوصف: {description or 'بدون وصف'}\n\n"
                f"✅ الأمر نشط ويمكن للمستخدمين استخدامه الآن!",
                parse_mode='Markdown'
            )
            return True

        return False

    except Exception as e:
        logging.exception("Error in handle_custom_command_creation")
        return False

# معالج استخدام الأوامر المخصصة
async def handle_custom_command_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تنفيذ الأوامر المخصصة"""
    user_id = update.effective_user.id
    command_text = update.message.text[1:]  # إزالة /

    # البحث عن الأمر
    cursor.execute("""
        SELECT command, points, description, is_active
        FROM custom_commands
        WHERE command = ? AND is_active = 1
    """, (command_text,))
    command_info = cursor.fetchone()
    if not command_info:
        return False  # الأمر غير موجود أو معطل

    command, points, description, is_active = command_info

    # التحقق من عدم استخدام المستخدم للأمر مسبقاً
    cursor.execute("""
        SELECT used_at FROM command_usage
        WHERE user_id = ? AND command = ?
    """, (user_id, command))
    already_used = cursor.fetchone()

    # استثناء خاص لأمر start
    if command == "start":
        if not already_used:
            # إضافة النقاط وتسجيل الاستخدام
            add_points(user_id, points, source="custom_command")
            now = get_baghdad_time().isoformat()
            cursor.execute("""
                INSERT INTO command_usage (user_id, command, used_at)
                VALUES (?, ?, ?)
            """, (user_id, command, now))
            connection.commit()
            # إظهار قائمة الأزرار الرئيسية
            await start(update, context)
        # إذا استخدمه من قبل: لا ترسل أي رد
        return True

    # باقي الأوامر: السلوك المعتاد
    if already_used:
        await update.message.reply_text(
            f"⚠️ لقد استخدمت الأمر `/{command}` من قبل!\n"
            f"كل أمر يمكن استخدامه مرة واحدة فقط.",
            parse_mode='Markdown'
        )
        return True

    # إضافة النقاط للمستخدم (تضاف لجميع الجداول: يومي، شهري، سنوي، إجمالي)
    add_points(user_id, points, source="custom_command")

    # تسجيل الاستخدام
    now = get_baghdad_time().isoformat()
    cursor.execute("""
        INSERT INTO command_usage (user_id, command, used_at)
        VALUES (?, ?, ?)
    """, (user_id, command, now))
    connection.commit()

    # رسالة التأكيد
    message = f"🎉 **تهانينا!**\n\n"
    message += f"💰 حصلت على {points} نقطة من الأمر `/{command}`\n"
    if description:
        message += f"📝 {description}\n"
    message += f"\n✨ بعد ما تكدر تستخدم هذا الأمر مرة ثانية، جرب أوامر ثانية أو انتظر مسابقات جديدة "
# ...existing code...
    await update.message.reply_text(message, parse_mode='Markdown')
    return True

async def command_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات الأوامر المخصصة"""
    # تأكد من تأهيل أسماء الأعمدة لتجنب الغموض
    cursor.execute("""
        SELECT cu.command AS command, COUNT(*) as usage_count, SUM(cc.points) as total_points
        FROM command_usage cu
        JOIN custom_commands cc ON cu.command = cc.command
        GROUP BY cu.command
    """)
    stats = cursor.fetchall()
    
    message = "📊 **إحصائيات الأوامر المخصصة**\n\n"
    
    if stats:
        for command, usage_count, total_points in stats:
            message += f"• `/{command}`:\n"
            message += f"  👥 عدد المستخدمين: {usage_count}\n"
            message += f"  💰 مجموع النقاط: {total_points}\n\n"
    else:
        message += "📭 لا توجد إحصائيات حتى الآن\n\n"
    
    buttons = [
        [InlineKeyboardButton("🔙 رجوع", callback_data='custom_commands')]
    ]
    markup = InlineKeyboardMarkup(buttons)
    
    # update.callback_query قد تكون None إذا استدعيت عبر رسالة عادية
    if getattr(update, "callback_query", None):
        await update.callback_query.edit_message_text(message, reply_markup=markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, reply_markup=markup, parse_mode='Markdown')

async def toggle_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل حالة الأوامر المخصصة"""
    cursor.execute("SELECT command, is_active FROM custom_commands")
    commands = cursor.fetchall()
    
    if not commands:
        await update.callback_query.edit_message_text(
            "❌ لا توجد أوامر مخصصة حتى الآن",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='custom_commands')]])
        )
        return
    
    buttons = []
    for command, is_active in commands:
        status = "🟢" if is_active else "🔴"
        buttons.append([InlineKeyboardButton(f"{status} /{command}", callback_data=f"toggle_{command}")])
    
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data='custom_commands')])
    markup = InlineKeyboardMarkup(buttons)
    
    await update.callback_query.edit_message_text(
        "🔧 **تبديل حالة الأوامر**\n\nاختر الأمر الذي تريد تبديل حالته:",
        reply_markup=markup
    )

async def delete_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف الأوامر المخصصة"""
    cursor.execute("SELECT command FROM custom_commands")
    commands = cursor.fetchall()
    
    if not commands:
        await update.callback_query.edit_message_text(
            "❌ لا توجد أوامر مخصصة حتى الآن",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='custom_commands')]])
        )
        return
    
    buttons = []
    for (command,) in commands:
        buttons.append([InlineKeyboardButton(f"🗑️ /{command}", callback_data=f"delete_{command}")])
    
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data='custom_commands')])
    markup = InlineKeyboardMarkup(buttons)
    
    await update.callback_query.edit_message_text(
        "🗑️ **حذف الأوامر المخصصة**\n\nاختر الأمر الذي تريد حذفه:",
        reply_markup=markup
    )

async def handle_toggle_delete_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار الديناميكية لتبديل وحذف الأوامر"""
    query = update.callback_query
    data = query.data
    
    if data.startswith('toggle_'):
        command_name = data.replace('toggle_', '')
        # تبديل الحالة
        cursor.execute("SELECT is_active FROM custom_commands WHERE command = ?", (command_name,))
        result = cursor.fetchone()
        if result:
            new_status = 0 if result[0] else 1
            cursor.execute("UPDATE custom_commands SET is_active = ? WHERE command = ?", (new_status, command_name))
            connection.commit()
            
            status_text = "مفعّل" if new_status else "معطّل"
            await query.answer(f"تم {status_text} الأمر /{command_name}")
            await custom_commands_handler(update, context)
    
    elif data.startswith('delete_'):
        command_name = data.replace('delete_', '')
        # حذف الأمر
        cursor.execute("DELETE FROM custom_commands WHERE command = ?", (command_name,))
        cursor.execute("DELETE FROM command_usage WHERE command = ?", (command_name,))
        connection.commit()
        
        await query.answer(f"تم حذف الأمر /{command_name}")
        await custom_commands_handler(update, context)
#########################################################
def run_async_job(coro):
    global MAIN_LOOP
    return asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)



def get_user_name_with_title(user_id):
    cursor.execute("SELECT title FROM users WHERE user_id = ?", (user_id,))
    title = cursor.fetchone()
    return title[0] if title else ""
# ألقاب التخصصات
titles = [
    "🩺 الدكت,ور", "🩺 الجراح", "💊 صيدلاني", 
    "🦷 أسنان", "🏗️ المهندس", "💉 المخدر", 
    "📡 الاشعائي", "🧪 المحلل", "🐾 البيطري", 
    "🛫 طيار", "🕵️‍♂️ الجنائي", "💉 الممرض", 
    "⚖️ المحامي", "👨‍🏫 المدرس", "📊 المحاسب", 
    "🌐 المترجم", "👨‍🏫 معلم", "👮‍♂️ ضابط", 
    "💉 إبرة كانونه", "🧹 الفراش", "🔧 العامل", 
    "🎤 السختجي", "🎤 بطران", "😴 دايح"
]

# إنشاء الأزرار بحيث تكون كل 3 أزرار في صف
buttons = [[InlineKeyboardButton(title, callback_data=f'select_title_{title}') for title in titles[i:i+3]] for i in range(0, len(titles), 3)]
# إضافة زر منفرد للمعلومات
buttons.append([InlineKeyboardButton("📘 سعر الالقاب", callback_data='specialization_info')])

# إنشاء الـ InlineKeyboardMarkup
titles_markup = InlineKeyboardMarkup(buttons)

rc = [
    {"name": "م.معمارية", "points_required": 220},
    {"name": "م.مدنية", "points_required": 219},
    {"name": "م.ميكانيكية", "points_required": 218},
    {"name": "م.كهربائية", "points_required": 217},
    {"name": "م.صناعية", "points_required": 216},
    {"name": "م.كيميائية", "points_required": 215},
    {"name": "م.حاسوب", "points_required": 214},
    {"name": "م.نووية", "points_required": 213},
    {"name": "م.زراعية", "points_required": 212},
    {"name": "م.طيران", "points_required": 211},
    {"name": "م.بحرية", "points_required": 210},
    {"name": "م.ذكاء اصطناعي", "points_required": 209},
    {"name": "م.مالية", "points_required": 208},
    {"name": "م.بيئية", "points_required": 207},
    {"name": "م.طاقة متجددة", "points_required": 206}
]

# أقسام الهندسة (Engineering Specializations)
rc_male = [
    {"name": "م.معماري", "points_required": 220},
    {"name": "م.مدني", "points_required": 219},
    {"name": "م.ميكانيكي", "points_required": 218},
    {"name": "م.كهربائي", "points_required": 217},
    {"name": "م.صناعي", "points_required": 216},
    {"name": "م.كيميائي", "points_required": 215},
    {"name": "م.حاسوب", "points_required": 214},
    {"name": "م.نووي", "points_required": 213},
    {"name": "م.زراعي", "points_required": 212},
    {"name": "م.طيران", "points_required": 211},
    {"name": "م.بحري", "points_required": 210},
    {"name": "م.ذكاء اصطناعي", "points_required": 209},
    {"name": "م.مالية", "points_required": 208},
    {"name": "م.بيئي", "points_required": 207},
    {"name": "م.طاقة متجددة", "points_required": 206}
]

met = [
    {"name": "ط.عامة", "points_required": 165},
    {"name": "ط.باطنية", "points_required": 164},
    {"name": "ط.نسائية", "points_required": 163},
    {"name": "ط.اطفال", "points_required": 162},
    {"name": "ط.اسنان", "points_required": 161},
    {"name": "ط.عيون", "points_required": 160},
    {"name": "ط.أنف وأذن وحنجرة", "points_required": 159},
    {"name": "ط.قلبية", "points_required": 158},
    {"name": "ط.جراحة", "points_required": 157},
    {"name": "ط.تخدير", "points_required": 156},
    {"name": "ممرضة", "points_required": 155},
    {"name": "صيدلانية", "points_required": 154},
    {"name": "تحليلات", "points_required": 153},
    {"name": "ط.تجميل", "points_required": 152},
    {"name": "ط.تغذية", "points_required": 151},
    {"name": "ط.نفسية", "points_required": 150},
    {"name": "ط.عظام ومفاصل", "points_required": 149},
    {"name": "ط.بيئية", "points_required": 148},
    {"name": "ط.مختبرات", "points_required": 147}
]

# أقسام طبية (Medical Specializations)
met_male = [
    {"name": "ط.عام", "points_required": 165},
    {"name": "ط.باطنية", "points_required": 164},
    {"name": "ط.نسائية", "points_required": 163},
    {"name": "ط.اطفال", "points_required": 162},
    {"name": "ط.اسنان", "points_required": 161},
    {"name": "ط.عيون", "points_required": 160},
    {"name": "ط.أنف وأذن وحنجرة", "points_required": 159},
    {"name": "ط.قلبية", "points_required": 158},
    {"name": "ط.جراح", "points_required": 157},
    {"name": "ط.تخدير", "points_required": 156},
    {"name": "ممرض", "points_required": 155},
    {"name": "صيدلاني", "points_required": 154},
    {"name": "تحليلات", "points_required": 153},
    {"name": "ط.تجميل", "points_required": 152},
    {"name": "ط.تغذية", "points_required": 151},
    {"name": "ط.نفسي", "points_required": 150},
    {"name": "ط.عظام ومفاصل", "points_required": 149},
    {"name": "ط.بيئي", "points_required": 148},
    {"name": "ط.مختبرات", "points_required": 147}
]
# أقسام التربية والتعليم (Education Specializations)
tr = [
    {"name": "وزيرة التربية", "points_required": 130},
    {"name": "أ.لغة انجليزية", "points_required": 129},
    {"name": "أ.لغة عربية", "points_required": 128},
    {"name": "أ.فيزياء", "points_required": 127},
    {"name": "أ.كيمياء", "points_required": 126},
    {"name": "أ.فنية", "points_required": 125},
    {"name": "أ.رياضة", "points_required": 124},
    {"name": "أ.اسلامية", "points_required": 123},
    {"name": "أ.احياء", "points_required": 122},
    {"name": "أ.رياضيات", "points_required": 121},
    {"name": "أ.علوم", "points_required": 120},
    {"name": "أ.قراءة", "points_required": 119},
    {"name": "مديرة مدرسة", "points_required": 118},
    {"name": "مشرفة", "points_required": 117},
    {"name": "ام الحانوت", "points_required": 116},
    {"name": "حارسة", "points_required": 115},
    {"name": "ام الخط", "points_required": 114}
]

# أقسام التربية والتعليم للذكور (Education Specializations for Males)
tr_male = [
    {"name": "وزير التربية", "points_required": 130},
    {"name": "أ.لغة انجليزية", "points_required": 129},
    {"name": "أ.لغة عربية", "points_required": 128},
    {"name": "أ.فيزياء", "points_required": 127},
    {"name": "أ.كيمياء", "points_required": 126},
    {"name": "أ.فنية", "points_required": 125},
    {"name": "أ.رياضة", "points_required": 124},
    {"name": "أ.اسلامية", "points_required": 123},
    {"name": "أ.احياء", "points_required": 122},
    {"name": "أ.رياضيات", "points_required": 121},
    {"name": "أ.علوم", "points_required": 120},
    {"name": "أ.قراءة", "points_required": 119},
    {"name": "مدير مدرسة", "points_required": 118},
    {"name": "مشرف", "points_required": 117},
    {"name": "ابو الحانوت", "points_required": 116},
    {"name": "حارس", "points_required": 115},
    {"name": "ابو الخط", "points_required": 114}
]

# أقسام فن واعلام للإناث (Media and Arts Specializations for Females)
fn = [
    {"name": "رسامة", "points_required": 140},
    {"name": "مصورة", "points_required": 139},
    {"name": "نحاتة", "points_required": 138},
    {"name": "إعلامية", "points_required": 137},
    {"name": "مُمنتجة", "points_required": 136},
    {"name": "مخرجة سينمائية", "points_required": 135},
    {"name": "مصممة ديكور", "points_required": 134},
    {"name": "مصممة ازياء", "points_required": 133},
    {"name": "ممثلة", "points_required": 132},
    {"name": "كاتبة", "points_required": 131}
]

# أقسام فن واعلام للذكور (Media and Arts Specializations for Males)
fn_male = [
    {"name": "رسام", "points_required": 140},
    {"name": "مصور", "points_required": 139},
    {"name": "نحات", "points_required": 138},
    {"name": "إعلامي", "points_required": 137},
    {"name": "مُمنتج", "points_required": 136},
    {"name": "مخرج سينمائي", "points_required": 135},
    {"name": "مصمم ديكور", "points_required": 134},
    {"name": "مصمم ازياء", "points_required": 133},
    {"name": "ممثل", "points_required": 132},
    {"name": "كاتب", "points_required": 131}
]

# أقسام الأمن والقضاء للإناث (Security and Justice Specializations for Females)
aj = [
    {"name": "وزيرة", "points_required": 150},
    {"name": "محافظة", "points_required": 149},
    {"name": "رئيسة وزراء", "points_required": 148},
    {"name": "رئيسة جمهورية", "points_required": 147},
    {"name": "نائبة", "points_required": 146},
    {"name": "قاضية", "points_required": 145},
    {"name": "محامية", "points_required": 144},
    {"name": "محققة جنائية", "points_required": 143},
    {"name": "محللة جنائية", "points_required": 142},
    {"name": "آمن سيبراني", "points_required": 141},
    {"name": "آمن وطني", "points_required": 140},
    {"name": "مكافحة الإرهاب", "points_required": 139},
    {"name": "مكافحة المخدرات", "points_required": 138},
    {"name": "كابتنة بحرية", "points_required": 137},
    {"name": "كابتنة طيارة", "points_required": 136},
    {"name": "مضيفة طيران", "points_required": 135},
    {"name": "عاملة نظافة", "points_required": 134},
    {"name": "موظفة حكومية", "points_required": 133},
    {"name": "سائقة taxi", "points_required": 132},
    {"name": "سائقة شاحنة", "points_required": 131},
    {"name": "سياسية", "points_required": 130}
]

# أقسام الأمن والقضاء للذكور (Security and Justice Specializations for Males)
aj_male = [
    {"name": "وزير", "points_required": 150},
    {"name": "محافظ", "points_required": 149},
    {"name": "رئيس وزراء", "points_required": 148},
    {"name": "رئيس جمهورية", "points_required": 147},
    {"name": "نائب", "points_required": 146},
    {"name": "قاضي", "points_required": 145},
    {"name": "محامي", "points_required": 144},
    {"name": "محقق جنائي", "points_required": 143},
    {"name": "محلل جنائي", "points_required": 142},
    {"name": "آمن سيبراني", "points_required": 141},
    {"name": "آمن وطني", "points_required": 140},
    {"name": "مكافحة الإرهاب", "points_required": 139},
    {"name": "مكافحة المخدرات", "points_required": 138},
    {"name": "كابتن بحرية", "points_required": 137},
    {"name": "كابتن طيار", "points_required": 136},
    {"name": "مضيف طيران", "points_required": 135},
    {"name": "عامل نظافة", "points_required": 134},
    {"name": "موظف حكومي", "points_required": 133},
    {"name": "سائق taxi", "points_required": 132},
    {"name": "سائق شاحنة", "points_required": 131},
    {"name": "سياسي", "points_required": 130}
]


    # تصفير سنوي - أول يوم من كل سنة
def is_first_day_of_year():
    now = get_baghdad_time()
    return now.day == 1 and now.month == 1


    # تصفير شهري - أول يوم من كل شهر
def is_first_day_of_month():
    now = get_baghdad_time()
    return now.day == 1

# الخطوات في ConversationHandler
ADD_POINTS_STEP, REDUCE_POINTS_STEP, ENTER_POINTS = range(3)

# List of admin user IDs who can access the special button
ADMIN_USERNAMES = ['@Y_HOH0', '@znahdr']  # Replace with actual admin usernames


# تحديث دالة تسجيل المستخدم للعمل مع الجلسات الشخصية
async def register_user_in_personal_session(update: Update, context: ContextTypes.DEFAULT_TYPE, ref_code):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    check_user(user_id, user_name)

    # البحث عن صاحب الجلسة من خلال ref_code
    cursor.execute("""
        SELECT user_id FROM personal_sessions WHERE ref_code = ? LIMIT 1
    """, (ref_code,))
    result = cursor.fetchone()
    
    if not result:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ رمز الجلسة غير صحيح أو منتهي الصلاحية"
        )
        return
    
    session_owner_id = result[0]
    
    # جلب جلسات صاحب الجلسة
    user_sessions = get_user_study_sessions(context, session_owner_id, session_owner_id)
    
    if not user_sessions:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ لا توجد جلسات متاحة حالياً"
        )
        return
    
    now = get_baghdad_time()
    session_found = False
    
    # المرور على جلسات المستخدم الشخصية
    for (hour, minute), session_info in user_sessions.items():
        duration = session_info["duration"]
        session_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        session_end_time = session_time + datetime.timedelta(minutes=duration)
        
        # التحقق إذا كان المستخدم ضمن وقت الجلسة
        if session_time <= now < session_end_time:
            session_found = True
            remaining_time = (session_end_time - now).total_seconds() / 60
            delay_time = duration - remaining_time
            
            # تحديد النقاط حسب وقت الدخول
            if remaining_time > (duration - 15):
                points = 1.0
                delay_msg = "💯 دخلت بالوقت المثالي! ✅"
            elif remaining_time > (duration - 25):
                points = 0.75
                delay_msg = f"⚠️ تأخرت 15 دقيقة عن بداية الجلسة"
            elif remaining_time > (duration - 35):
                points = 0.50
                delay_msg = f"⚠️ تأخرت 25 دقيقة عن بداية الجلسة"
            else:
                points = 0.25
                delay_msg = f"⚠️ تأخرت 35 دقيقة تقريباً عن بداية الجلسة، باقي شوي وتخلص الجلسة!"
            
            if is_user_registered_for_session(user_id, session_time):
                # --- حذف رسالة الدعوة من الخاص إذا كانت موجودة ---
                cursor.execute("""
                    SELECT session_number FROM personal_sessions
                    WHERE user_id = ? AND start_hour = ? AND start_minute = ?
                """, (session_owner_id, hour, minute))
                session_row = cursor.fetchone()
                if session_row:
                    session_number = session_row[0]
                    cursor.execute("SELECT message_id FROM session_invites WHERE user_id=? AND session_number=?", (user_id, session_number))
                    row = cursor.fetchone()
                    if row:
                        try:
                            await context.bot.delete_message(chat_id=user_id, message_id=row[0])
                        except Exception:
                            pass
                        cursor.execute("DELETE FROM session_invites WHERE user_id=? AND session_number=?", (user_id, session_number))
                        connection.commit()
                # --- نهاية الحذف ---

                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=random.choice(ALREADY_REGISTERED_PHRASES)
                )
                return
            
            register_user_for_session(user_id, session_time)
            
            # --- حذف رسالة الدعوة من الخاص إذا كانت موجودة ---
            cursor.execute("""
                SELECT session_number FROM personal_sessions
                WHERE user_id = ? AND start_hour = ? AND start_minute = ?
            """, (session_owner_id, hour, minute))
            session_row = cursor.fetchone()
            if session_row:
                session_number = session_row[0]
                cursor.execute("SELECT message_id FROM session_invites WHERE user_id=? AND session_number=?", (user_id, session_number))
                row = cursor.fetchone()
                if row:
                    try:
                        await context.bot.delete_message(chat_id=user_id, message_id=row[0])
                    except Exception:
                        pass
                    cursor.execute("DELETE FROM session_invites WHERE user_id=? AND session_number=?", (user_id, session_number))
                    connection.commit()
            # --- نهاية الحذف ---

            # جدولة إضافة النقاط بعد انتهاء الجلسة
            context.job_queue.run_once(
                send_session_reminder,
                when=session_end_time,
                data={'user_id': user_id, 'points': points}
            )

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ تم تسجيلك في الجلسة!\n\n" + delay_msg + "\n\n⏳ ادرس للآخر حتى تنحسب نقاطك!"
            )
            return
    # إذا ماكو جلسة حالياً
    if not session_found:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=random.choice(NO_SESSION_PHRASES)
        )

NO_SESSION_PHRASES = [
    "❌ ماكو جلسة شخصية حاليا بالقناة، ارتاح شوي 🕸☕ وانتظر الجاية! 💤",
    "😴 بعدك متأخر، الجلسة بعد ما بدت. خذلك استراحة وارجع بعدين!",
    "🕸️ الجلسة بعد ما بلشت، ريّح بالك وخل عينك عالإشعار القادم!",
    "☕️ ارتاح هسه، الجلسة الجاية قريبة إن شاء الله!",
    "💤 ماكو جلسة هسه، استغل الوقت بريّحة شاي أو قهوة!",
    "🕸️ الجلسة بعدها ما بدت، انتظر إشعار البدء ولاتقلق!",
    "😌 بعدك سابق الجلسة، ريّح شوي وارجع بعدين!"
]

ALREADY_REGISTERED_PHRASES = [
    "ℹ️ سجلت بهالجلسة قبل شوي.",
    "✅ أنت مسجل أصلاً بهالجلسة، شد حيلك!",
    "😉 سبق وسجلت، لا تنسى تركز بالدراسة!",
    "🔄 أنت مشارك بهالجلسة من قبل، استمر!",
    "💪 أنت ضمن الجلسة، واصل يا بطل!",
    "📝 اسمك موجود بالقائمة، شد حيلك!",
    "✅ أنت مشارك، لا تشيل هم!"
]
#🌟 شد حيلك وخلينا نشوف الهمة العراقية!\n\n

def points_to_hours_text(points):
    """تحويل النقاط إلى نص الساعات والدقائق"""
    
    if points == 0:
        return "0 دقيقة"
    
    # تحويل النقاط إلى دقائق (افتراض أن كل نقطة = 50 دقيقة)
    total_minutes = int(points * 50)
    
    # حساب الساعات والدقائق
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    # بناء النص
    result = ""
    
    if hours > 0:
        if hours == 1:
            result += "ساعة"
        elif hours == 2:
            result += "ساعتان"
        elif hours <= 10:
            result += f"{hours} ساعات"
        else:
            result += f"{hours} ساعة"
    
    if minutes > 0:
        if result:  # إضافة "و" إذا كانت هناك ساعات
            result += " و "
        
        if minutes == 15:
            result += "ربع ساعة"
        elif minutes == 30:
            result += "نصف ساعة"
        elif minutes == 45:
            result += "ثلاثة أرباع ساعة"
        elif minutes == 1:
            result += "دقيقة"
        elif minutes == 2:
            result += "دقيقتان"
        elif minutes <= 10:
            result += f"{minutes} دقائق"
        else:
            result += f"{minutes} دقيقة"
    
    return result

# دالة بديلة للنقاط الصغيرة
def format_small_points(points):
    """تنسيق خاص للنقاط الصغيرة (أقل من 1)"""
    
    if points >= 1:
        return points_to_hours_text(points)
    
    # للنقاط الصغيرة
    if points == 0.25:
        return "ربع ساعة"
    elif points == 0.5:
        return "نصف ساعة"
    elif points == 0.75:
        return "ثلاثة أرباع ساعة"
    elif points < 0.25:
        return f"{int(points * 50)} دقيقة"
    else:
        return f"{points * 50:.0f} دقيقة"


# تحديث معالج start للتعامل مع رموز الإحالة الشخصية
async def start_with_personal_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and args[0].startswith('ref_'):
        ref_code = args[0]
        #if ref_code == "ref_0":
            # للجلسات العامة - استخدم الدالة العادية
            # Define a simple placeholder for register_user_in_session to avoid NameError
            #async def register_user_in_session(update, context):
                #await context.bot.send_message(
                    #chat_id=update.effective_chat.id,
                    #text="تم تسجيلك في الجلسة العامة!"
                #)
            #await register_user_in_session(update, context)
        #else:
            # للجلسات الشخصية
        await register_user_in_personal_session(update, context, ref_code)#هنا اذا ترجع العامة اترك مسافة
    else:
        # معالج start العادي
        await start(update, context)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_name = update.effective_user.first_name
        user_id = update.effective_user.id
        check_user(user_id, user_name)
        points, title = get_points_and_title(user_id)
        current_username = update.effective_user.username
        is_admin = current_username and current_username.replace('@', '') in [username.replace('@', '') for username in ADMIN_USERNAMES]
        
        # استخراج نص الرسالة لمعرفة رابط الإحالة (إذا وجد)
        message_text = update.message.text if getattr(update, "message", None) else ""
        ref_code = None
        if "start=" in message_text:
            ref_code = message_text.split("start=")[-1].strip()
        elif context.args:
            ref_code = context.args[0]

        # إذا وُجد ref_code وكان يساوي "1" أو "ref_1"، يتم تسجيل الجلسة
        async def register_user_in_session(update, context):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="تم تسجيلك في الجلسة العامة!"
            )

        if ref_code and (ref_code == "1" or ref_code == "ref_1"):
            await register_user_in_session(update, context)
            return

        # إذا كان هناك ref_code ولكن ليس لتسجيل الجلسة، نقوم بمعالجة الإحالة
        referrer_id = None
        if ref_code:
            try:
                referrer_id = int(ref_code.replace("ref_", ""))
                if referrer_id == user_id:
                    referrer_id = None  # تجاهل الإحالة الذاتية
            except ValueError:
                print("⚠️ فشل في تحويل `ref_code` إلى رقم صحيح!")

        # استدعاء دالة check_user مرة واحدة عند تسجيل الدخول
        status = check_user(user_id, user_name, referrer_id)
        if status == "new_user_with_referrer" and referrer_id:
            referrer_message = f"🎉 {user_name} استخدم رابط الدعوة الخاص بك! حصلت على 3 نقاط لأنه مستخدم جديد. 🌟"
            await context.bot.send_message(chat_id=referrer_id, text=referrer_message)
        elif status == "existing_user" and referrer_id:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"⚠️ {user_name} دخل عبر رابطك لكنه كان قد استخدم البوت مسبقًا. لم تُحتسب لك نقاط."
            )

        # رسالة الترحيب وإعداد الأزرار
        message = f"""
⭐️| مرحبًا {user_name} {title},
شلونك اليوم؟ أتمنى لك يومًا مليئًا بالسعادة!
{get_combined_quotes()}
        """
        ref_code = "ref_1"
        user_sessions = get_user_personal_sessions(user_id)
        if user_sessions:
            ref_code = get_or_create_user_ref_code(user_id)

        # زر تفعيل/إيقاف الجلسات الادمن في الخاص
        cursor.execute("""
            SELECT is_active FROM channel_sessions_status
            WHERE channel_id = ? AND user_id = ?
        """, (str(user_id), user_id))
        result = cursor.fetchone()
        private_active = result[0] if result is not None else 1  # افتراضي: مفعّل
        private_emoji = "🟢" if private_active else "🔴"
        private_text = f"{private_emoji} الجلسات في الخاص"

        buttons = [
            [InlineKeyboardButton("تسجيل للجلسة", url=f"https://t.me/Challen96bot?start={ref_code}")],
            [InlineKeyboardButton("شرح البوت", callback_data='help')],
            [InlineKeyboardButton("ساعاتي", callback_data='my_hours')],
            [InlineKeyboardButton("نقاطي", callback_data='my_points')],
            [InlineKeyboardButton("توب", callback_data='top')],
            [InlineKeyboardButton("المشاركة", callback_data='share')],
            [InlineKeyboardButton("اختر تخصصك", callback_data='choose_title')]
        ]

        # إضافة أزرار الإدمن إذا كان المستخدم أدمن
        if is_admin:
            admin_buttons = [
                [InlineKeyboardButton("اضافه نقاط", callback_data='add_points'),
                 InlineKeyboardButton("تقليل نقاط", callback_data='reduce_points')],
                [InlineKeyboardButton("نشر الجلسات", callback_data='add_channel'),
                 InlineKeyboardButton("إدارة قنوات المستخدمين", callback_data='manage_user_channels')],
                [InlineKeyboardButton("إدارة جلسات المستخدمين", callback_data='manage_user_sessions')],
                [InlineKeyboardButton("📢 الإذاعة", callback_data='broadcast'),
                 InlineKeyboardButton("🛠️ الأوامر المخصصة", callback_data='custom_commands')]
            ]
            buttons.extend(admin_buttons)

        inline_markup = InlineKeyboardMarkup(buttons)

        # إرسال الرسالة أو تعديلها حسب نوع الاستدعاء
        if getattr(update, "message", None):
            await update.message.reply_text(text=message.strip(), reply_markup=inline_markup)
        elif getattr(update, "callback_query", None):
            try:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(text=message.strip(), reply_markup=inline_markup)
            except Exception as e:
                if "Message is not modified" in str(e):
                    pass  # تجاهل الخطأ إذا لم يتغير شيء
                else:
                    print(f"❌ خطأ في دالة start: {e}")

    except Exception as e:
        print(f"❌ خطأ في دالة start: {e}")
        error_msg = "اضغط /start للبدأ."
        if getattr(update, "message", None):
            await update.message.reply_text(error_msg)
        elif getattr(update, "callback_query", None):
            try:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(error_msg)
            except Exception:
                pass
async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username  # جلب يوزر البوت تلقائياً
    add_admin_url = f"https://t.me/{bot_username}?startchannel=add"

    instructions = """
📢 لنشر الجلسات في قناتك أو مجموعتك، يجب:
2️⃣ إرسال معرف القناة/المجموعة (@username) أو الرابط

سيتم إرسال رسائل تذكير يومياً في الأوقات المحددة ⏰
"""
    keyboard = [
        [InlineKeyboardButton("طلب رقم 1: إضافة البوت كمشرف", url=add_admin_url)]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    context.user_data['waiting_for_channel'] = True
    await update.callback_query.edit_message_text(text=instructions, reply_markup=markup)

async def handle_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_channel'):
        return

    channel_link = update.message.text.strip()
    user_id = update.effective_user.id
    current_time = datetime.datetime.now(baghdad_tz)
    chat_id = None
    channel_username = None

    # دعم جميع الأنواع: قناة عامة، قناة خاصة، مجموعة
    if channel_link.startswith('@'):
        channel_username = channel_link.lstrip('@')
        chat_id = f"@{channel_username}"
    elif channel_link.startswith('https://t.me/'):
        if '/c/' in channel_link:
            chat_id = channel_link
            channel_username = None
        else:
            channel_username = channel_link.split('/')[-1]
            chat_id = f"@{channel_username}"
    elif channel_link.startswith('-100'):
        chat_id = int(channel_link)
        channel_username = None
    elif channel_link.isalnum() or (channel_link.replace('_', '').isalnum()):  # <-- دعم يوزر بدون @
        channel_username = channel_link
        chat_id = f"@{channel_username}"
    else:
        await update.message.reply_text("❌ صيغة الرابط أو المعرف غير مدعومة.")
        return

    try:
        chat = await context.bot.get_chat(chat_id)
        bot_member = await chat.get_member(context.bot.id)
        try:
            user_member = await chat.get_member(user_id)
        except Exception:
            user_member = None

        # جلب جميع المشرفين
        admins = await context.bot.get_chat_administrators(chat.id)
        admin_ids = [admin.user.id for admin in admins] if admins else []

        # تحقق من صلاحيات البوت (للقنوات فقط)
        if chat.type in ['channel', 'supergroup']:
            if chat.type == 'channel' and not bot_member.can_post_messages:
                await update.message.reply_text("❌ يجب أن يكون البوت مشرفاً بصلاحية إرسال الرسائل!")
                return

        # إذا لم يوجد أي مالك أو مشرفين
        if not admins or len(admins) == 0:
            members_count = await context.bot.get_chat_members_count(chat.id)
            if members_count < 50:
                await update.message.reply_text("❌ لا يمكن تفعيل البوت، لا يوجد مشرفين وعدد الأعضاء أقل من 50.")
                return
            # تقييد البوت مؤقتاً
            cursor.execute("""
                INSERT OR REPLACE INTO user_channels (channel_id, user_id, username, added_date)
                VALUES (?, ?, ?, ?)
            """, (str(chat.id), user_id, channel_username or chat.title, current_time))
            connection.commit()
            # إرسال رسالة في القناة/المجموعة تطلب من المالك أو مشرف جديد كتابة "تفعيل"
            await context.bot.send_message(
                chat_id=chat.id,
                text="🚫 البوت مقيد مؤقتاً لأنه لا يوجد مشرفين أو مالك في القناة/المجموعة.\n"
                     "إذا كنت المالك أو مشرف جديد، اكتب كلمة (تفعيل) هنا لتفعيل البوت."
            )
            await update.message.reply_text("🚫 تم تقييد البوت مؤقتاً في القناة/المجموعة. أرسل كلمة (تفعيل) من حساب مشرف أو مالك ليتم التفعيل.")
            context.user_data['waiting_for_channel'] = False
            return

        # إذا المستخدم ليس مشرف أو مالك
        is_owner_or_admin = user_member and user_member.status in ["creator", "administrator"]
        if not is_owner_or_admin:
            members_count = await context.bot.get_chat_members_count(chat.id)
            if members_count < 50:
                await update.message.reply_text("❌ لا يمكنك إضافة القناة لأنك لست مالكًا أو مشرفًا وعدد الأعضاء أقل من 50.")
                return
            await context.bot.send_message(
                chat_id=chat.id,
                text="👤 أضف البوت كمشرف ثم اطلب من المالك أو مشرف جديد كتابة (تفعيل) هنا ليتم تفعيل البوت."
            )
            await update.message.reply_text("🚫 تم تقييد البوت مؤقتاً. يجب رفع البوت مشرف ثم كتابة (تفعيل) من حساب مشرف أو مالك.")
            context.user_data['waiting_for_channel'] = False
            return

        # التحقق من وجود القناة مسبقاً
        cursor.execute("SELECT channel_id FROM user_channels WHERE channel_id = ?", (str(chat.id),))
        existing_channel = cursor.fetchone()
        if existing_channel:
            await update.message.reply_text("⚠️ هذه القناة/المجموعة مضافة مسبقًا!")
            return

        # تخزين معلومات القناة/المجموعة
        cursor.execute("""
            INSERT OR REPLACE INTO user_channels (channel_id, user_id, username, added_date)
            VALUES (?, ?, ?, ?)
        """, (str(chat.id), user_id, channel_username or chat.title, current_time))
        connection.commit()

        # جدولة الجلسات (شخصية أو عامة)
        is_personal = schedule_channel_messages(context, chat.id, user_id)
        session_type = "شخصية" if is_personal else "عامة"
        await update.message.reply_text(
            f"✅ تم إضافة القناة/المجموعة! ستبدأ الجلسات ال{session_type} تلقائياً.\n"
            f"🎮 استخدم /control للتحكم في الجلسات"
        )

    except Exception as e:
        print(f"Error adding channel/group: {e}")
        await update.message.reply_text("❌ حدث خطأ. تأكد من صحة الرابط وصلاحيات البوت.")

    context.user_data['waiting_for_channel'] = False

async def activation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text.strip().lower() == "تفعيل":
        chat = update.effective_chat
        user_id = update.effective_user.id
        try:
            member = await context.bot.get_chat_member(chat.id, user_id)
            if member.status in ["creator", "administrator"]:
                # إلغاء التقييد (تفعيل البوت)
                # يمكنك هنا تحديث قاعدة البيانات إذا كنت تخزن حالة التقييد
                await update.message.reply_text("✅ تم تفعيل البوت بنجاح! سيبدأ نشر الجلسات.")
                # يمكنك هنا إعادة جدولة الجلسات إذا كانت متوقفة
                schedule_channel_messages(context, chat.id, user_id)
            else:
                await update.message.reply_text("❌ فقط المالك أو المشرف يمكنه تفعيل البوت.")
        except Exception as e:
            print(f"Error in activation_handler: {e}")


# لوحة التحكم في الجلسات
async def sessions_control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # جلب قنوات المستخدم
    cursor.execute("""
        SELECT uc.channel_id, uc.username, css.is_active, css.is_personal
        FROM user_channels uc
        LEFT JOIN channel_sessions_status css ON uc.channel_id = css.channel_id AND css.user_id = ?
        WHERE uc.user_id = ?
    """, (user_id, user_id))
    
    channels = cursor.fetchall()
    
    if not channels:
        await update.message.reply_text("❌ لم تقم بإضافة أي قنوات بعد!")
        return
    
    # إنشاء الأزرار
    keyboard = []
    
    # زر التحكم العام
    total_active = sum(1 for _, _, is_active, _ in channels if is_active)
    total_channels = len(channels)
    
    if total_active == total_channels:
        control_text = "⏸️ إيقاف جميع الجلسات"
        control_action = "stop_all_sessions"
    elif total_active == 0:
        control_text = "▶️ تشغيل جميع الجلسات"
        control_action = "start_all_sessions"
    else:
        control_text = f"🎮 التحكم العام ({total_active}/{total_channels})"
        control_action = "toggle_all_sessions"
    
    keyboard.append([InlineKeyboardButton(control_text, callback_data=control_action)])
    
    # أزرار القنوات الفردية
    for channel_id, username, is_active, is_personal in channels:
        is_active = is_active if is_active is not None else 1
        is_personal = is_personal if is_personal is not None else 0
        
        status_emoji = "🟢" if is_active else "🔴"
        session_type = "شخصية" if is_personal else "عامة"
        action_text = "إيقاف" if is_active else "تشغيل"
        
        button_text = f"{status_emoji} @{username} ({session_type}) - {action_text}"
        callback_data = f"toggle_channel_{channel_id}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # زر إضافة قناة جديدة
    keyboard.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="add_channel")])
    
    markup = InlineKeyboardMarkup(keyboard)
    
    text = "🎮 لوحة التحكم في الجلسات\n\n"
    text += f"📊 الحالة: {total_active}/{total_channels} قنوات نشطة\n"
    text += "🔹 اختر القناة للتحكم في جلساتها"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


# القائمة الأولى - أدعية
PRAYERS_QUOTES = [
    "سبحان الله وبحمده",
    "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد، وهو على كل شيء قدير",
    "سبحان الله العظيم وبحمده",
    "أستغفر الله العظيم وأتوب إليه",
    "لا حول ولا قوة إلا بالله",
    "اللهم صلِّ وسلِّم على نبينا محمد",
    "حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم",
    "سبحان الله، الحمد لله، لا إله إلا الله، الله أكبر",
    "رضيتُ بالله ربًا، وبالإسلام دينًا، وبمحمد ﷺ نبيًا",
    "بسم الله الذي لا يضرُّ مع اسمه شيء في الأرض ولا في السماء وهو السميع العليم",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة",
    "اللهم اغفر لي، وارحمني، واهدني، وعافني، وارزقني",
    "أعوذ بكلمات الله التامات من شر ما خلق",
    "يا حي يا قيوم برحمتك أستغيث، أصلح لي شأني كله ولا تكلني إلى نفسي طرفة عين",
    "أستغفر الله الذي لا إله إلا هو الحي القيوم وأتوب إليه",
    "سبحان الله وبحمده، عدد خلقه، ورضا نفسه، وزنة عرشه، ومداد كلماته",
    "اللهم إني أسألك الجنة وأعوذ بك من النار",
    "اللهم لك الحمد كما ينبغي لجلال وجهك وعظيم سلطانك",
    "اللهم ثبت قلبي على دينك",
    "اللهم إني أسألك من الخير كله عاجله وآجله، وأعوذ بك من الشر كله عاجله وآجله",
    "اللهم اجعلني من أهل القرآن الذين هم أهلك وخاصتك",
    "اللهم اهدني وسددني"
]

def get_combined_quotes():
    """الحصول على رسالتين من القائمتين معاً"""
    prayer = random.choice(PRAYERS_QUOTES)
    return f"{prayer}"

# إنشاء مُجدول واحد عام لتفادي التكرار
scheduler = AsyncIOScheduler()

# إضافة جدول لحالة الجلسات
def init_session_control_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_sessions_status (
            channel_id TEXT,
            user_id INTEGER,
            is_active INTEGER DEFAULT 1,
            is_personal INTEGER DEFAULT 0,
            PRIMARY KEY (channel_id, user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            job_id TEXT PRIMARY KEY,
            channel_id TEXT,
            user_id INTEGER,
            job_type TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    connection.commit()

def schedule_channel_messages(context, channel_id, user_id):
    """جدولة الجلسات - إما شخصية للمستخدم أو عامة"""
    
    sessions_to_use = None
    is_personal = False
    ref_code = "ref_0"
    jobs = list(context.job_queue.jobs())
    for job in jobs:
        # اسم الجوب يكون مثل: session_{channel_id}_{user_id}_{start_hour}_{start_minute}
        if job.name and job.name.startswith(f"session_{channel_id}_{user_id or 0}_"):
            job.schedule_removal()

    if user_id:
        user_sessions = get_user_study_sessions(context, user_id, user_id)
        if user_sessions:
            sessions_to_use = user_sessions
            is_personal = True
            ref_code = get_or_create_user_ref_code(user_id)
            print(f"استخدام الجلسات الشخصية للمستخدم {user_id}")
    
    #if not sessions_to_use:
        #sessions_to_use = STUDY_SESSIONS
        #is_personal = False
        #ref_code = "ref_0"
        #print("استخدام الجلسات العامة")
    
    # حفظ حالة الجلسات
    cursor.execute("""
        INSERT OR REPLACE INTO channel_sessions_status 
        (channel_id, user_id, is_active, is_personal)
        VALUES (?, ?, 1, ?)
    """, (str(channel_id), user_id or 0, 1 if is_personal else 0))
    connection.commit()
    
    # جدولة التوب الأسبوعي
    scheduler = AsyncIOScheduler()
    weekly_job_id = f"weekly_{channel_id}_{user_id or 0}"
    try:
        scheduler.add_job(
            send_weekly_top_and_reset,
            'cron',
            day_of_week='thu',
            hour=23,
            minute=59,
            timezone=baghdad_tz,
            args=[context],
            id=weekly_job_id
        )
        scheduler.start()
    except Exception as e:
        print(f"خطأ في جدولة التوب الأسبوعي: {e}")
    
    # حساب جلسات الاستراحة
    break_sessions = calculate_break_sessions(sessions_to_use)
    all_sessions = {**sessions_to_use, **break_sessions}
    
    print(f"جدولة {len(all_sessions)} جلسة للقناة {channel_id}")
    
    # جدولة جميع الجلسات
    for (start_hour, start_minute), session_info in all_sessions.items():
        job_time = datetime.time(hour=start_hour, minute=start_minute, tzinfo=baghdad_tz)
        
        # حساب المدة
        if 'duration' in session_info:
            duration = session_info['duration']
        else:
            start_datetime = datetime.datetime.combine(datetime.date.today(), 
                datetime.time(start_hour, start_minute))
            end_datetime = datetime.datetime.combine(datetime.date.today(), 
                datetime.time(session_info["end_hour"], session_info["end_minute"]))
            
            if end_datetime < start_datetime:
                end_datetime += datetime.timedelta(days=1)
                
            duration = int((end_datetime - start_datetime).total_seconds() / 60)
        
        # إنشاء job_id فريد
        job_id = f"session_{channel_id}_{user_id or 0}_{start_hour}_{start_minute}"
        
        # جدولة الجلسة
        try:
            context.job_queue.run_daily(
                send_session_message,  # استخدام الدالة المحدثة
                job_time,
                data={
                    'channel_id': channel_id,
                    'user_id': user_id,
                    'start_hour': start_hour,
                    'start_minute': start_minute,
                    'end_hour': session_info["end_hour"],
                    'end_minute': session_info["end_minute"],
                    'session_type': session_info["type"],
                    'duration': duration,
                    'ref_code': ref_code,
                    'is_personal': is_personal
                },
                name=job_id
            )
            print(f"تم جدولة جلسة: {start_hour:02d}:{start_minute:02d}")
            
        except Exception as e:
            print(f"خطأ في جدولة الجلسة {start_hour}:{start_minute}: {e}")
        
        # حفظ معلومات الجوب
        cursor.execute("""
            INSERT OR REPLACE INTO scheduled_jobs 
            (job_id, channel_id, user_id, job_type, is_active)
            VALUES (?, ?, ?, 'session', 1)
        """, (job_id, str(channel_id), user_id or 0))
    
    connection.commit()
    print(f"تم حفظ {len(all_sessions)} جلسة في قاعدة البيانات")
    return is_personal

STUDY_SESSIONS = {
    (5, 0): {"end_hour": 6, "end_minute": 50, "duration": 110, "type": f"📕 جلسة دراسية من 5:00 AM إلى 6:50 AM\n\n🕸️اللهم بك أصبحنا وبك أمسينا، وبك نحيا وبك نموت، وإليك النشور🕸️\n\n"},
    (7, 0): {"end_hour": 7, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 7:00 AM إلى 7:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (8, 0): {"end_hour": 8, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 8:00 AM إلى 8:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (9, 0): {"end_hour": 9, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 9:00 AM إلى 9:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (10, 0): {"end_hour": 10, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 10:00 AM إلى 10:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (11, 0): {"end_hour": 11, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 11:00 AM إلى 11:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (13, 0): {"end_hour": 13, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 1:00 PM إلى 1:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (14, 0): {"end_hour": 14, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 2:00 PM إلى 2:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (15, 0): {"end_hour": 15, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 3:00 PM إلى 3:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (16, 0): {"end_hour": 16, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 4:00 PM إلى 4:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (17, 0): {"end_hour": 17, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 5:00 PM إلى 5:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (19, 0): {"end_hour": 19, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 7:00 PM إلى 7:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (20, 0): {"end_hour": 20, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 8:00 PM إلى 8:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (21, 0): {"end_hour": 21, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 9:00 PM إلى 9:50 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (22, 30): {"end_hour": 23, "end_minute": 20, "duration": 50, "type": f"📕 جلسة دراسية من 10:30 PM إلى 11:20 PM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (0, 1): {"end_hour": 0, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 12:01 AM إلى 12:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (1, 0): {"end_hour": 1, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 1:00 AM إلى 1:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (2, 0): {"end_hour": 2, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 2:00 AM إلى 2:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (3, 0): {"end_hour": 3, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 3:00 AM إلى 3:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
    (4, 0): {"end_hour": 4, "end_minute": 50, "duration": 50, "type": f"📕 جلسة دراسية من 4:00 AM إلى 4:50 AM\n\n🕸️{get_combined_quotes()}🕸️\n\n"},
}

async def send_top_hours_daily(context: ContextTypes.DEFAULT_TYPE):
    """دالة ترسل قائمة التوب اليومية للساعات في الساعة 12:01 AM"""
    job_data = context.job.data
    channel_id = job_data['channel_id']
    today = get_baghdad_time().date()

    # جلب أفضل المستخدمين للساعات اليومية
    cursor.execute("""
            SELECT user_id, points AS hours
            FROM user_daily_points
            WHERE date = ?
            ORDER BY hours DESC
            LIMIT 60
    """, (today,))
    top_users = cursor.fetchall()

    message = "🏆 **توب اليوم - اطول 60 طالب ساعات دراسة ومراجعة:**\n\n"
    for rank, (uid, hours) in enumerate(top_users, 1):
        cursor.execute("SELECT title FROM users WHERE user_id = ?", (uid,))
        result = cursor.fetchone()
        title = result[0] if result and result[0] else ""
        

        # إذا لم يوجد اسم، جلبه من تيليجرام
        if not username:
            try:
                user = await context.bot.get_chat(uid)
                username = user.first_name if user.first_name else "مجهول"
            except Exception:
                username = "غير معروف"

        hours_text = points_to_hours_text(hours)
        if title:
            message += f"{rank}. {username} ({title}) - {hours_text}\n"
        else:
            message += f"{rank}. {username} - {hours_text}\n"

    await context.bot.send_message(
        chat_id=channel_id,
        text=message
    )

def calculate_break_sessions(study_sessions):
    break_sessions = {}
    sorted_times = sorted(study_sessions.items())
    
    for i in range(len(sorted_times) - 1):
        current_session = sorted_times[i]
        next_session = sorted_times[i + 1]
        
        current_end = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time(current_session[1]["end_hour"], current_session[1]["end_minute"])
        )
        next_start = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time(next_session[0][0], next_session[0][1])
        )
        
        if next_start - current_end >= datetime.timedelta(seconds=1):
            break_start = current_end + datetime.timedelta(seconds=2)
            break_end = next_start - datetime.timedelta(seconds=2)
            
            break_sessions[(break_start.hour, break_start.minute)] = {
                "end_hour": break_end.hour,
                "end_minute": break_end.minute,
                "type": "استراحة"
            }
    
    return break_sessions

def is_user_registered_for_session(user_id, session_time):
    cursor.execute("""
        SELECT COUNT(*) FROM user_sessions
        WHERE user_id = ? AND session_time = ?
    """, (user_id, session_time))
    result = cursor.fetchone()
    return result[0] > 0

def register_user_for_session(user_id, session_time):
    cursor.execute("""
        INSERT INTO user_sessions (user_id, session_time)
        VALUES (?, ?)
    """, (user_id, session_time))
    connection.commit()

async def send_session_message(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    channel_id = job_data['channel_id']
    user_id = job_data.get('user_id', 0)
    session_type = job_data['session_type']
    duration = job_data['duration']
    is_personal = job_data.get('is_personal', False)

    # استخراج بيانات الجلسة من job_data
    start_hour = job_data.get('start_hour')
    start_minute = job_data.get('start_minute')
    end_hour = job_data.get('end_hour')
    end_minute = job_data.get('end_minute')

    # حساب رقم الجلسة
    session_number = None
    if is_personal:
        cursor.execute("""
            SELECT session_number FROM personal_sessions
            WHERE user_id = ? AND start_hour = ? AND start_minute = ?
        """, (user_id, start_hour, start_minute))
        result = cursor.fetchone()
        session_number = result[0] if result else 1
    else:
        session_number = list(STUDY_SESSIONS.keys()).index((start_hour, start_minute)) + 1

    # التحقق من حالة الجلسات
    cursor.execute("""
        SELECT is_active FROM channel_sessions_status 
        WHERE channel_id = ? AND user_id = ?
    """, (str(channel_id), user_id))
    result = cursor.fetchone()
    if not result or not result[0]:
        print(f"الجلسات متوقفة للقناة {channel_id}")
        return

    current_time = datetime.datetime.now(baghdad_tz)
    end_time = current_time + datetime.timedelta(minutes=duration)

    session_header = f"⏰ {session_type}\n"
    initial_message = (
        f"{session_header}"
        f"من يخلص👈🏻--:--\n\n"
        f"تكوم تدرس🫵🏻"
    )

    markup = None
    ref_code = job_data.get('ref_code', 'ref_0')
    if "استراحة" not in session_type:
        button_text = "تسجيل للجلسة" if is_personal else "تسجيل للجلسة"
        button = InlineKeyboardButton(button_text, url=f"https://t.me/challen96bot?start={ref_code}")
        markup = InlineKeyboardMarkup([[button]])

    try:
        # 1. إرسال رسالة الجلسة في القناة أولاً
        message = await context.bot.send_message(
            chat_id=channel_id,
            text=initial_message,
            reply_markup=markup
        )

        # 2. حفظ التايمر في قاعدة البيانات
        cursor.execute("""
            INSERT INTO active_timers (channel_id, message_id, session_type, start_time, end_time, duration)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (channel_id, message.message_id, session_type, current_time.isoformat(), end_time.isoformat(), duration))
        connection.commit()

        # 3. حذف رسائل الدعوة القديمة من الخاص (دائماً)
        await delete_session_invites(session_number)

        # 4. إرسال الدعوات للمستخدمين فقط إذا ليست استراحة
        if "استراحة" not in session_type:
            await notify_all_users_new_session(
                context,
                session_number,
                start_hour,
                start_minute,
                end_hour,
                end_minute,
                duration,
                ref_code
            )

        # 5. بدء التايمر
        await update_countdown_updated(
            context, 
            channel_id, 
            message.message_id, 
            duration, 
            session_header,
            ref_code,
            is_personal,
            job_data
        )

    except Exception as e:
        print(f"خطأ في إرسال رسالة الجلسة: {e}")


async def update_countdown_updated(context, channel_id, message_id, duration, session_header, ref_code, is_personal=False, job_data=None):
    try:
        cursor.execute("""
            SELECT end_time FROM active_timers 
            WHERE channel_id = ? AND message_id = ?
        """, (channel_id, message_id))
        result = cursor.fetchone()
        
        if not result:
            print(f"No timer found for channel {channel_id} and message {message_id}")
            return
            
        end_time_dt = datetime.datetime.fromisoformat(result[0])
        
        # إعداد الأزرار
        markup = None
        if "استراحة" not in session_header:
            button_text = "تسجيل للجلسة" if is_personal else "تسجيل للجلسة"
            button = InlineKeyboardButton(button_text, url=f"https://t.me/challen96bot?start={ref_code}")
            markup = InlineKeyboardMarkup([[button]])
        
        # حلقة العد التنازلي
        while True:
            current_time = datetime.datetime.now(baghdad_tz)
            
            # التحقق من انتهاء الوقت
            if current_time >= end_time_dt:
                break
                
            remaining = end_time_dt - current_time
            total_seconds = int(remaining.total_seconds())
            
            # حساب الوقت المتبقي
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            # تنسيق عرض الوقت
            time_display = f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
            
            if "استراحة" in session_header:
                countdown_message = (
                    f"⏰ استراحة\n\n"
                    f"من يخلص👈🏻 {time_display}\n\n"
                    f"تكوم تدرس🫵🏻"
                )
            else:
                countdown_message = (
                    f"{session_header}"
                    f"ادرس الى أن ينتهي 👈🏻 {time_display}\n\n"
                    f"حط فراولة لا تنسى [🍓]"
                )

            try:
                # تحديث الرسالة
                await context.bot.edit_message_text(
                    chat_id=channel_id,
                    message_id=message_id,
                    text=countdown_message,
                    reply_markup=markup
                )
            except Exception as edit_error:
                print(f"Error editing message: {edit_error}")
                # التحقق من وجود الرسالةz
                try:
                    await context.bot.get_chat(channel_id)
                except Exception:
                    print("Channel or message no longer accessible")
                    return
            
            # انتظار 30 ثانية
            await asyncio.sleep(30)
        
        # انتهاء التايمر
        try:
            # حذف من قاعدة البيانات
            cursor.execute("""
                DELETE FROM active_timers 
                WHERE channel_id = ? AND message_id = ?
            """, (channel_id, message_id))
            connection.commit()
            
            # إرسال رسالة الانتهاء
            final_message = f"{session_header}✅ انتهت\n" if "استراحة" not in session_header else "⏰ استراحة انتهت ✅"
            await context.bot.edit_message_text(
                chat_id=channel_id,
                message_id=message_id,
                text=final_message,
                reply_markup=markup
            )

            if "استراحة" not in session_header:
                #try:
                    #await context.bot.delete_message(
                        #chat_id=channel_id,
                        #message_id=message_id
                    #)
                #except Exception as e:
                    #print(f"خطأ أثناء حذف رسالة الجلسة: {e}")
                # تحديد رقم الجلسة بشكل صحيح
                #session_number = None
                if job_data is not None:
                    if job_data.get('is_personal'):
                        # جلسة شخصية
                        cursor.execute("""
                            SELECT session_number FROM personal_sessions
                            WHERE user_id = ? AND start_hour = ? AND start_minute = ?
                        """, (job_data.get('user_id'), job_data.get('start_hour'), job_data.get('start_minute')))
                        result = cursor.fetchone()
                        session_number = result[0] if result else None
                    else:
                        # جلسة عامة
                        session_number = list(STUDY_SESSIONS.keys()).index(
                            (job_data.get('start_hour'), job_data.get('start_minute'))
                        ) + 1
                if session_number:
                    await delete_session_invites(session_number)
# ...existing code...
            else:
                # إذا استراحة فقط، عدل الرسالة للنهاية
                final_message = "⏰ استراحة انتهت ✅"
                await context.bot.edit_message_text(
                    chat_id=channel_id,
                    message_id=message_id,
                    text=final_message,
                    reply_markup=markup
                )
        except Exception as e:
            print(f"Error handling timer completion: {e}")
    except Exception as main_error:
        print(f"Major error in update_countdown: {main_error}")
        print(f"Major error in update_countdown: {main_error}")


# إصلاح دالة فحص التايمرات النشطة
async def check_active_timers(context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.datetime.now(baghdad_tz)
   
    # استرجاع التايمرات النشطة
    cursor.execute("""
        SELECT channel_id, message_id, session_type, start_time, end_time, duration
        FROM active_timers
        WHERE end_time > ?
    """, (current_time,))
    active_timers = cursor.fetchall()
   
    for timer in active_timers:
        channel_id, message_id, session_type, start_time, end_time, duration = timer
        session_header = f"⏰ {session_type}\n"
       
        # التحقق من نوع البيانات وتحويلها إذا لزم الأمر
        if isinstance(start_time, str):
            # إذا كان start_time نص، نحوله إلى datetime
            try:
                start_time_dt = datetime.datetime.fromisoformat(start_time)
                start_time_str = start_time_dt.strftime("%H:%M")
            except:
                # إذا فشل التحويل، استخدم النص مباشرة
                start_time_str = start_time
        else:
            start_time_str = start_time.strftime("%H:%M")
            
        if isinstance(end_time, str):
            try:
                end_time_dt = datetime.datetime.fromisoformat(end_time)
                end_time_str = end_time_dt.strftime("%H:%M")
            except:
                end_time_str = end_time
        else:
            end_time_str = end_time.strftime("%H:%M")
       
        # إعادة تشغيل العد التنازلي للتايمرات النشطة
        await update_countdown_updated(
            context,
            channel_id,
            message_id,
            duration,
            session_header,
            start_time_str,
            end_time_str
        )


# دالة محدثة لمعالجة الأمر
async def manage_personal_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # دعم الاستدعاء من زر أو رسالة
    if hasattr(update, "effective_user"):
        user_id = update.effective_user.id
        user_name = update.from_user.first_name
        check_user(user_id, user_name)
    elif hasattr(update, "from_user"):
        user_id = update.from_user.id
    else:
        user_id = None

    sessions = get_user_personal_sessions(user_id)
    
    if not sessions:
        keyboard = [[InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")]]
        markup = InlineKeyboardMarkup(keyboard)
        text = (
            "📚 إدارة الجلسات الشخصية\n\n"
            "🔹 لا توجد جلسات لك حتى الآن\n\n"
            "💡 استخدم /جلساتي أو /mysessions للوصول لهذه القائمة"
        )
    else:
        text = "📚 جلساتك الشخصية:\n\n"
        for session_number, start_hour, start_minute, duration in sessions:
            end_hour = (start_hour + (start_minute + duration) // 60) % 24
            end_minute = (start_minute + duration) % 60
            start_time_12 = format_12_hour(start_hour, start_minute)
            end_time_12 = format_12_hour(end_hour, end_minute)
            text += f"🔸 الجلسة {session_number}: {start_time_12} إلى {end_time_12} ({duration} دقيقة)\n"
        remaining_hours, remaining_mins = calculate_remaining_time(sessions)
        text += f"\n⏰ باقي {remaining_hours} ساعة و {remaining_mins} دقيقة من اليوم"
        text += "\n💡 الأوقات الأخرى مخصصة للاستراحة\n"
        text += "\n📝 اكتب رقم الجلسة لتعديلها أو حذفها"
        ref_code = get_or_create_user_ref_code(user_id)
        text += f"\n\n🔗 رابط التسجيل في جلساتك:\nhttps://t.me/challen96bot?start={ref_code}"
        keyboard = [[InlineKeyboardButton("➕ إضافة جلسة جديدة", callback_data="add_session")]]
        markup = InlineKeyboardMarkup(keyboard)

    # إرسال الرسالة أو تعديلها حسب نوع الاستدعاء
    if getattr(update, "message", None):
        await update.message.reply_text(text, reply_markup=markup)
    elif getattr(update, "callback_query", None):
        await update.callback_query.edit_message_text(text, reply_markup=markup)

IRAQI_START_PHRASES = [
    "🚨 هااا شباب وبنات!",
    "يلاااا شباب وبنات، الجلسة بدت!",
    "هلا والله، بدت الجلسة الجديدة!",
    "هاااااا، منو جاهز للجلسة؟",
    "يلا قوموا، ",
    "وينكم يا أبطال؟ الجلسة هسه بدت!",
    "يلا نبلش الجلسة، شدوا حيلكم!",
    "هااااا، حضروا أقلامكم ودفاتركم، الجلسة بدت!",
    "يلا يا مبدعين، الجلسة بلشت!"
]

async def notify_all_users_new_session(context, session_number, start_hour, start_minute, end_hour, end_minute, duration, ref_code):

    # جلب المستخدمين حسب ref_code مع استثناء من سجلوا بالفعل
    if ref_code == "ref_1":
        cursor.execute("""
            SELECT user_id FROM users
            WHERE user_id NOT IN (
                SELECT user_id FROM user_sessions WHERE session_time = ?
            )
        """, (f"{start_hour}:{start_minute}",))
        users = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT DISTINCT user_id FROM personal_sessions
            WHERE ref_code = ?
            AND user_id NOT IN (
                SELECT user_id FROM user_sessions WHERE session_time = ?
            )
        """, (ref_code, f"{start_hour}:{start_minute}"))
        users = cursor.fetchall()

    start_time_12 = format_12_hour(start_hour, start_minute)
    end_time_12 = format_12_hour(end_hour, end_minute)

    start_phrase = random.choice(IRAQI_START_PHRASES)
    text = (
        f"{start_phrase}\n"
        f"بدت الجلسة رقم {session_number} 🙌\n"
        f"مدتها {duration} دقيقة\n"
        f"من {start_time_12} إلى {end_time_12}\n\n"
        f"تريد تشارك ويانه بهالجلسة؟"
    )

    keyboard = [
        [InlineKeyboardButton("نعم، أريد أشارك ✅", url=f"https://t.me/Challen96bot?start={ref_code}")],
        [InlineKeyboardButton("لا، بعدين 🙃", callback_data=f"decline_session_{session_number}")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    # أرسل الرسالة لكل مستخدم (بشكل متسلسل لتجنب الحظر) واحفظ message_id
    sent_to = set()
    for (user_id,) in users:
        if user_id in sent_to:
            continue  # لا ترسل مرتين لنفس المستخدم
        sent_to.add(user_id)
        try:
            msg = await context.bot.send_message(chat_id=user_id, text=text, reply_markup=markup)
            cursor.execute(
                "INSERT OR REPLACE INTO session_invites (user_id, session_number, message_id) VALUES (?, ?, ?)",
                (user_id, session_number, msg.message_id)
            )
            connection.commit()
            await asyncio.sleep(0.03)
        except Exception as e:
            print(f"تعذر إرسال رسالة للمستخدم {user_id}: {e}")

async def delete_session_invites(session_number):
    cursor.execute("SELECT user_id, message_id FROM session_invites WHERE session_number=?", (session_number,))
    invites = cursor.fetchall()
    for user_id, message_id in invites:
        try:
            await BOT_INSTANCE.delete_message(chat_id=user_id, message_id=message_id)
        except Exception:
            pass
    cursor.execute("DELETE FROM session_invites WHERE session_number=?", (session_number,))
    connection.commit()

# دالة مساعدة لإصلاح تحويل الوقت
def safe_time_format(time_value):
    """تحويل آمن للوقت إلى نص"""
    if isinstance(time_value, str):
        try:
            # محاولة تحويل النص إلى datetime
            dt = datetime.datetime.fromisoformat(time_value)
            return dt.strftime("%H:%M")
        except:
            # إذا فشل، إرجاع النص كما هو
            return time_value
    elif hasattr(time_value, 'strftime'):
        return time_value.strftime("%H:%M")
    else:
        return str(time_value)

# دالة لبدء فحص التايمرات النشطة عند تشغيل البوت
async def start_timer_check(context: ContextTypes.DEFAULT_TYPE):
    try:
        await check_active_timers(context)
    except Exception as e:
        print(f"خطأ في فحص التايمرات: {e}")

def get_weekly_points(user_id):
    now = get_baghdad_time()
    week_number = now.isocalendar()[1]
    cursor.execute("""
        SELECT points FROM user_weekly_points
        WHERE user_id = ? AND week = ? AND year = ?
    """, (user_id, week_number, now.year))
    result = cursor.fetchone()
    return result[0] if result else 0


def get_weekly_top_points(limit=60):
    now = get_baghdad_time()
    week_number = now.isocalendar()[1]
    cursor.execute("""
        SELECT user_id, points FROM user_weekly_points
        WHERE week = ? AND year = ?
        ORDER BY points DESC
        LIMIT ?
    """, (week_number, now.year, limit))
    return cursor.fetchall()

#المستخدم باي جلسة ردوود التحفيز التحت
def get_sessions_count_today(user_id):
    today = get_baghdad_time().date()
    cursor.execute("""
        SELECT COUNT(*) FROM user_sessions
        WHERE user_id = ? AND DATE(session_time) = ?
    """, (user_id, today))
    result = cursor.fetchone()
    return result[0] if result else 0

def motivational_message(points, sessions_count):
    points_text = format_small_points(points)
    base = f"كفو! كملت الجلسة وانحسبت لك {points_text} و نقطة. ✌🏻\n"
    if sessions_count == 1:
        return base + "بداية حلوة، شد حيلك!"
    elif sessions_count == 2:
        return base + "يلا بعد وحدة وتدخل جو!"
    elif sessions_count == 3:
        return base + "ثلاث جلسات؟ بطل! استمر."
    elif sessions_count == 4:
        return base + "أربع جلسات! اشرب ماي وكمل."
    elif sessions_count == 5:
        return base + "خمس جلسات! لا تنسى ترتاح شوي."
    elif sessions_count >= 6 and sessions_count < 10:
        return base + "🔥 ماكينة دراسة! استمر، وريح شوي."
    elif sessions_count >= 10 and sessions_count < 15:
        return base + "😱 عشرة جلسات! انت اسطورة اليوم."
    elif sessions_count >= 15:
        return base + "🚀 انت فد بطل! بس لا تنسى صحتك."
    else:
        return base + "كل جلسة تقربك لهدفك!"

# ✅ **دالة احتساب النقاط بعد انتهاء الجلسة**
async def send_session_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data  # استرجاع البيانات المخزنة
    user_id = job_data['user_id']
    points = job_data['points']  # استرجاع النقاط المحسوبة مسبقًا

    # **إضافة النقاط بعد انتهاء الجلسة**
    add_points(user_id, points)

    sessions_count = get_sessions_count_today(user_id)
    text = motivational_message(points, sessions_count)
    # **إرسال رسالة تأكيد احتساب النقاط**
    await context.bot.send_message(
        chat_id=user_id,
        text=text
    )

# دالة لمعالجة الأزرار
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data

    # Check if the user is an admin
    current_username = update.effective_user.username
    if query.data == 'share':
        user_id = update.effective_user.id
        total_points, user_title = get_points_and_title(user_id)
        check_user(user_id)

        # إنشاء رابط الدعوة
        invite_link = f"https://t.me/Challen96bot?start={user_id}"
        user_points = get_points_and_title(user_id)

        await context.bot.send_message(
        chat_id=query.message.chat_id,
        text = f"🌟 شارك رابط الإحالة الخاص بك مع أصدقائك لربح النقاط:\n\n"
               f"🔗 رابط الدعوة: {invite_link}\n"
               f"💎 نقاطك الحالية: {total_points}\n\n"
               f"⚡ احصل على 3 نقاط مجانية لكل صديق ينضم باستخدام رابطك!"
        )
    elif query.data == 'add_channel':
        await add_channel_handler(update, context)

    elif query.data == 'choose_title':
        buttons = [
            [InlineKeyboardButton("أقسام الهندسة📐", callback_data='title_rc_male')],
            [InlineKeyboardButton("أقسام طبية 🏥", callback_data='title_met_male')],
            [InlineKeyboardButton("أقسام التربية والتعليم", callback_data='title_tr_male')],
            [InlineKeyboardButton("أقسام آمن و قضاء و عدالة وخدمات عامة", callback_data='title_aj_male')],
            [InlineKeyboardButton("أقسام فن واعلام", callback_data='title_fn_male')],
            [InlineKeyboardButton("🕸سعر الأقسام🕸", callback_data='specialization_info')],
            [InlineKeyboardButton("رجوع", callback_data='back_to_main')]
        ]
    



        markup = InlineKeyboardMarkup(buttons)
        
        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text="اختر القسم المناسب:",
            reply_markup=markup
    )
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(rc), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in rc[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("📋 سعر الألقاب", callback_data='specialization_info')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)


    elif query.data == 'title_rc_male':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(rc_male), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in rc_male[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمؤنث⬅", callback_data='title_rc')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )

    elif query.data == 'title_met_male':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(met_male), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in met_male[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمؤنث⬅", callback_data='title_met')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )
    elif query.data == 'title_tr_male':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(tr_male), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in tr_male[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمؤنث⬅", callback_data='title_tr')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )
    elif query.data == 'title_aj_male':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(aj_male), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in aj_male[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمؤنث⬅", callback_data='title_aj')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )
    elif query.data == 'title_fn_male':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(fn_male), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in fn_male[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمؤنث⬅", callback_data='title_fn')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )



    elif query.data == 'title_rc':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(rc), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in rc[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمذكر➡", callback_data='title_rc_male')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )
    elif query.data == 'title_met':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(met), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in met[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمذكر➡", callback_data='title_met_male')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )
    elif query.data == 'title_tr':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(tr), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in tr[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمذكر➡", callback_data='title_tr_male')])

    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )
    elif query.data == 'title_aj':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(aj), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in aj[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمذكر➡", callback_data='title_aj_male')])

    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )
    elif query.data == 'title_fn':
    
        message = "🎓 اختر لقبك المناسب من القائمة أدناه. سيتم خصم النقاط المطلوبة من حسابك."
        buttons = []

    # تقسيم الألقاب إلى أزرار (3 أزرار في كل سطر)
        for i in range(0, len(fn), 3):
            row = [
                InlineKeyboardButton(
                    title["name"], callback_data=f"title_{title['name']}_{title['points_required']}"
                )
                for title in fn[i:i+3]
            ]
            buttons.append(row)

    # زر منفرد لعرض معلومات التخصصات
        buttons.append([InlineKeyboardButton("للمذكر➡", callback_data='title_fn_male')])


    # إعداد لوحة الأزرار
        title_markup = InlineKeyboardMarkup(buttons)
    # إضافة زر "رجوع"
        buttons.append([InlineKeyboardButton("رجوع", callback_data='choose_title')])

    # إنشاء واجهة الأزرار
        markup = InlineKeyboardMarkup(buttons)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=message,
            reply_markup=markup
        )

    elif query.data.startswith('choose_title_'):
        user_id = update.effective_user.id
        chosen_title = query.data.split('_')[2]  # اللقب المختار
        title_cost = rc[chosen_title]  # تكلفة اللقب من القاموس TITLES
    
    # تحقق من النقاط الحالية
        user_points = get_points_and_title(user_id)
        if user_points < title_cost:
            await query.edit_message_text("❌ ليس لديك نقاط كافية لشراء هذا اللقب!")
        else:
        # خصم النقاط وتحديث اللقب
            add_points(user_id, -title_cost)
            update_user_title(user_id, chosen_title)
            await query.edit_message_text(f"✅ تم شراء لقبك الجديد: {chosen_title}")


    elif query.data == 'titles_info':
        titles_info = """
📘 *معلومات التخصصات:*
🩺 الدكتور: 40 نقطة
🩺 الجراح: 39 نقطة
💊 صيدلاني: 36 نقطة
🦷 أسنان: 35 نقطة
🏗️ المهندس: 34 نقطة
💉 المخدر: 33 نقطة
📡 الاشعائي: 32 نقطة
🧪 المحلل: 31 نقطة
🐾 البيطري: 30 نقطة
🛫 طيار: 30 نقطة
🕵️‍♂️ الجنائي: 29 نقطة
💉 الممرض: 28 نقطة
⚖️ المحامي: 22 نقطة
👨‍🏫 المدرس: 21 نقطة
📊 المحاسب: 20 نقطة
🌐 المترجم: 19 نقطة
👨‍🏫 معلم: 19 نقطة
👮‍♂️ ضابط: 15 نقطة
💉 إبرة كانونه: 4 نقطة
🧹 الفراش: 3 نقطة
🔧 العامل: 2 نقطة
🎤 السختجي: 1 نقطة
🎤 بطران: 1 نقطة
"""
        await query.edit_message_text(text=titles_info, parse_mode='Markdown')

    elif query.data == "specialization_info":
        specialization_info = """
🏗️ أقسام الهندسة (206-220 نقطة):
م.معماري: 220 نقطة
م.مدني: 219 نقطة
م.ميكانيكي: 218 نقطة
م.كهربائي: 217 نقطة
م.صناعي: 216 نقطة
م.كيميائي: 215 نقطة
م.حاسوب: 214 نقطة
م.نووي: 213 نقطة
م.زراعي: 212 نقطة
م.طيران: 211 نقطة
م.بحري: 210 نقطة
م.ذكاء اصطناعي: 209 نقطة
م.مالية: 208 نقطة
م.بيئي: 207 نقطة
م.طاقة متجددة: 206 نقطة
\n🏥 الأقسام الطبية (147-165 نقطة):
ط.عام: 165 نقطة
ط.باطنية: 164 نقطة
ط.نسائية: 163 نقطة
ط.اطفال: 162 نقطة
ط.اسنان: 161 نقطة
ط.عيون: 160 نقطة
ط.أنف وأذن وحنجرة: 159 نقطة
ط.قلبية: 158 نقطة
ط.جراح: 157 نقطة
ط.تخدير: 156 نقطة
ممرض: 155 نقطة
صيدلاني: 154 نقطة
تحليلات: 153 نقطة
ط.تجميل: 152 نقطة
ط.تغذية: 151 نقطة
ط.نفسي: 150 نقطة
ط.عظام ومفاصل: 149 نقطة
ط.بيئي: 148 نقطة
ط.مختبرات: 147 نقطة
\n🎓 أقسام التربية والتعليم (114-130 نقطة):
وزير التربية: 130 نقطة
أ.لغة انجليزية: 129 نقطة
أ.لغة عربية: 128 نقطة
أ.فيزياء: 127 نقطة
أ.كيمياء: 126 نقطة
أ.فنية: 125 نقطة
أ.رياضة: 124 نقطة
أ.اسلامية: 123 نقطة
أ.احياء: 122 نقطة
أ.رياضيات: 121 نقطة
أ.علوم: 120 نقطة
أ.قراءة: 119 نقطة
مدير مدرسة: 118 نقطة
مشرف: 117 نقطة
ابو الحانوت: 116 نقطة
حارس: 115 نقطة
ابو الخط: 114 نقطة
\n🎨 أقسام الفن والإعلام (131-140 نقطة):
رسام: 140 نقطة
مصور: 139 نقطة
نحات: 138 نقطة
إعلامي: 137 نقطة
مُمنتج: 136 نقطة
مخرج سينمائي: 135 نقطة
مصمم ديكور: 134 نقطة
مصمم ازياء: 133 نقطة
ممثل: 132 نقطة
كاتب: 131 نقطة
\n🛡️ أقسام الأمن والقضاء (130-150 نقطة):
وزير: 150 نقطة
محافظ: 149 نقطة
رئيس وزراء: 148 نقطة
رئيس جمهورية: 147 نقطة
نائب: 146 نقطة
قاضي: 145 نقطة
محامي: 144 نقطة
محقق جنائي: 143 نقطة
محلل جنائي: 142 نقطة
آمن سيبراني: 141 نقطة
آمن وطني: 140 نقطة
مكافحة الإرهاب: 139 نقطة
مكافحة المخدرات: 138 نقطة
كابتن بحرية: 137 نقطة
كابتن طيار: 136 نقطة
مضيف طيران: 135 نقطة
عامل نظافة: 134 نقطة
موظف حكومي: 133 نقطة
سائق taxi: 132 نقطة
سائق شاحنة: 131 نقطة
سياسي: 130 نقطة
"""
    # إضافة زر "رجوع"
        buttons = [[InlineKeyboardButton("رجوع", callback_data='choose_title')]]
        markup = InlineKeyboardMarkup(buttons)

    # تعديل الرسالة لعرض المعلومات مع زر الرجوع
        await query.edit_message_text(
            text=specialization_info,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    elif query.data.startswith("title_"):
        data_parts = query.data.split("_")
    
        if len(data_parts) != 3:
            await query.edit_message_text("❌ خطأ في البيانات.")
            return

        _, title_name, points_required = data_parts
        points_required = int(points_required)
        user_id = update.effective_user.id

      # التحقق من النقاط الحالية للمستخدم
        user_points, user_title = get_points_and_title(user_id)
        if user_points >= points_required:
        # حفظ المعلومات مؤقتًا في user_data
            context.user_data[user_id] = {
                "title_name": title_name,
                "points_required": points_required
            }

        # عرض أزرار تحديد الجنس
            gender_buttons = [
                [InlineKeyboardButton("شراء", callback_data=f"confirm_title_{user_id}_ذكر")],
                [InlineKeyboardButton("رجوع", callback_data='choose_title')]
            ]
            gender_markup = InlineKeyboardMarkup(gender_buttons)

            await query.edit_message_text(
                f"؟🔰 هل انت متأكد'{title_name}':",
                reply_markup=gender_markup
            )
        else:
            await query.edit_message_text(f"⚠️ ليس لديك نقاط كافية للحصول على لقب '{title_name}'. النقاط المطلوبة: {points_required}.")

    elif query.data.startswith("confirm_title_"):
        _, _, user_id, gender = query.data.split("_")
        user_id = int(user_id)
        total_points, user_title = get_points_and_title(user_id)

    # استرجاع المعلومات المؤقتة
        if user_id not in context.user_data:
            await query.edit_message_text("❌ حدث خطأ. حاول مرة أخرى.")
            return

        title_data = context.user_data[user_id]
        title_name = title_data["title_name"]
        points_required = title_data["points_required"]

    # تعديل اللقب إذا كان المستخدم أنثى
        if gender == "أنثى":
            title_name += "ة"  # إضافة "ة" إذا كان اللقب لأنثى

    # خصم النقاط وتعيين اللقب
        cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (points_required, user_id))
        cursor.execute("UPDATE users SET title = ? WHERE user_id = ?", (title_name, user_id))
        connection.commit()

    # حذف البيانات المؤقتة
        del context.user_data[user_id]

        await query.edit_message_text(f"✅ تم شراء اللقب '{title_name}' بنجاح! نقاطك المتبقية: {(total_points)}.")


    elif query.data == 'my_hours':
        user_id = update.effective_user.id
        check_user(user_id)
    
        today = get_baghdad_time().date()
        now = get_baghdad_time()
        weekly_points = get_weekly_points(user_id)

        year_points = get_yearly_points(user_id)
        yearly_rank = get_user_rank(user_id, 'yearly')

        
    # جلب أفضل المستخدمين للساعات الشهرية
        cursor.execute("""
            SELECT user_id, SUM(points) AS hours
            FROM user_daily_points
            WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
            GROUP BY user_id
            ORDER BY hours DESC
            LIMIT 60
        """)
        top_users = cursor.fetchall()

        
    # جلب أفضل المستخدمين للساعات اليومية
        cursor.execute("""
            SELECT user_id, points AS hours
            FROM user_daily_points
            WHERE date = ?
            ORDER BY hours DESC
            LIMIT 60
        """, (today,))
        top_users = cursor.fetchall()
        
        
    # حساب إحصائيات المستخدم الحالي
        today_hours, _ = get_user_study_hours(user_id)
        user_rank = 1 + sum(1 for uid, _ in top_users if uid != user_id and today_hours < _)

        # حساب إحصائيات المستخدم الحالي
        _, week_hours = get_user_study_hours(user_id)
        weekH_rank = 1 + sum(1 for uid, _ in top_users if uid != user_id and week_hours < _)
        
        cursor.execute("""
            SELECT SUM(points) AS hours
            FROM user_daily_points
            WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        """, (user_id,))
        month_hours = cursor.fetchone()[0] or 0.0
        monthH_rank = 1 + sum(1 for uid, _ in top_users if uid != user_id and month_hours < _)


        cursor.execute("""
            SELECT SUM(points) AS hours
            FROM user_daily_points
            WHERE user_id = ? AND strftime('%Y', date) = strftime('%Y', 'now')
        """, (user_id,))
        year_points = cursor.fetchone()[0] or 0.0

        # Get user's yeaarly points
        now = get_baghdad_time()
        cursor.execute("""
            SELECT points 
            FROM user_yearly_points 
            WHERE user_id = ? AND year = ?
        """, (user_id, now.year))
        user_yearly_points = cursor.fetchone()
        user_yearly_points = user_yearly_points[0] if user_yearly_points else 0


    # رسالة الإحصائيات
        message = (

        "⏰ *ساعات الدراسة:*\n"
        f"• اليوم: {today_hours:.2f} ساعة\n"
        f"• الأسبوع: {weekly_points} ساعة\n"
        f"• الشهر: {month_hours:.2f} ساعة\n"
        f"• السنة : {year_points} ساعة\n\n"

        f"🏆 *الترتيب:*\n"
        f"• اليومي: المركز {user_rank}\n"
        f"• الأسبوعي: المركز {weekH_rank}\n"
        f"• الشهري: المركز {monthH_rank}\n"
        f"• السنوي: المركز {yearly_rank}\n"
        )
    
        buttons = [[InlineKeyboardButton("رجوع", callback_data='back_to_main')]]
        markup = InlineKeyboardMarkup(buttons)
    
        await query.edit_message_text(
            text=message,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    elif query.data == 'my_points':
        user_id = update.effective_user.id
        check_user(user_id)
    
    # استرجاع الساعات المستثناة من الإحالة
        total_points, user_title = get_points_and_title(user_id)
        weekly_points = get_weekly_points(user_id)
        user_monthly_points = get_monthly_points(user_id)
        user_yearly_points = get_yearly_points(user_id)
        daily_points = get_daily_points()  # Today's points
        monthly_points = get_monthly_points(user_id)
        year_points = get_yearly_points(user_id)
    # ترتيب المستخدم
        daily_rank = get_user_rank(user_id, 'daily')
        monthly_rank = get_user_rank(user_id, 'monthly')
        yearly_rank = get_user_rank(user_id, 'yearly')
    # Get points and title
        total_points, user_title = get_points_and_title(user_id)

        today = get_baghdad_time().date()
        now = get_baghdad_time()
        week_number = now.isocalendar()[1]

        # Get user's yeaarly points
        now = get_baghdad_time()
        cursor.execute("""
            SELECT points
            FROM user_yearly_points
            WHERE user_id = ? AND year = ?
        """, (user_id, now.year))
        user_yearly_points = cursor.fetchone()
        user_yearly_points = user_yearly_points[0] if user_yearly_points else 0





    # Get today's points for the current user
        today = get_baghdad_time().date()
        cursor.execute("""
            SELECT points 
            FROM user_daily_points 
            WHERE user_id = ? AND date = ?
        """, (user_id, today))
        user_daily_points = cursor.fetchone()
        user_daily_points = user_daily_points[0] if user_daily_points else 0




        # Get user's monthly points
        now = get_baghdad_time()
        cursor.execute("""
            SELECT points 
            FROM user_monthly_points 
            WHERE user_id = ? AND month = ? AND year = ?
        """, (user_id, now.month, now.year))
        user_monthly_points = cursor.fetchone()
        user_monthly_points = user_monthly_points[0] if user_monthly_points else 0

    # رسالة الإحصائيات
        message = (
        f"📊 *إحصائياتك:*\n\n"
        "💫 *النقاط:*\n"
        f"• اليوم: {user_daily_points} نقطة\n"
        f"• الأسبوع: {weekly_points} نقطة\n"
        f"• الشهر: {user_monthly_points} نقطة\n"
        f"• السنة: {year_points} نقطة\n"

        f"💎 *النقاط الإجمالية:*\n"
        f"• {total_points} نقطة (تتضمن النقاط من الإحالة)\n\n"

        f"🏆 *الترتيب:*\n"
        f"• اليومي: المركز {daily_rank}\n"
        f"• الشهري: المركز {monthly_rank}\n"
        f"• السنوي: المركز {yearly_rank}\n"
        )
    
        buttons = [[InlineKeyboardButton("رجوع", callback_data='back_to_main')]]
        markup = InlineKeyboardMarkup(buttons)
    
        await query.edit_message_text(
            text=message,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    elif query.data == 'back_to_main':
        user_name = update.effective_user.first_name
        user_id = update.effective_user.id
        check_user(user_id, user_name)     # <--  أحذف هذا السطر هنا عند اكتمال الاسماء الحقيقية للسلاسة
        points, title = get_points_and_title(user_id)
        current_username = update.effective_user.username
        is_admin = current_username and current_username.replace('@', '') in [username.replace('@', '') for username in ADMIN_USERNAMES]

    # ✅ رسالة الترحيب وإعداد الأزرار
        message = f"""
    ⭐️| مرحبًا {user_name} {title}،
    شلونك اليوم؟ أتمنى لك يومًا مليئًا بالسعادة! \n\n{get_combined_quotes()}
        """
        buttons = [
        [InlineKeyboardButton("تسجيل للجلسة", url="https://t.me/Challen96bot?start=ref_0")],
        [InlineKeyboardButton("شرح البوت", callback_data='help')],
        [InlineKeyboardButton("ساعاتي", callback_data='my_hours')],
        [InlineKeyboardButton("نقاطي", callback_data='my_points')],
        [InlineKeyboardButton("توب", callback_data='top')],
        [InlineKeyboardButton("المشاركة", callback_data='share')],
        [InlineKeyboardButton("اختر تخصصك", callback_data='choose_title')]
        ]

        if is_admin:
            buttons.append([
            InlineKeyboardButton("اضافه نقاط", callback_data='add_points'),
            InlineKeyboardButton("تقليل نقاط", callback_data='reduce_points'),
            InlineKeyboardButton("نشر الجلسات", callback_data='add_channel')
        ])
    
        inline_markup = InlineKeyboardMarkup(buttons)

    # ✅ تعديل الرسالة بدلاً من إرسال رسالة جديدة
        await query.message.edit_text(text=message.strip(), reply_markup=inline_markup)


    elif query.data == 'top':
        buttons = [
            [InlineKeyboardButton("توب النقاط", callback_data='top_points')],
            [InlineKeyboardButton("توب الساعات", callback_data='top_hours')],
            [InlineKeyboardButton("توب المشاركة", callback_data='top_participation')]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="اختر ما تريده:", reply_markup=markup
        )

    
    elif query.data == 'top_points':
        buttons = [
            [InlineKeyboardButton("يومي", callback_data='top_daily')],
            [InlineKeyboardButton("شهري", callback_data='top_monthly')],
            [InlineKeyboardButton("سنوي", callback_data='top_yearly')]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="اختر ما تريده:", reply_markup=markup
        )

    elif query.data == 'top_monthly':
        user_id = update.effective_user.id
        top_users = get_monthly_points()  # جلب المستخدمين الشهريين والنقاط
        user_rank = get_user_rank(user_id, 'monthly')
        points, user_title = get_points_and_title(user_id)  # جلب النقاط واللقب للمستخدم

        # Get user's monthly points
        now = get_baghdad_time()
        cursor.execute("""
            SELECT points 
            FROM user_monthly_points 
            WHERE user_id = ? AND month = ? AND year = ?
        """, (user_id, now.month, now.year))
        user_monthly_points = cursor.fetchone()
        user_monthly_points = user_monthly_points[0] if user_monthly_points else 0

        message = "🏆 **توب النقاط للشهر - أفضل 60 مستخدم**:\n\n"
        for rank, (uid, points) in enumerate(top_users, 1):
            # جلب اللقب لكل مستخدم
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"

            user_name = username

            if title:
                message += f"{rank}. {user_name} ({title}) - {points} نقطة\n"
            else:
                message += f"{rank}. {user_name} - {points} نقطة\n"

        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {user_rank}\n"
        message += f"📊 نقاطك هذا الشهر: {user_monthly_points} نقطة\n"
        message += f"🏷️ لقبك: {user_title}"

        buttons = [
            [InlineKeyboardButton("يومي", callback_data='top_daily')],
            [InlineKeyboardButton("شهري", callback_data='top_monthly')],
            [InlineKeyboardButton("سنوي", callback_data='top_yearly')]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup, parse_mode='Markdown')

    elif query.data == 'top_yearly':
        user_id = update.effective_user.id
        top_users = get_yearly_points_top()  # Using the new function
        user_rank = get_user_rank(user_id, 'yearly')
        points, user_title = get_points_and_title(user_id)

    # Get user's yearly points
        now = get_baghdad_time()
        cursor.execute("""
            SELECT points 
            FROM user_yearly_points 
            WHERE user_id = ? AND year = ?
        """, (user_id, now.year))
        user_yearly_points = cursor.fetchone()
        user_yearly_points = user_yearly_points[0] if user_yearly_points else 0
        total_points, user_title = get_points_and_title(user_id)
        message = "🏆 **توب النقاط للسنة - أفضل 60 مستخدم**:\n\n"
        for rank, (uid, points) in enumerate(top_users, 1):
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
            

            
            user_name = username

            if title:
                message += f"{rank}. {user_name} ({title}) - {points} نقطة\n"
            else:
                message += f"{rank}. {user_name} - {points} نقطة\n"

        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {user_rank}\n"
        message += f"📊 نقاطك هذه السنة: {total_points} نقطة\n"
        message += f"🏷️ لقبك: {user_title}"

        buttons = [
        [InlineKeyboardButton("يومي", callback_data='top_daily')],
        [InlineKeyboardButton("شهري", callback_data='top_monthly')],
        [InlineKeyboardButton("سنوي", callback_data='top_yearly')]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup, parse_mode='Markdown')
    elif query.data == 'top_daily':
        user_id = update.effective_user.id
        top_users = get_daily_points()  # Using the new function
        user_rank = get_user_rank(user_id, 'daily')
    
    # Get today's points for the current user
        today = get_baghdad_time().date()
        cursor.execute("""
            SELECT points 
            FROM user_daily_points 
            WHERE user_id = ? AND date = ?
        """, (user_id, today))
        user_daily_points = cursor.fetchone()
        user_daily_points = user_daily_points[0] if user_daily_points else 0

        message = "🏆 **توب النقاط لليوم - أفضل المستخدمين**:\n\n"
        for rank, (uid, points) in enumerate(top_users, 1):
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            user_title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
        
            user_name = username
        
            if user_title:
                message += f"{rank}. {user_name} ({user_title}) - {points} نقطة\n"
            else:
                message += f"{rank}. {user_name} - {points} نقطة\n"

        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {user_rank}\n"
        message += f"📊 نقاطك اليوم: {user_daily_points}"

        buttons = [
        [InlineKeyboardButton("يومي", callback_data='top_daily')],
        [InlineKeyboardButton("شهري", callback_data='top_monthly')],
        [InlineKeyboardButton("سنوي", callback_data='top_yearly')]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup, parse_mode='Markdown')



    elif query.data == 'top_hours':
        buttons = [
        [InlineKeyboardButton("يومي", callback_data='top_hours_daily')],
        [InlineKeyboardButton("اسبوعي", callback_data='top_hours_weekly')],
        [InlineKeyboardButton("شهري", callback_data='top_hours_monthly')],
        [InlineKeyboardButton("سنوي", callback_data='top_hours_yearly')],
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text("اختر الفئة الزمنية:", reply_markup=markup)
        
    elif query.data == 'top_hours_daily':
        user_id = update.effective_user.id
        today = get_baghdad_time().date()

    # جلب أفضل المستخدمين للساعات اليومية
        cursor.execute("""
            SELECT user_id, points AS hours
            FROM user_daily_points
            WHERE date = ?
            ORDER BY hours DESC
            LIMIT 60
        """, (today,))
        top_users = cursor.fetchall()

    # حساب إحصائيات المستخدم الحالي
        today_hours, _ = get_user_study_hours(user_id)
        user_rank = 1 + sum(1 for uid, _ in top_users if uid != user_id and today_hours < _)

        message = "🏆 **توب الساعات اليومية - أفضل المستخدمين:**\n\n"
        for rank, (uid, hours) in enumerate(top_users, 1):
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
    
            user_name = username

            hours_text = points_to_hours_text(hours)
            if title:
                message += f"{rank}. {user_name} ({title}) - {hours_text}\n"
            else:
                message += f"{rank}. {user_name} - {hours_text}\n"

        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {user_rank}\n"
        message += f"📊 عدد ساعاتك اليوم: {points_to_hours_text(today_hours)}\n"

        buttons = [
        [InlineKeyboardButton("يومي", callback_data='top_hours_daily')],
        [InlineKeyboardButton("اسبوعي", callback_data='top_hours_weekly')],
        [InlineKeyboardButton("شهري", callback_data='top_hours_monthly')],
        [InlineKeyboardButton("سنوي", callback_data='top_hours_yearly')],
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup)
    elif query.data == 'top_hours_weekly':
        user_id = update.effective_user.id
        today = get_baghdad_time().date()
        now = get_baghdad_time()
        week_number = now.isocalendar()[1]

        # جلب أفضل المستخدمين للساعات الأسبوعية
        cursor.execute("""
            SELECT user_id, SUM(points) AS hours
            FROM user_daily_points
            WHERE date >= ?
            GROUP BY user_id
            ORDER BY hours DESC
            LIMIT 60
        """, (week_number,))
        top_users = cursor.fetchall()

        # الحصول على نقاط المستخدم الأسبوعية
        week_hours = get_weekly_points(user_id)
        weekH_rank = 1 + sum(1 for uid, pts in top_users if uid != user_id and week_hours < pts)

        message = "🏆 **توب الأسبوع - أفضل 60 طالب دراسة:**\n\n"
        for rank, (uid, pts) in enumerate(top_users, 1):
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
            
            user_name = username
            
            # تحويل النقاط إلى نص الساعات
            hours_text = points_to_hours_text(pts)
            
            if title:
                message += f"{rank}. {user_name} ({title}) - {hours_text}\n"
            else:
                message += f"{rank}. {user_name} - {hours_text}\n"

        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {weekH_rank}\n"
        message += f"📊 ساعات دراستك الأسبوعية: {points_to_hours_text(week_hours)}\n"

        buttons = [
            [InlineKeyboardButton("يومي", callback_data='top_hours_daily')],
            [InlineKeyboardButton("اسبوعي", callback_data='top_hours_weekly')],
            [InlineKeyboardButton("شهري", callback_data='top_hours_monthly')],
            [InlineKeyboardButton("سنوي", callback_data='top_hours_yearly')],
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup)



    elif query.data == 'top_hours_monthly':
        user_id = update.effective_user.id
        today = get_baghdad_time().date()

    # جلب أفضل المستخدمين للساعات الشهرية
        cursor.execute("""
            SELECT user_id, SUM(points) AS hours
            FROM user_daily_points
            WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
            GROUP BY user_id
            ORDER BY hours DESC
            LIMIT 60
        """)
        top_users = cursor.fetchall()

    # حساب إحصائيات المستخدم الحالي
        cursor.execute("""
            SELECT SUM(points) AS hours
            FROM user_daily_points
            WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        """, (user_id,))
        month_hours = cursor.fetchone()[0] or 0.0
        monthH_rank = 1 + sum(1 for uid, _ in top_users if uid != user_id and month_hours < _)

        message = "🏆 **توب الساعات الشهرية - أفضل المستخدمين:**\n\n"
        for rank, (uid, hours) in enumerate(top_users, 1):
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
        
            user_name = username

            hours_text = points_to_hours_text(hours)
            if title:
                message += f"{rank}. {user_name} ({title}) - {hours_text}\n"
            else:
                message += f"{rank}. {user_name} - {hours_text}\n"


        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {monthH_rank}\n"
        message += f"📊 عدد ساعاتك الشهرية: {points_to_hours_text(month_hours)}\n"

        buttons = [
        [InlineKeyboardButton("يومي", callback_data='top_hours_daily')],
        [InlineKeyboardButton("اسبوعي", callback_data='top_hours_weekly')],
        [InlineKeyboardButton("شهري", callback_data='top_hours_monthly')],
        [InlineKeyboardButton("سنوي", callback_data='top_hours_yearly')],
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup)


    elif query.data == 'top_hours_yearly':
        user_id = update.effective_user.id
        top_users = get_yearly_points_top()
        user_rank = get_user_rank(user_id, 'yearly')
        today = get_baghdad_time().date()
        points, user_title = get_points_and_title(user_id)

        total_points, user_title = get_points_and_title(user_id)
    # حساب إحصائيات المستخدم الحالي
        cursor.execute("""
            SELECT SUM(points) AS hours
            FROM user_daily_points
            WHERE user_id = ? AND strftime('%Y', date) = strftime('%Y', 'now')
        """, (user_id,))
        total_points = cursor.fetchone()[0] or 0.0

        message = "🏆 **توب الساعات السنوية - أفضل المستخدمين:**\n\n"
        for rank, (uid, hours) in enumerate(top_users, 1):
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
        
            user_name = username

            hours_text = points_to_hours_text(hours)
            if title:
                message += f"{rank}. {user_name} ({title}) - {hours_text}\n"
            else:
                message += f"{rank}. {user_name} - {hours_text}\n"


        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {user_rank}\n"
        message += f"📊 عدد ساعاتك السنوية: {points_to_hours_text(total_points)}\n"

        buttons = [
        [InlineKeyboardButton("يومي", callback_data='top_hours_daily')],
        [InlineKeyboardButton("اسبوعي", callback_data='top_hours_weekly')],
        [InlineKeyboardButton("شهري", callback_data='top_hours_monthly')],
        [InlineKeyboardButton("سنوي", callback_data='top_hours_yearly')],
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup)
        
    elif query.data == 'top_participation':
        user_id = update.effective_user.id

        # 🔹 جلب المستخدمين الذين لديهم مشاركات فقط (إهمال الذين لديهم 0 مشاركة)
        cursor.execute("""
            SELECT user_id, COUNT(*) as referral_count
            FROM users
            WHERE referrer_id IS NOT NULL
            GROUP BY user_id
            HAVING referral_count > 0
            ORDER BY referral_count DESC
            LIMIT 30
        """)
        top_participants = cursor.fetchall()

        # 🔹 حساب عدد المشاركات للمستخدم الحالي
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        user_referrals = cursor.fetchone()[0]

        # 🔹 حساب ترتيب المستخدم الحالي في القائمة
        cursor.execute("""
            SELECT COUNT(*) + 1
            FROM (
                SELECT user_id, COUNT(*) as ref_count
                FROM users 
                WHERE referrer_id IS NOT NULL
                GROUP BY user_id
                HAVING ref_count > ?
            )
        """, (user_referrals,))
        user_participation_rank = cursor.fetchone()[0]

        # 🔹 بناء رسالة التوب
        message = "🏆 **توب المشاركة - أفضل المستخدمين**:\n\n" if top_participants else "🚫 لا يوجد مشاركون حتى الآن.\n"

        for rank, (uid, referral_count) in enumerate(top_participants, 1):
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"

            user_name = username

            message += f"{rank}. {user_name} {'('+title+')' if title else ''} - {referral_count} مشاركة\n"

        message += f"\n\n**إحصائياتك:**\n"
        message += f"🎯 ترتيبك: {user_participation_rank}\n"
        message += f"📊 عدد مشاركاتك: {user_referrals}\n"

        buttons = [
            [InlineKeyboardButton("توب النقاط", callback_data='top_points')],
            [InlineKeyboardButton("توب الساعات", callback_data='top_hours')],
            [InlineKeyboardButton("توب المشاركة", callback_data='top_participation')]
        ]
        markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(message, reply_markup=markup, parse_mode='Markdown')

    elif query.data == 'help':
        buttons = [
            [InlineKeyboardButton("جدول الجلسات", callback_data='forward_message')]
        ]
        inline_markup = InlineKeyboardMarkup(buttons)
        await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=" اختر ما تريد من الخيارات التالية:", reply_markup=inline_markup
        )

    elif query.data == 'forward_message':
        try:
            # تحديد معرف القناة ومعرف الرسالة المراد نسخها
            channel_id = "@STUDYWITHELAHMED"  # ضع معرف القناة هنا
            message_id = 446  # ضع معرف الرسالة هنا

            # نسخ الرسالة من القناة وإرسالها إلى المستخدم
            await context.bot.forward_message(
                chat_id=query.message.chat_id,  # إرسال الرسالة إلى نفس المحادثة
                from_chat_id=channel_id,        # معرف القناة
                message_id=message_id          # معرف الرسالة
            )
        except Exception as e:
            print(f"❌ خطأ أثناء نسخ الرسالة: {e}")
            await query.edit_message_text("❌ حدث خطأ أثناء جلب الرسالة.")
    
    elif query.data == "register_challenge":
        # إرسال أمر start للبوت
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="/start"
        )
        await query.answer("تم التوجيه إلى البوت!")
    elif query.data == 'add_points':
        context.user_data['operation'] = 'add'
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text ="💳 أدخل يوزر المستخدم الذي تريد إضافة نقاط له:"
        )
        return ADD_POINTS_STEP

    elif query.data == 'reduce_points':
        context.user_data['operation'] = 'reduce'
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text ="🔻 أدخل يوزر المستخدم الذي تريد تقليل نقاطه:"
        )
        return REDUCE_POINTS_STEP

    elif query.data == 'manage_personal_sessions':
        await query.answer()  # لإخفاء علامة التحميل من الزر
        user_id = update.effective_user.id
        sessions = get_user_personal_sessions(user_id)
        
        if not sessions:
            keyboard = [[InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")]]
            markup = InlineKeyboardMarkup(keyboard)
            text = (
                "📚 إدارة الجلسات الشخصية\n\n"
                "🔹 لا توجد جلسات لك حتى الآن\n\n"
                "💡 استخدم /جلساتي أو /mysessions للوصول لهذه القائمة"
            )
        else:
            text = "📚 جلساتك الشخصية:\n\n"
            for session_number, start_hour, start_minute, duration in sessions:
                end_hour = (start_hour + (start_minute + duration) // 60) % 24
                end_minute = (start_minute + duration) % 60
                start_time_12 = format_12_hour(start_hour, start_minute)
                end_time_12 = format_12_hour(end_hour, end_minute)
                text += f"🔸 الجلسة {session_number}: {start_time_12} إلى {end_time_12} ({duration} دقيقة)\n"
            
            remaining_hours, remaining_mins = calculate_remaining_time(sessions)
            text += f"\n⏰ باقي {remaining_hours} ساعة و {remaining_mins} دقيقة من اليوم"
            text += "\n💡 الأوقات الأخرى مخصصة للاستراحة\n"
            text += "\n📝 اكتب رقم الجلسة لتعديلها أو حذفها"
            ref_code = get_or_create_user_ref_code(user_id)
            text += f"\n\n🔗 رابط التسجيل في جلساتك:\nhttps://t.me/challen96bot?start={ref_code}"
            keyboard = [[InlineKeyboardButton("➕ إضافة جلسة جديدة", callback_data="add_session")]]
            markup = InlineKeyboardMarkup(keyboard)
    
        # إرسال رسالة جديدة بدل تعديل الرسالة الحالية
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=markup,
            disable_web_page_preview=True #بدون معاين عند الارسال ينطبق للكل ب await
        )

#اذا تريد تكون بشكل تعديل edit_message_text

    elif data == "add_session":
        # عرض أزرار اختيار الوقت
        keyboard = []
        
        # ترتيب الأوقات بدءاً من 12ص
        sorted_times = []
        # من 12ص إلى 11:30ص
        for hour in range(12):
            for minute in [0, 30]:
                sorted_times.append((hour, minute))
        # من 12م إلى 11:30م
        for hour in range(12, 24):
            for minute in [0, 30]:
                if not (hour == 23 and minute == 30):
                    sorted_times.append((hour, minute))
        
        for hour, minute in sorted_times:
            time_12 = format_12_hour(hour, minute)
            keyboard.append([InlineKeyboardButton(
                time_12, 
                callback_data=f"select_time_{hour}_{minute}"
            )])
        
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🕐 اختر وقت بداية الجلسة:",
            reply_markup=markup
        )
        
    elif data.startswith("select_time_"):
        # تم اختيار الوقت
        parts = data.split("_")
        hour = int(parts[2])
        minute = int(parts[3])
        
        # حفظ الوقت المختار
        update_user_state(user_id, "waiting_duration", f"{hour}_{minute}")
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_sessions")]]
        markup = InlineKeyboardMarkup(keyboard)
        
        selected_time_12 = format_12_hour(hour, minute)
        await query.edit_message_text(
            f"✅ تم اختيار الوقت: {selected_time_12}\n\n"
            f"📝 اكتب مدة الجلسة بالدقائق (مثال: 50)",
            reply_markup=markup
        )
        
    elif data == "back_to_sessions":
        # العودة لإدارة الجلسات
        update_user_state(user_id, None)
        await manage_personal_sessions(query, context)
        
    elif data.startswith("edit_session_"):
        session_number = int(data.split("_")[2])
        update_user_state(user_id, "editing", editing_session=session_number)
        
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل هذه الجلسة", callback_data=f"modify_session_{session_number}")],
            [InlineKeyboardButton("🗑️ حذف هذه الجلسة", callback_data=f"delete_session_{session_number}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_sessions")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🔧 ماذا تريد أن تفعل بالجلسة {session_number}؟",
            reply_markup=markup
        )

    elif data.startswith("delete_session_"):
        session_number = int(data.split("_")[2])
        delete_personal_session(user_id, session_number, context)  # مرر context هنا
    
        # إرسال رسالة تأكيد الحذف مؤقتة
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ تم حذف الجلسة بنجاح!",
            reply_to_message_id=query.message.message_id
        )
        await asyncio.sleep(2)
        try:
            await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
        except Exception:
            pass
    
        # إعادة عرض قائمة الجلسات الشخصية بعد الحذف
        await manage_personal_sessions(update, context)
    elif data.startswith("modify_session_"):
        session_number = int(data.split("_")[2])
        # حفظ حالة التعديل
        update_user_state(user_id, "editing", editing_session=session_number)
        # يمكنك هنا إرسال رسالة تطلب من المستخدم إدخال مدة جديدة أو وقت جديد
        await query.edit_message_text(
            f"✏️ اكتب مدة الجلسة الجديدة (بالدقائق) للجلسة {session_number}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_sessions")]
            ])
        )

    elif data == "back_to_sessions":
        update_user_state(user_id, None)
        await manage_personal_sessions(update, context)

    elif data == "start_all_sessions":
        # تشغيل جميع الجلسات
        cursor.execute("""
            UPDATE channel_sessions_status 
            SET is_active = 1 
            WHERE user_id = ?
        """, (user_id,))
        connection.commit()
        
        await query.answer("✅ تم تشغيل جميع الجلسات!")
        await sessions_control_panel(update, context)
        
    elif data == "stop_all_sessions":
        # إيقاف جميع الجلسات
        cursor.execute("""
            UPDATE channel_sessions_status 
            SET is_active = 0 
            WHERE user_id = ?
        """, (user_id,))
        connection.commit()
        
        await query.answer("⏸️ تم إيقاف جميع الجلسات!")
        await sessions_control_panel(update, context)
        
    elif data.startswith("toggle_channel_"):
        # تبديل حالة قناة معينة
        channel_id = data.replace("toggle_channel_", "")
        
        cursor.execute("""
            SELECT is_active FROM channel_sessions_status 
            WHERE channel_id = ? AND user_id = ?
        """, (channel_id, user_id))
        result = cursor.fetchone()
        
        new_status = 0 if (result and result[0]) else 1
        
        cursor.execute("""
            UPDATE channel_sessions_status 
            SET is_active = ? 
            WHERE channel_id = ? AND user_id = ?
        """, (new_status, channel_id, user_id))
        connection.commit()
        
        status_text = "تم التشغيل ✅" if new_status else "تم الإيقاف ⏸️"
        await query.answer(status_text)
        await sessions_control_panel(update, context)

#ادارة قنواة\جلسات المستخدمين

    elif query.data == 'manage_user_channels':
        # جلب جميع القنوات من جدول user_channels
        cursor.execute("SELECT channel_id, username FROM user_channels")
        channels = cursor.fetchall()
        if not channels:
            await query.edit_message_text("لا توجد قنوات مضافة من المستخدمين.")
            return
        keyboard = [
            [InlineKeyboardButton(f"{username}", callback_data=f"user_channel_{channel_id}")]
            for channel_id, username in channels
        ]
        keyboard.append([InlineKeyboardButton("رجوع", callback_data='back_to_main')])
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("اختر قناة لإدارتها:", reply_markup=markup)

    elif query.data.startswith('user_channel_'):
        channel_id = query.data.replace('user_channel_', '')
        cursor.execute("SELECT username FROM user_channels WHERE channel_id = ?", (channel_id,))
        result = cursor.fetchone()
        username = result[0] if result else "غير معروف"
        keyboard = [
            [InlineKeyboardButton("🗑️ حذف القناة", callback_data=f"delete_channel_{channel_id}")],
            [InlineKeyboardButton("🚫 تقييد القناة", callback_data=f"restrict_channel_{channel_id}")],
            [InlineKeyboardButton("رجوع", callback_data='manage_user_channels')]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"قناة: @{username}\nID: {channel_id}",
            reply_markup=markup
        )

    elif query.data.startswith('delete_channel_'):
        channel_id = query.data.replace('delete_channel_', '')
        cursor.execute("DELETE FROM user_channels WHERE channel_id = ?", (channel_id,))
        connection.commit()
        await query.edit_message_text("✅ تم حذف القناة بنجاح.")
        await asyncio.sleep(1)
        await button_callback(update, context)  # إعادة عرض القائمة

    elif query.data.startswith('restrict_channel_'):
        channel_id = query.data.replace('restrict_channel_', '')
        # هنا يمكنك تنفيذ منطق التقييد (مثلاً تحديث عمود في الجدول)
        cursor.execute("UPDATE user_channels SET username = username || ' [مقيد]' WHERE channel_id = ?", (channel_id,))
        connection.commit()
        await query.edit_message_text("🚫 تم تقييد القناة.")
        await asyncio.sleep(1)
        await button_callback(update, context)  # إعادة عرض القائمة

    elif query.data == 'manage_user_sessions':
        # جلب جميع المستخدمين الذين لديهم جلسات شخصية
        cursor.execute("SELECT DISTINCT user_id FROM personal_sessions")
        users = cursor.fetchall()
        if not users:
            await query.edit_message_text("لا يوجد مستخدمون لديهم جلسات شخصية.")
            return
        keyboard = [
            [InlineKeyboardButton(f"مستخدم {user_id}", callback_data=f"user_sessions_{user_id}")]
            for (user_id,) in users
        ]
        keyboard.append([InlineKeyboardButton("رجوع", callback_data='back_to_main')])
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("اختر مستخدم لإدارة جلساته:", reply_markup=markup)

    elif query.data.startswith('user_sessions_'):
        user_id = int(query.data.replace('user_sessions_', ''))
        sessions = get_user_personal_sessions(user_id)
        if not sessions:
            await query.edit_message_text("لا توجد جلسات لهذا المستخدم.")
            return
        text = f"جلسات المستخدم {user_id}:\n"
        for session in sessions:
            
            text += f"- جلسة {session[0]}: {session[1]:02d}:{session[2]:02d} لمدة {session[3]} دقيقة\n"
        keyboard = [
            [InlineKeyboardButton("🗑️ حذف جميع الجلسات", callback_data=f"delete_sessions_{user_id}")],
            [InlineKeyboardButton("🚫 تقييد الجلسات", callback_data=f"restrict_sessions_{user_id}")],
            [InlineKeyboardButton("رجوع", callback_data='manage_user_sessions')]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=markup)

    elif query.data.startswith('delete_sessions_'):
        user_id = int(query.data.replace('delete_sessions_', ''))
        cursor.execute("DELETE FROM personal_sessions WHERE user_id = ?", (user_id,))
        connection.commit()
        await query.edit_message_text("✅ تم حذف جميع الجلسات لهذا المستخدم.")
        await asyncio.sleep(1)
        await button_callback(update, context)

    elif query.data.startswith('restrict_sessions_'):
        user_id = int(query.data.replace('restrict_sessions_', ''))
        # هنا يمكنك تنفيذ منطق التقييد (مثلاً تحديث عمود أو إضافة منطق خاص)
        await query.edit_message_text("🚫 تم تقييد جلسات المستخدم.")
        await asyncio.sleep(1)
        await button_callback(update, context)
    elif query.data == 'toggle_private_sessions':
        user_id = update.effective_user.id
        cursor.execute("""
            SELECT is_active FROM channel_sessions_status
            WHERE channel_id = ? AND user_id = ?
        """, (str(user_id), user_id))
        result = cursor.fetchone()
        current_status = result[0] if result is not None else 1
        new_status = 0 if current_status else 1
        cursor.execute("""
            INSERT OR REPLACE INTO channel_sessions_status
            (channel_id, user_id, is_active, is_personal)
            VALUES (?, ?, ?, 1)
        """, (str(user_id), user_id, new_status))
        connection.commit()
        # إعادة جدولة الجلسات في الخاص
        schedule_channel_messages(context, user_id, user_id)
        status_text = "✅ تم تفعيل الجلسات في الخاص!" if new_status else "⏸️ تم إيقاف الجلسات في الخاص!"
        await query.answer(status_text)
        # إعادة رسم الأزرار مع الحالة الجديدة
        await start(update, context)

    elif data.startswith("join_session_"):
        session_number = int(data.split("_")[2])
        user_id = update.effective_user.id
        # سجل المستخدم في الجلسة (نفس منطق زر تسجيل الجلسة)
        # يمكنك هنا استدعاء register_user_for_session أو أي منطق تريده
        await query.answer("تم تسجيلك بهالجلسة، شد حيلك! 💪")
        await query.edit_message_text("✅ سجلتك بهالجلسة، يلا ننتظرك تبدع! 🚀")
    
    elif data.startswith("decline_session_") or data.startswith("join_session_"):
        session_number = int(data.split("_")[2])
        # حذف رسالة الدعوة من الخاص
        cursor.execute("SELECT message_id FROM session_invites WHERE user_id=? AND session_number=?", (user_id, session_number))
        row = cursor.fetchone()
        if row:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=row[0])
            except Exception:
                pass
            cursor.execute("DELETE FROM session_invites WHERE user_id=? AND session_number=?", (user_id, session_number))
            connection.commit()
        # أرسل رسالة تعذرية أو إشعار للمستخدم
        await context.bot.send_message(chat_id=user_id, text=f"ولا يهمك! إذا تحتاج ترتاح شوي أو عندك شغلة، الجلسات مستمرة طول اليوم.\nرجع متى ما تحب، أهم شي صحتك وراحتك. 🙏🏿🍃")

#اذاعة
    elif query.data == 'broadcast':
        await broadcast_handler(update, context)
    
    elif query.data == 'custom_commands':
        await custom_commands_handler(update, context)
    
    elif query.data == 'add_custom_command':
        await add_custom_command_handler(update, context)
    elif data == 'command_stats':
        await command_stats_handler(update, context)
    elif data == 'toggle_command':
        await toggle_command_handler(update, context)
    elif data == 'delete_command':
        await delete_command_handler(update, context)
    elif data == 'admin_panel':
        await start(update, context)
    # معالجات الأزرار الديناميكية
    elif data.startswith('toggle_') or data.startswith('delete_'):
        await handle_toggle_delete_commands(update, context)
    

    # التحقق من معالج الإذاعة أولاً
    elif await handle_broadcast_message(update, context):
        return
    
    # التحقق من معالج إنشاء الأوامر
    elif await handle_custom_command_creation(update, context):
        return
    
    # معالجات أخرى...
    # باقي المعالجات الموجودة


def get_user_id_from_user_name(user_name):
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (user_name,))
    result = cursor.fetchone()
    user_id = get_points_and_title(user_id)

async def handle_points_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال اسم المستخدم"""
    user_name = update.effective_user.first_name
    user_id = get_user_id_from_user_name(user_name)
    user_name = update.message.text.strip()

    if user_id:
        context.user_data['user_id'] = user_id
        context.user_data['operation'] = 'add' if update.message.text == 'إضافة نقاط' else 'reduce'
        await update.message.reply_text("📊 أدخل عدد النقاط:")
        return ENTER_POINTS
    else:
        await update.message.reply_text("❌ المستخدم غير موجود. تأكد من كتابة اليوزر بشكل صحيح.")
        return ConversationHandler.END
async def add_points_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    query = update.callback_query
    username = update.message.text.strip()
    
    # البحث عن user_id باستخدام اليوزرنيم أو user_id
    try:
        if username.startswith('@'):
            username = username[1:]
        
        # محاولة البحث عن طريق اليوزرنيم
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        
        if not result:
            # محاولة البحث عن طريق user_id إذا كان الإدخال رقمي
            if username.isdigit():
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (int(username),))
                result = cursor.fetchone()
            
        if not result:
            await update.message.reply_text("❌ المستخدم غير موجود. تأكد من كتابة اليوزر أو ID بشكل صحيح.")
            return ConversationHandler.END
            
        context.user_data['target_user_id'] = result[0]
        await update.message.reply_text("📊 أدخل عدد النقاط:")
        return ENTER_POINTS
        
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء البحث عن المستخدم.")
        return ConversationHandler.END

async def reduce_points_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    query = update.callback_query
    username = update.message.text.strip()
    
    try:
        if username.startswith('@'):
            username = username[1:]
            
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        
        if not result and username.isdigit():
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (int(username),))
            result = cursor.fetchone()
        
        if not result:
            await update.message.reply_text("❌ المستخدم غير موجود. تأكد من كتابة اليوزر أو ID بشكل صحيح.")
            return ConversationHandler.END
            
        context.user_data['target_user_id'] = result[0]
        await update.message.reply_text("📉 أدخل عدد النقاط المطلوب تقليلها:")
        return ENTER_POINTS
        
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء البحث عن المستخدم.")
        return ConversationHandler.END

async def enter_points_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        points = float(update.message.text.strip())
        target_user_id = context.user_data.get('target_user_id')
        operation = context.user_data.get('operation')
        
        if operation == 'add':
            add_manual_points(target_user_id, points) # <-- استخدام الدالة الجديدة
            await update.message.reply_text(f"✅ تم إضافة {points} نقطة للمستخدم!")
        elif operation == 'reduce':
            add_manual_points(target_user_id, -points)
            await update.message.reply_text(f"✅ تم خصم {points} نقطة من المستخدم!")
            
        context.user_data.clear()
        
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('تم إلغاء العملية.')
    context.user_data.clear()
    return ConversationHandler.END
async def handle_points_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ العملية بناءً على عدد النقاط"""
    try:
        points = int(update.message.text.strip())
        user_id = context.user_data['user_id']
        operation = context.user_data['operation']

        if operation == 'add':
            add_points(user_id, points)
            await update.message.reply_text(f"✅ تم إضافة {points} نقطة.")
        elif operation == 'reduce':
            add_points(user_id, -points)
            await update.message.reply_text(f"✅ تم تقليل {points} نقطة.")
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال عدد صحيح.")
    finally:
        return ConversationHandler.END

async def load_scheduled_channels(context: ContextTypes.DEFAULT_TYPE):
    """تحميل القنوات المسجلة مسبقًا وإعادة جدولة الرسائل عند تشغيل البوت."""
    cursor.execute("SELECT channel_id, user_id FROM user_channels")
    channels = cursor.fetchall()

    if not channels:
        print("⚠️ لا توجد قنوات مسجلة في قاعدة البيانات!")
        return

    # إعادة جدولة كل قناة حسب وجود جلسات شخصية للمستخدم
    for (channel_id, user_id) in channels:
        # جدولة القناة (ستستخدم الجلسات الشخصية إذا وجدت)
        schedule_channel_messages(context, channel_id, user_id)
        # إعادة جدولة الخاص للمستخدم نفسه (إذا كان user_id هو نفسه channel_id)
        if str(channel_id) == str(user_id):
            schedule_channel_messages(context, user_id, user_id)

    print(f"✅ تمت إعادة جدولة الجلسات لجميع القنوات ({len(channels)}) المخزنة بنجاح!")

async def send_top_lists_and_reset(context: ContextTypes.DEFAULT_TYPE = None):
    bot = context.bot if context is not None else BOT_INSTANCE
    now = get_baghdad_time()
    channel_id = "@STUDYWITHELAHMED"  # ضع هنا معرف القناة الخاصة بك
    
    # الحصول على توب النقاط اليومية
    top_points = get_daily_points()
    points_message = "🏆 **توب النقاط لليوم**:\n\n"
    for rank, (uid, points) in enumerate(top_points, 1):
        try:
            user = await bot.get_chat(uid)
            user_name = user.first_name if user.first_name else "مجهول"
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
            if title:
                points_message += f"{rank}. {user_name} ({title}) - {points} نقطة\n"
            else:
                points_message += f"{rank}. {user_name} - {points} نقطة\n"
        except Exception:
            continue
    
    # الحصول على توب الساعات اليومية
    cursor.execute("""
        SELECT user_id, SUM(points) AS hours
        FROM user_daily_points
        WHERE date = DATE('now', 'localtime')
        GROUP BY user_id
        ORDER BY hours DESC
        LIMIT 60
    """)
    top_hours = cursor.fetchall()
    
    hours_message = "\n🕒 **توب الساعات لليوم**:\n\n"
    for rank, (uid, hours) in enumerate(top_hours, 1):
        try:
            user = await bot.get_chat(uid)
            user_name = user.first_name if user.first_name else "مجهول"
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"
            hours_text = points_to_hours_text(hours)
            if title:
                hours_message += f"{rank}. {user_name} ({title}) - {hours_text}\n"
            else:
                hours_message += f"{rank}. {user_name} - {hours_text}\n"

        except Exception:
            continue

    # إرسال الرسائل
    if channel_id:
        try:
            # إرسال رسالة توب النقاط
            await bot.send_message(
                chat_id=channel_id,
                text=points_message,
                parse_mode='Markdown'
)

# إرسال رسالة توب الساعات
            await bot.send_message(
                chat_id=channel_id,
                text=hours_message,
                parse_mode='Markdown'
)

            
            # رسالة تصفير النقاط
            reset_message = "🔄 تم تصفير النقاط والساعات اليومية.\nيوم جديد، بداية جديدة! 💪"
            await bot.send_message(
                chat_id=channel_id,
                text=reset_message
            )
        except Exception as e:
            print(f"Error sending messages: {e}")

    # تصفير النقاط اليومية
    cursor.execute("""
        DELETE FROM user_daily_points
        WHERE date < DATE('now', 'localtime')
    """)
    connection.commit()

async def send_monthly_top_and_reset(context: ContextTypes.DEFAULT_TYPE = None):
    bot = context.bot if context is not None else BOT_INSTANCE
    channel_id = "@STUDYWITHELAHMED"  # ضع هنا معرف القناة
    now = get_baghdad_time()
    top_users = get_monthly_points()
    top_users = get_monthly_points()
    # 📌 **إرسال توب النقاط الشهرية قبل التصفير**

    message = "🏆 **توب النقاط الشهرية:**\n\n" if (top_users, 1) else "🔹 لا توجد بيانات متاحة لهذا الشهر.\n"

    for rank, (uid, points) in enumerate(top_users, 1):
        try:
            user = await bot.get_chat(uid)
            user_name = user.first_name if user.first_name else "مجهول"

            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"

            message += f"{rank}. {user_name} {'('+title+')' if title else ''} - {points} نقطة\n"
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب بيانات المستخدم {uid}: {e}")
            continue

    # 📌 **إرسال توب الساعات الشهرية**
    cursor.execute("""
        SELECT user_id, SUM(points) AS hours
        FROM user_daily_points
        WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
        GROUP BY user_id
        ORDER BY hours DESC
        LIMIT 60
    """)
    top_users = cursor.fetchall()

    hours_text = points_to_hours_text(hours)
    hours_message += f"{rank}. {user_name} {'('+title+')' if title else ''} - {hours_text}\n"


    for rank, (uid, hours) in enumerate(top_users, 1):
        try:
            user = await bot.get_chat(uid)
            user_name = user.first_name if user.first_name else "مجهول"
            hours_message += f"{rank}. {user_name} {'('+title+')' if title else ''} - {hours:.2f} ساعة\n"
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب بيانات المستخدم {uid}: {e}")
            continue

    # 📌 **إرسال الرسائل إلى القناة**
    try:
        await bot.send_message(chat_id=channel_id, text=message, parse_mode='Markdown')
        await bot.send_message(chat_id=channel_id, text=hours_message, parse_mode='Markdown')
        await bot.send_message(chat_id=channel_id, text="🔄 تم تصفير إحصائيات الشهر.\n✨ شهر جديد، إنجازات جديدة! 💪")
    except Exception as e:
        print(f"⚠️ خطأ أثناء إرسال توب الشهر: {e}")
    # 📌 تصفير نقاط الشهر
    cursor.execute("""
        UPDATE user_monthly_points
        SET points = 0
        WHERE month = ? AND year = ?
    """, (now.month, now.year))
    connection.commit()

    # 📌 تصفير ساعات الشهر (تم التعديل هنا)
    cursor.execute("""
        DELETE FROM user_daily_points
        WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """)
    connection.commit()

async def send_yearly_top_and_reset(context: ContextTypes.DEFAULT_TYPE = None):
    bot = context.bot if context is not None else BOT_INSTANCE
    channel_id = "@STUDYWITHELAHMED"  # ضع هنا معرف القناة
    now = get_baghdad_time()
    today = get_baghdad_time().date()
    now = get_baghdad_time()
    week_number = now.isocalendar()[1]
    # 📌 **إرسال توب النقاط السنوية قبل التصفير**
    cursor.execute("""
        SELECT user_id, points
        FROM user_yearly_points
        WHERE year = ?
        ORDER BY points DESC
        LIMIT 60
    """, (now.year,))
    top_yearly = cursor.fetchall()

    message = "🏆 **توب النقاط السنوية:**\n\n" if top_yearly else "🔹 لا توجد بيانات متاحة لهذه السنة.\n"

    for rank, (uid, points) in enumerate(top_yearly, 1):
        try:
            user = await bot.get_chat(uid)
            user_name = user.first_name if user.first_name else "مجهول"

            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"

            message += f"{rank}. {user_name} {'('+title+')' if title else ''} - {points} نقطة\n"
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب بيانات المستخدم {uid}: {e}")
            continue

    # 📌 **إرسال توب الساعات السنوية**
    cursor.execute("""
        SELECT user_id, SUM(points) as total_hours
        FROM user_yearly_points
        WHERE year = ?
        GROUP BY user_id
        ORDER BY total_hours DESC
        LIMIT 60
    """, (now.year,))
    top_yearly_hours = cursor.fetchall()

    hours_text = points_to_hours_text(hours)
    hours_message += f"{rank}. {user_name} {'('+title+')' if title else ''} - {hours_text}\n"


    for rank, (uid, hours) in enumerate(top_yearly_hours, 1):
        try:
            user = await bot.get_chat(uid)
            user_name = user.first_name if user.first_name else "مجهول"
            hours_message += f"{rank}. {user_name} {'('+title+')' if title else ''} - {hours:.2f} ساعة\n"
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب بيانات المستخدم {uid}: {e}")
            continue

    # 📌 **إرسال الرسائل إلى القناة**
    try:
        await bot.send_message(chat_id=channel_id, text=message, parse_mode='Markdown')
        await bot.send_message(chat_id=channel_id, text=hours_message, parse_mode='Markdown')
        await bot.send_message(chat_id=channel_id, text="🔄 تم تصفير إحصائيات السنة.\n🎯 سنة جديدة، أهداف جديدة! 💪")
    except Exception as e:
        print(f"⚠️ خطأ أثناء إرسال توب السنة: {e}")

    # 📌 **تصفير نقاط السنة**
    cursor.execute("""
        UPDATE user_yearly_points
        SET points = 0
        WHERE year = ?
    """, (now.year,))

    connection.commit()


    # حذف   كل المدات فورمات ما عدا النقاط الاجماليه
    cursor.execute("""
        DELETE FROM user_daily_points 
        WHERE strftime('%Y', date) = strftime('%Y', 'now')
    """)
    
    connection.commit()


scheduler = AsyncIOScheduler()

scheduler.add_job(
    send_monthly_top_and_reset,
    'cron',
    day=1,          # يوم 12        # الشهر الثاني (فبراير)
    hour=23,          # الساعة 0 صباحاً (يمكنك تعديلها حسب رغبتك)
    minute=49,
    timezone=baghdad_tz
)
scheduler.add_job(
    send_yearly_top_and_reset,
    'cron',
    day=1,          # يوم 12
    month=1,         # الشهر الثاني (فبراير)
    hour=23,          # الساعة 0 صباحاً (يمكنك تعديلها حسب رغبتك)
    minute=48,
    timezone=baghdad_tz
)
async def start_scheduler():
    scheduler.start()



async def send_weekly_top_and_reset(context: ContextTypes.DEFAULT_TYPE):
    if hasattr(context, 'weekly_job_executed'):
        return
    context.weekly_job_executed = True
    bot = context.bot
    channel_id = "@STUDYWITHELAHMED"  # ضع هنا معرف القناة
    now = get_baghdad_time()
    week_number = now.isocalendar()[1]
    
    # جلب أفضل المستخدمين للساعات الأسبوعية
    cursor.execute("""
        SELECT user_id, SUM(points) AS hours
        FROM user_daily_points
        WHERE date >= ?
        GROUP BY user_id
        ORDER BY hours DESC
        LIMIT 60
    """, (week_number,))
    top_users = cursor.fetchall()
    
    message = "🏆 **توب الأسبوع - أفضل 60 طالب ساعات دراسة:**\n\n" if top_users else "🔹 لا يوجد احد دارس لهذا الأسبوع.\n"
    for rank, (uid, hours) in enumerate(top_users, 1):
        try:
            user = await bot.get_chat(uid)
            user_name = user.first_name if user.first_name else "مجهول"
            cursor.execute("SELECT title, username FROM users WHERE user_id = ?", (uid,))
            result = cursor.fetchone()
            title = result[0] if result and result[0] else ""
            username = result[1] if result and result[1] else f"{uid}"

            hours_text = points_to_hours_text(hours)
            if title:
                message += f"{rank}. {user_name} ({title}) - {hours_text}\n"
            else:
                message += f"{rank}. {user_name} - {hours_text}\n"
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب بيانات المستخدم {uid}: {e}")
            continue

    # إرسال الرسالة إلى القناة
    try:
        await bot.send_message(chat_id=channel_id, text=message, parse_mode='Markdown')
        await bot.send_message(chat_id=channel_id, text=f"🌀 خلص الأسبوع وتم تصفير ساعاته \n🕒يلا نبدأ من جديد تعالو ندرس ساعات اكثر")
    except Exception as e:
        print(f"⚠️ خطأ أثناء إرسال توب النقاط الأسبوعية: {e}")

    # تصفير النقاط الأسبوعية: حذف سجلات الأسبوع الحالي
    cursor.execute("""
        DELETE FROM user_weekly_points
        WHERE week = ? AND year = ?
    """, (week_number, now.year))
    connection.commit()

    # إعادة تعيين العلامة بعد الإرسال
    del context.weekly_job_executed


# معالج آمن للرسائل النصية
async def handle_session_text_safe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text.strip()
        state, selected_time, editing_session = get_user_state(user_id)

        # إضافة جلسة جديدة
        if state == "waiting_duration" and text.isdigit():
            duration = int(text)
            if 1 <= duration <= 300:
                hour, minute = map(int, selected_time.split("_"))
                session_number = add_personal_session(user_id, hour, minute, duration, context)
                end_hour = (hour + (minute + duration) // 60) % 24
                end_minute = (minute + duration) % 60
                start_time_12 = format_12_hour(hour, minute)
                end_time_12 = format_12_hour(end_hour, end_minute)
                ref_code = get_or_create_user_ref_code(user_id)
                update_user_state(user_id, None)
                await update.message.reply_text(
                    f"✅ تم إضافة الجلسة {session_number} بنجاح!\n\n"
                    f"🕐 من {start_time_12} إلى {end_time_12}\n"
                    f"⏱️ المدة: {duration} دقيقة\n\n"
                )
                asyncio.create_task(reschedule_personal_sessions(user_id, context))
                
                # إعادة عرض قائمة الجلسات الشخصية بعد الحذف
                await manage_personal_sessions(update, context)
            else:
                await update.message.reply_text("❌ يرجى إدخال مدة صحيحة بين 1 و 300 دقيقة")

        # تعديل جلسة موجودة
        elif state == "editing" and editing_session:
            # إذا أدخل المستخدم مدة جديدة
            if text.isdigit():
                duration = int(text)
                if 1 <= duration <= 300:
                    # جلب بيانات الجلسة القديمة
                    sessions = get_user_personal_sessions(user_id)
                    session = next((s for s in sessions if s[0] == editing_session), None)
                    if session:
                        start_hour, start_minute = session[1], session[2]
                        # تحديث الجلسة في قاعدة البيانات
                        cursor.execute("""
                            UPDATE personal_sessions
                            SET duration = ?
                            WHERE user_id = ? AND session_number = ?
                        """, (duration, user_id, editing_session))
                        connection.commit()
                        update_user_state(user_id, None)
                        await update.message.reply_text(f"✅ تم تعديل مدة الجلسة {editing_session} بنجاح!")
                        asyncio.create_task(reschedule_personal_sessions(user_id, context))
                    else:
                        await update.message.reply_text("❌ رقم الجلسة غير موجود")
                else:
                    await update.message.reply_text("❌ يرجى إدخال مدة صحيحة بين 1 و 300 دقيقة")
            # إذا أدخل المستخدم وقت جديد (مثال: 13:30)
            elif ":" in text:
                try:
                    hour, minute = map(int, text.split(":"))
                    if 0 <= hour < 24 and 0 <= minute < 60:
                        # تحديث وقت الجلسة في قاعدة البيانات
                        cursor.execute("""
                            UPDATE personal_sessions
                            SET start_hour = ?, start_minute = ?
                            WHERE user_id = ? AND session_number = ?
                        """, (hour, minute, user_id, editing_session))
                        connection.commit()
                        update_user_state(user_id, None)
                        sessions = get_user_personal_sessions(user_id)
                        session = next((s for s in sessions if s[0] == editing_session), None)
                        if session:
                            duration = session[3]
                            end_hour = (hour + (minute + duration) // 60) % 24
                            end_minute = (minute + duration) % 60
                            start_time_12 = format_12_hour(hour, minute)
                            end_time_12 = format_12_hour(end_hour, end_minute)
                            await update.message.reply_text(
                                f"✅ تم تعديل وقت الجلسة {editing_session} بنجاح!\n\n"
                                f"🕐 من {start_time_12} إلى {end_time_12}\n"
                                f"⏱️ المدة: {duration} دقيقة"
                            )
                        else:
                            await update.message.reply_text(f"✅ تم تعديل وقت الجلسة {editing_session} بنجاح!")
                        asyncio.create_task(reschedule_personal_sessions(user_id, context))
                    else:
                        await update.message.reply_text("❌ يرجى إدخال وقت صحيح (مثال: 13:30)")
                except Exception:
                    await update.message.reply_text("❌ يرجى إدخال وقت صحيح (مثال: 13:30)")
            
        # تحديد جلسة للتعديل أو الحذف
        elif text.isdigit():
            session_number = int(text)
            sessions = get_user_personal_sessions(user_id)
            if any(s[0] == session_number for s in sessions):
                keyboard = [
                    [InlineKeyboardButton("✏️ تعديل هذه الجلسة", callback_data=f"modify_session_{session_number}")],
                    [InlineKeyboardButton("🗑️ حذف هذه الجلسة", callback_data=f"delete_session_{session_number}")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_sessions")]
                ]
                markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"🔧 ماذا تريد أن تفعل بالجلسة {session_number}؟",
                    reply_markup=markup
                )
            else:
                await update.message.reply_text("❌ رقم الجلسة غير موجود")

    except Exception as e:
        print(f"خطأ في معالجة النص: {e}")
        await update.message.reply_text("❌ حدث خطأ، يرجى المحاولة مرة أخرى")

async def reschedule_personal_sessions(user_id, context):
    # إعادة جدولة جميع قنوات المستخدم (والخاص)
    cursor.execute("SELECT channel_id FROM user_channels WHERE user_id = ?", (user_id,))
    channels = cursor.fetchall()
    for (channel_id,) in channels:
        schedule_channel_messages(context, channel_id, user_id)
    schedule_channel_messages(context, user_id, user_id)

# إضافة أوامر جديدة لـ main()
def add_control_handlers(application):
    """إضافة معالجات التحكم في الجلسات"""
    
    # أمر لوحة التحكم
    application.add_handler(CommandHandler("control", sessions_control_panel))
    application.add_handler(MessageHandler(filters.Regex("^/تحكم$"), sessions_control_panel))
    
    # معالج أزرار التحكم
    application.add_handler(CallbackQueryHandler(
        button_callback,
        pattern="^(start_all_sessions|stop_all_sessions|toggle_all_sessions|toggle_channel_)"
    ))
    
    print("✅ تم إضافة أوامر التحكم:")
    print("   /control (إنجليزي)")
    print("   /تحكم (عربي)")


# الوظيفة الرئيسية لتشغيل البوت
def main():
    global BOT_INSTANCE
    application = Application.builder().token(BOT_TOKEN).build()
    BOT_INSTANCE = application.bot

    # تهيئة نظام الجلسات الشخصية
    init_personal_sessions_db()

    # ربط أوامر البداية
    application.add_handler(CommandHandler("start", start_with_personal_ref))

    # ConversationHandler للإدارة (النقاط)
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern='^(add_points|reduce_points)$')],
        states={
            ADD_POINTS_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_points_step)],
            REDUCE_POINTS_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reduce_points_step)],
            ENTER_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_points_step)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    application.add_handler(conv_handler)

    # معالجات الجلسات الشخصية
    application.add_handler(CallbackQueryHandler(
        button_callback,
        pattern="^(add_session|select_time_|back_to_sessions|edit_session_|delete_session_|modify_session_)"
    ))

    # معالج الأزرار العام
    application.add_handler(CallbackQueryHandler(button_callback))

    # ✅ معالج استخدام الأوامر المخصصة (يجب أن يكون أول MessageHandler في group=0)
    application.add_handler(MessageHandler(
        filters.Regex(r'^/\w+$'),
        handle_custom_command_usage
    ), group=0)

    # معالج الإذاعة (يجب أن يكون أول MessageHandler في group=0)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_broadcast_message), group=0)
    
    # معالج إنشاء الأوامر المخصصة (بعد الإذاعة واحد منهم يعمل)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_command_creation), group=0)
    
    # معالج الجلسات الشخصية (في group=1)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\d+$'),
        handle_session_text_safe
    ), group=1)

    # معالج رابط القناة (في group=2)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_link), group=2)

    # معالج /cancel عام
    application.add_handler(CommandHandler('cancel', cancel), group=0)

    # أوامر الجلسات
    add_session_commands(application)
    add_control_handlers(application)

    # تهيئة قواعد البيانات للأذاعة والأوامر
    init_broadcast_custom_db()
    initialize_personal_sessions()

    # تصفير يومي - 12 منتصف الليل بتوقيت بغداد
    application.job_queue.run_daily(
        send_top_lists_and_reset,
        time=datetime.time(hour=23, minute=59, tzinfo=pytz.timezone('Asia/Baghdad'))
    )

    # تشغيل استرجاع القنوات المسجلة عند بدء التشغيل
    application.job_queue.run_once(load_scheduled_channels, when=5)

    # بدء فحص التايمرات النشطة
    application.job_queue.run_once(start_timer_check, when=1)

    print("✅ تم إضافة نظام الإذاعة والأوامر المخصصة")
    print("🎯 البوت جاهز مع الميزات الجديدة:")
    print("   • جلسات شخصية وعامة")
    print("   • لوحة تحكم متقدمة")
    print("   • جدولة ذكية")

    application.run_polling()

# تعريف دالة start_command لتجنب الخطأ
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# تشغيل البوت
if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        MAIN_LOOP = loop
        asyncio.set_event_loop(loop)
        
        # تشغيل الجدولة قبل بدء البوت
        loop.run_until_complete(start_scheduler())
        
        # تشغيل البوت
        main()
        
    except Exception as e:
        print(f"❌ خطأ في تشغيل البوت: {e}")
        import traceback
        traceback.print_exc()
