import logging
import sqlite3
import asyncio
from datetime import datetime
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode

# إعدادات البوت
BOT_TOKEN = "7978232505:AAHOlE6PqB5hCB1i7dRmeVbgA7h2AEV2bJI"  # ضع توكن البوت هنا
ADMIN_USER_ID = 5652989037  # ضع معرف المطور هنا
CHANNEL_USERNAME = "@AlCRTOON"  # ضع يوزر القناة هنا

# إعداد نظام السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramSearchBot:
    def __init__(self):
        self.db_path = "search_bot.db"
        self.auto_add_enabled = False
        self.processed_messages = set()  # لتجنب إضافة المحتوى المكرر
        self.init_database()
        
    def init_database(self):
        """إنشاء قاعدة البيانات والجداول"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول المحتوى
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(title, url)
            )
        ''')
        
        # جدول المستخدمين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الإحصائيات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                search_query TEXT,
                search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الرسائل المعالجة للإضافة التلقائية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id INTEGER PRIMARY KEY,
                channel_username TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """إضافة مستخدم جديد أو تحديث معلوماته"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_activity)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, datetime.now()))
        
        conn.commit()
        conn.close()
    
    def log_search(self, user_id: int, query: str):
        """تسجيل عملية البحث"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO searches (user_id, search_query)
            VALUES (?, ?)
        ''', (user_id, query))
        
        conn.commit()
        conn.close()
    
    def add_content(self, title: str, url: str):
        """إضافة محتوى جديد"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO content (title, url)
                VALUES (?, ?)
            ''', (title, url))
            
            conn.commit()
            return cursor.rowcount > 0  # إرجاع True إذا تم إدراج محتوى جديد
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def search_content(self, query: str) -> List[Dict]:
        """البحث عن المحتوى بترتيب أبجدي"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # البحث الأبجدي - أولاً النتائج التي تبدأ بالاستعلام
        cursor.execute('''
            SELECT title, url FROM content 
            WHERE title LIKE ? 
            ORDER BY 
                CASE WHEN LOWER(title) LIKE LOWER(?) THEN 1 ELSE 2 END,
                LENGTH(title),
                title COLLATE NOCASE
        ''', (f'%{query}%', f'{query}%'))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{'title': row[0], 'url': row[1]} for row in results]
    
    def get_user_stats(self) -> Dict:
        """الحصول على إحصائيات المستخدمين"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM searches')
        total_searches = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM content')
        total_content = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_users': total_users,
            'total_searches': total_searches,
            'total_content': total_content
        }
    
    def get_all_content(self) -> List[Dict]:
        """الحصول على جميع المحتوى"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT title, url FROM content ORDER BY title')
        results = cursor.fetchall()
        conn.close()
        
        return [{'title': row[0], 'url': row[1]} for row in results]
    
    def is_message_processed(self, message_id: int) -> bool:
        """التحقق من معالجة الرسالة مسبقاً"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM processed_messages WHERE message_id = ?', (message_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def mark_message_processed(self, message_id: int):
        """وضع علامة على الرسالة كمعالجة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO processed_messages (message_id, channel_username)
            VALUES (?, ?)
        ''', (message_id, CHANNEL_USERNAME))
        
        conn.commit()
        conn.close()


    def delete_content(self, titles: List[str]) -> int:
        """حذف محتوى بواسطة عناوين متعددة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        deleted_count = 0
        for title in titles:
            cursor.execute('DELETE FROM content WHERE title = ?', (title,))
            if cursor.rowcount > 0:
                deleted_count += 1
        
        conn.commit()
        conn.close()
        return deleted_count
    
    def get_content_titles(self) -> List[str]:
        """الحصول على جميع عناوين المحتوى"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT title FROM content ORDER BY title')
        results = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in results]

# إنشاء كائن البوت
bot = TelegramSearchBot()

