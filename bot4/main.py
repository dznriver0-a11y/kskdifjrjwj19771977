import asyncio
import re
import logging
import sqlite3
from configparser import ConfigParser
from telethon import TelegramClient, events, utils
from telethon.errors import FloodWaitError
from telethon.tl.types import InputPeerChannel

# Configuration
cfg = ConfigParser()
cfg.read('config.ini')

API_ID = int(cfg.get('telegram', 'api_id', fallback='27210999'))
API_HASH = cfg.get('telegram', 'api_hash', fallback='c5d1e4d334d6c3746ee2666c099eef70')
SESSION = cfg.get('telegram', 'session', fallback='session')
BOT_USERNAME = cfg.get('telegram', 'bot_username', fallback='@W8RBOT')
SOURCE_CHANNEL = cfg.get('telegram', 'source_channel', fallback='@ALCRTOON')
BACKUP_CHANNEL = cfg.get('telegram', 'backup_channel', fallback='@hsisig8757')
DB_PATH = cfg.get('telegram', 'db', fallback='progress.db')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LINK_RE = re.compile(r'https?://[^\s)>\]]+')

def init_db(path):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_msg_id INTEGER
        )
    ''')
    cur.execute('INSERT OR IGNORE INTO progress(id, last_msg_id) VALUES(1, 0)')
    conn.commit()
    return conn

def get_last_processed(conn):
    cur = conn.cursor()
    cur.execute('SELECT last_msg_id FROM progress WHERE id=1')
    return cur.fetchone()[0]

def set_last_processed(conn, msg_id):
    cur = conn.cursor()
    cur.execute('UPDATE progress SET last_msg_id = ? WHERE id=1', (msg_id,))
    conn.commit()

async def process_video(client, msg, bot, src, backup, conn):
    """معالجة فيديو واحد"""
    logger.info('Processing msg id=%s date=%s', msg.id, msg.date)

    # Step 1: Send video to bot and wait for reply with stream link
    stream_link = None
    MAX_TRIES = 5
    for attempt in range(1, MAX_TRIES+1):
        try:
            async with client.conversation(bot, timeout=90) as conv:
                await conv.send_file(msg.video)
                logger.info('Sent video to bot (attempt %s)', attempt)
                
                await asyncio.sleep(3)
                
                try:
                    resp = await conv.get_response(timeout=90)
                    text = resp.text if resp else ''
                    m = LINK_RE.search(text)
                    if m:
                        stream_link = m.group(0)
                        logger.info('Got stream link: %s', stream_link)
                        break
                    else:
                        logger.warning('Bot responded but no link found: %s (attempt %s)', text, attempt)
                except asyncio.TimeoutError:
                    logger.warning('Timeout waiting for bot response (attempt %s)', attempt)
                    await asyncio.sleep(10)
                    continue
        except FloodWaitError as e:
            logger.warning('Flood wait %s seconds', e.seconds)
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.exception('Error sending to bot (attempt %s): %s', attempt, e)
            await asyncio.sleep(10)

    if not stream_link:
        logger.error('لم يحصل على رابط من البوت للرسالة %s — تخطّى إلى التالية', msg.id)
        set_last_processed(conn, msg.id)
        return

    # Step 2: Generate original message link
    if getattr(src, 'username', None):
        orig_link = f'https://t.me/{src.username}/{msg.id}'
    else:
        channel_id = utils.get_peer_id(src)
        if channel_id < 0:
            channel_id = abs(channel_id)
        orig_link = f'https://t.me/c/{channel_id}/{msg.id}'
    logger.info('Original link: %s', orig_link)

    # Step 3: Send both links together to backup channel
    stream_link = stream_link.strip('`').strip()
    backup_text = f'رابط الاستريم:\n{stream_link}\n\nرابط الفيديو الأصلي:\n{orig_link}'
    try:
        backup_msg = await client.send_message(backup, backup_text)
        logger.info('Sent links to backup channel')
    except Exception as e:
        logger.exception('Failed to send to backup channel: %s', e)
        set_last_processed(conn, msg.id)
        return

    # Step 4: Edit original message
    try:
        orig_msg = await client.get_messages(src, ids=msg.id)
        current_caption = getattr(orig_msg, 'message', None) or getattr(orig_msg, 'text', '') or ''
        
        # Remove any existing stream links
        current_caption = re.sub(r'\n\n\[اضغط للمشاهدة اونلاين\]\(.*?\)', '', current_caption)
        
        add_line = f'\n\n[اضغط للمشاهدة اونلاين]({stream_link})'
        new_caption = current_caption + add_line
        
        await client.edit_message(src, msg.id, new_caption, parse_mode='md')
        logger.info('Edited original message %s', msg.id)
    except Exception as e:
        logger.exception('Failed to edit original message %s: %s', msg.id, e)
        logger.error('تأكد أن الحساب يمتلك صلاحية "Edit messages" كـ admin في القناة الأصلية.')

    # Step 5: Save progress
    set_last_processed(conn, msg.id)
    logger.info('Finished processing msg %s', msg.id)

async def main():
    if API_ID == 0 or API_HASH == '':
        logger.error('ضع إعدادات Telegram (api_id, api_hash) في config.ini')
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    logger.info('Client started')

    conn = init_db(DB_PATH)
    last_processed = get_last_processed(conn)
    logger.info('Last processed message id: %s', last_processed)

    # Resolve entities
    src = await client.get_entity(SOURCE_CHANNEL)
    backup = await client.get_entity(BACKUP_CHANNEL)
    bot = await client.get_entity(BOT_USERNAME)

    # معالجة الفيديوهات القديمة أولاً
    logger.info('معالجة الفيديوهات القديمة...')
    async for msg in client.iter_messages(src, reverse=True):
        if not msg.video:
            continue
        if msg.id <= last_processed:
            continue
        
        await process_video(client, msg, bot, src, backup, conn)
        await asyncio.sleep(10)  # انتظار بين الفيديوهات

    logger.info('انتهت معالجة الفيديوهات القديمة. الآن في وضع المراقبة للفيديوهات الجديدة...')

    # مراقبة الرسائل الجديدة
    @client.on(events.NewMessage(chats=src))
    async def handler(event):
        msg = event.message
        if not msg.video:
            return
        
        last = get_last_processed(conn)
        if msg.id <= last:
            return
        
        logger.info('🆕 فيديو جديد اكتُشف!')
        await process_video(client, msg, bot, src, backup, conn)

    # البقاء متصلاً
    await client.run_until_disconnected()
    conn.close()
    logger.info('Done.')

if __name__ == '__main__':
    asyncio.run(main())