# متغيرات لحفظ حالة المستخدمين
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    user = update.effective_user
    bot.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_message = "👋 مرحباً! يمكنك مراسلتي بشكل خاص وسأساعدك في معرفة ما إذا كان المسلسل أو الفيلم متوفراً."
    
    if user.id == ADMIN_USER_ID:
        keyboard = [
            [InlineKeyboardButton("إنشاء", callback_data='create_content'),
             InlineKeyboardButton("إضافة تلقائي", callback_data='toggle_auto_add')],
            [InlineKeyboardButton("إحصائيات المستخدمين", callback_data='user_stats'),
             InlineKeyboardButton("إشاعة", callback_data='broadcast')],
            [InlineKeyboardButton("عرض المحتوى", callback_data='show_content'),
            InlineKeyboardButton("حذف", callback_data='delete_content')]  # الزر الجد
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل النصية"""
    user = update.effective_user
    
    # التحقق من وجود الرسالة والنص
    if not update.message or not update.message.text:
        return
    
    message = update.message.text
    
    # تحديث آخر نشاط للمستخدم
    bot.add_user(user.id, user.username, user.first_name, user.last_name)
    
    # إذا كان المستخدم في حالة إنشاء محتوى
    if user.id in user_states and user_states[user.id].startswith('creating_'):
        await handle_content_creation(update, context)
        return
    
    # إذا كان المستخدم هو المطور ويريد إرسال إشاعة
    if user.id == ADMIN_USER_ID and user.id in user_states and user_states[user.id] == 'broadcasting':
        await handle_broadcast(update, context)
        return
    
    # البحث عن المحتوى
    bot.log_search(user.id, message)
    results = bot.search_content(message)
    
    if results:
        response = "🎬 النتائج المتوفرة:\n\n"
        for result in results[:10]:  # عرض أول 10 نتائج
            response += f"- [{result['title']}]({result['url']})\n"
        
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        # إظهار رسالة "غير متوفر" فقط إذا كان بالخاص
        if update.effective_chat.type == "private":
            not_found_message = (
                "هذا العمل غير متوفر حاليًا، نحن نعمل على رفع جميع الأعمال المطلوبة تدريجيًا، "
                "ونقدّر صبركم وتفاعلكم. يرجى المحاولة لاحقًا.🌟🎬"
            )
            await update.message.reply_text(not_found_message)
        else:
            # تجاهل إذا كان في مجموعة أو قناة
            return


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار"""
    query = update.callback_query
    user = query.from_user
    
    if user.id != ADMIN_USER_ID:
        await query.answer("غير مصرح لك باستخدام هذه الميزة.")
        return
    
    await query.answer()
    
    if query.data == 'create_content':
        user_states[user.id] = 'creating_title'
        await query.edit_message_text("أرسل عنوان المحتوى الجديد:")
    
    elif query.data == 'toggle_auto_add':
        bot.auto_add_enabled = not bot.auto_add_enabled
        status = "تم تفعيل ✅" if bot.auto_add_enabled else "تم إيقاف ❌"
        await query.edit_message_text(f"{status} الإضافة التلقائية\n\nملاحظة: يجب أن يكون البوت مشرفاً في القناة {CHANNEL_USERNAME} لتعمل هذه الميزة")
    
    elif query.data == 'user_stats':
        stats = bot.get_user_stats()
        stats_message = f"""📊 إحصائيات البوت:

👥 إجمالي المستخدمين: {stats['total_users']}
🔍 إجمالي عمليات البحث: {stats['total_searches']}
🎬 إجمالي المحتوى: {stats['total_content']}"""
        
        await query.edit_message_text(stats_message)
    
    elif query.data == 'broadcast':
        user_states[user.id] = 'broadcasting'
        await query.edit_message_text("أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
    
    elif query.data == 'show_content':
        all_content = bot.get_all_content()
        if all_content:
            content_message = "📋 جميع المحتوى المضاف:\n\n"
            for i, content in enumerate(all_content[:50], 1):  # عرض أول 50 محتوى
                content_message += f"{i}. [{content['title']}]({content['url']})\n"
            
            if len(all_content) > 50:
                content_message += f"\n... و {len(all_content) - 50} محتوى إضافي"
            
            await query.edit_message_text(content_message, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("📋 لا يوجد محتوى مضاف حالياً.")


    elif query.data == 'delete_content':
        all_titles = bot.get_content_titles()
        
        if not all_titles:
            await query.edit_message_text("📋 لا يوجد محتوى مضاف حالياً.")
            return
        
        content_message = "📋 اختر المحتوى لحذفه (انسخ العنوان):\n\n"
        for i, title in enumerate(all_titles[:50], 1):  # عرض أول 50 محتوى
            content_message += f"`{title}`\n"
        
        if len(all_titles) > 50:
            content_message += f"\n... و {len(all_titles) - 50} محتوى إضافي"
        
        keyboard = [
            [InlineKeyboardButton("خروج من الحذف", callback_data='exit_delete')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_states[user.id] = 'deleting_content'
        await query.edit_message_text(
            content_message + "\n\n❕ أرسل العناوين التي تريد حذفها (واحدة أو أكثر في كل رسالة):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif query.data == 'exit_delete':
        if user.id in user_states and user_states[user.id] == 'deleting_content':
            del user_states[user.id]
            await query.edit_message_text("تم الخروج من وضع الحذف.")
        else:
            await query.answer("لست في وضع الحذف حالياً.")

async def handle_content_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إنشاء المحتوى"""
    user = update.effective_user
    message = update.message.text
    
    if user_states[user.id] == 'creating_title':
        context.user_data['content_title'] = message
        user_states[user.id] = 'creating_url'
        await update.message.reply_text("أرسل رابط المحتوى:")
    
    elif user_states[user.id] == 'creating_url':
        title = context.user_data['content_title']
        url = message
        
        success = bot.add_content(title, url)
        del user_states[user.id]
        
        if success:
            await update.message.reply_text(f"✅ تم إضافة المحتوى بنجاح!\n\n📝 العنوان: {title}\n🔗 الرابط: {url}")
        else:
            await update.message.reply_text(f"⚠️ المحتوى موجود مسبقاً أو فشل في الإضافة!\n\n📝 العنوان: {title}\n🔗 الرابط: {url}")


async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج عملية الحذف"""
    user = update.effective_user
    message = update.message.text
    
    if user.id not in user_states or user_states[user.id] != 'deleting_content':
        return
    
    # تقسيم الرسالة إلى عناوين (سطر بسطر أو بفواصل)
    titles = [title.strip() for title in message.split('\n') if title.strip()]
    
    if not titles:
        await update.message.reply_text("❌ لم يتم تحديد عناوين للحذف. أرسل العناوين مرة أخرى:")
        return
    
    deleted_count = bot.delete_content(titles)
    
    if deleted_count > 0:
        response = f"✅ تم حذف {deleted_count} من أصل {len(titles)} نتيجة:\n\n"
        for title in titles:
            status = "✓" if title in [t for t in titles] else "✗"  # تبسيط الفحص
            response += f"{status} {title}\n"
    else:
        response = "❌ لم يتم العثور على أي من العناوين المحددة!"
    
    # إبقاء المستخدم في وضع الحذف ليتيح له حذف المزيد
    response += "\n\nأرسل عناوين أخرى للحذف أو اضغط /exit للخروج"
    await update.message.reply_text(response)

async def exit_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر الخروج من وضع الحذف"""
    user = update.effective_user
    
    if user.id in user_states and user_states[user.id] == 'deleting_content':
        del user_states[user.id]
        await update.message.reply_text("تم الخروج من وضع الحذف.")
    else:
        await update.message.reply_text("لست في وضع الحذف حالياً.")

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الإشاعة"""
    user = update.effective_user
    message = update.message.text
    
    # الحصول على جميع المستخدمين
    conn = sqlite3.connect(bot.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    sent_count = 0
    failed_count = 0
    
    for user_row in users:
        user_id = user_row[0]
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            sent_count += 1
            await asyncio.sleep(0.1)  # تأخير بسيط لتجنب الحد الأقصى للطلبات
        except TelegramError as e:
            failed_count += 1
            logger.warning(f"فشل إرسال رسالة للمستخدم {user_id}: {e}")
    
    del user_states[user.id]
    
    await update.message.reply_text(f"📢 تم إرسال الإشاعة!\n\n✅ تم الإرسال: {sent_count}\n❌ فشل الإرسال: {failed_count}")

async def process_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج رسائل القناة للإضافة التلقائية"""
    if not bot.auto_add_enabled:
        logger.debug("الإضافة التلقائية غير مفعلة")
        return
    
    message = update.channel_post
    if not message:
        logger.debug("لا توجد رسالة في المنشور")
        return
    
    # الحصول على النص سواء كان في الرسالة أو في التسمية التوضيحية
    text = message.text or message.caption
    if not text:
        logger.debug("الرسالة لا تحتوي على نص")
        return
    
    # التحقق من أن الرسالة من القناة المحددة
    channel_username = CHANNEL_USERNAME.replace('@', '').strip().lower()
    if not message.chat.username or message.chat.username.lower() != channel_username:
        logger.info(f"رسالة من قناة غير مستهدفة: {message.chat.username} (المستهدف: {channel_username})")
        return
    
    # التحقق من عدم معالجة الرسالة مسبقاً
    if bot.is_message_processed(message.message_id):
        logger.info(f"تمت معالجة الرسالة {message.message_id} مسبقاً")
        return
    
    # البحث عن النص العريض في الرسالة
    bold_text = None
    entities = message.entities or message.caption_entities
    
    if entities:
        for entity in entities:
            if entity.type == "bold":
                start = entity.offset
                end = start + entity.length
                bold_text = text[start:end].strip()
                logger.debug(f"تم العثور على نص عريض: {bold_text}")
                break
    
    if not bold_text:
        logger.info(f"لم يتم العثور على نص عريض في الرسالة {message.message_id}")
        return
    
    # تحديد البادئة
    prefix = ""
    keywords = ["كرتون", "محاضرة", "مسلسل", "فيلم", "انمي", "anime", "cartoon", "movie", "series"]
    
    # التحقق إذا كان النص يحتوي على أي من الكلمات المفتاحية
    contains_keyword = any(keyword in bold_text.lower() for keyword in keywords)
    
    if not contains_keyword:
        prefix = "مسلسل "
        logger.debug(f"إضافة بادئة 'مسلسل' للنص: {bold_text}")
    
    title = prefix + bold_text
    url = f"https://t.me/{channel_username}/{message.message_id}"
    
    # إضافة المحتوى
    success = bot.add_content(title, url)
    
    if success:
        # وضع علامة على الرسالة كمعالجة
        bot.mark_message_processed(message.message_id)
        logger.info(f"تم إضافة محتوى تلقائي: {title} - {url}")
        
        # إشعار المطور
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"✅ تم إضافة محتوى تلقائي:\n📝 {title}\n🔗 {url}"
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار للمطور: {e}")
    else:
        logger.info(f"لم يتم إضافة {title} لأنه موجود مسبقاً")
    # اختبار الإضافة التلقائية
    test_title = "اختبار الإضافة التلقائية"
    test_url = "https://t.me/test/123"
    if bot.add_content(test_title, test_url):
        logger.debug("✅ اختبار الإضافة نجح")
    else:
        logger.debug("❌ اختبار الإضافة فشل - المحتوى موجود مسبقاً")
def main():
    """الوظيفة الرئيسية لتشغيل البوت"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة معالجات الأحداث
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback))
        
        # إضافة معالج رسائل القناة للإضافة التلقائية
        application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, process_channel_message))
        
        logger.info("تم بدء تشغيل البوت...")
        
        # إضافة معالج للحذف
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_USER_ID), 
            handle_delete
        ))
        
        # إضافة معالج لأمر الخروج
        application.add_handler(CommandHandler("exit", exit_delete))

        # تشغيل البوت
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")

if __name__ == '__main__':
    main()
