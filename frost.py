import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "starbot.db"

TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. FadeHost Environment Variables "
        "bo'limiga BOT_TOKEN qo'shing."
    )

OWNER_ID = 6383248812

DEFAULT_TASK_REWARD = 0.1
REFERRAL_REWARD = 1.5


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("FrostStars")


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return sqlite3.connect(DB_PATH)


def ensure_column(conn, table, column, definition):
    cur = conn.cursor()

    cur.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]

    if column not in columns:
        cur.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            referred_by INTEGER,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # COMPLETED TASKS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id TEXT,
            completed_at TEXT,
            UNIQUE(user_id, channel_id)
        )
    """)

    # --------------------------------------------------------
    # GIFTS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            gift_name TEXT,
            price REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # TASK CHANNELS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            username TEXT,
            title TEXT,
            reward REAL DEFAULT 0.1,
            active INTEGER DEFAULT 1
        )
    """)

    # --------------------------------------------------------
    # ADMINS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)

    # --------------------------------------------------------
    # ACTIVITY LOGS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # ADVERTISEMENTS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # MANDATORY CHANNELS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            title TEXT,
            username TEXT,
            invite_link TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    # --------------------------------------------------------
    # OLD DATABASE MIGRATION
    # --------------------------------------------------------

    ensure_column(conn, "users", "username", "TEXT")
    ensure_column(conn, "users", "first_name", "TEXT")
    ensure_column(conn, "users", "balance", "REAL DEFAULT 0")
    ensure_column(conn, "users", "referred_by", "INTEGER")
    ensure_column(conn, "users", "created_at", "TEXT")

    ensure_column(conn, "channels", "channel_id", "TEXT")
    ensure_column(conn, "channels", "username", "TEXT")
    ensure_column(conn, "channels", "title", "TEXT")
    ensure_column(conn, "channels", "reward", "REAL DEFAULT 0.1")
    ensure_column(conn, "channels", "active", "INTEGER DEFAULT 1")

    ensure_column(conn, "mandatory_channels", "channel_id", "TEXT")
    ensure_column(conn, "mandatory_channels", "title", "TEXT")
    ensure_column(conn, "mandatory_channels", "username", "TEXT")
    ensure_column(conn, "mandatory_channels", "invite_link", "TEXT")
    ensure_column(conn, "mandatory_channels", "active", "INTEGER DEFAULT 1")

    # --------------------------------------------------------
    # OWNER ADMIN
    # --------------------------------------------------------

    cur.execute(
        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
        (OWNER_ID,),
    )

    conn.commit()

    conn.close()


# ============================================================
# USER FUNCTIONS
# ============================================================

def add_user(user, referred_by=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user.id,),
    )

    existing = cur.fetchone()

    if existing:

        cur.execute("""
            UPDATE users
            SET username = ?,
                first_name = ?
            WHERE user_id = ?
        """, (
            user.username or "",
            user.first_name or "",
            user.id,
        ))

    else:

        cur.execute("""
            INSERT INTO users
            (
                user_id,
                username,
                first_name,
                balance,
                referred_by,
                created_at
            )
            VALUES (?, ?, ?, 0, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            referred_by,
            datetime.now().isoformat(),
        ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
    )

    result = cur.fetchone()

    conn.close()

    return result


def get_balance(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,),
    )

    result = cur.fetchone()

    conn.close()

    if result:
        return float(result[0] or 0)

    return 0.0


def change_balance(user_id, amount):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = COALESCE(balance, 0) + ?
        WHERE user_id = ?
    """, (
        amount,
        user_id,
    ))

    conn.commit()
    conn.close()


def get_user_count():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    result = cur.fetchone()[0]

    conn.close()

    return result


def get_all_users():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            username,
            first_name,
            balance
        FROM users
        ORDER BY user_id DESC
    """)

    result = cur.fetchall()

    conn.close()

    return result


# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def is_admin(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM admins WHERE user_id = ?",
        (user_id,),
    )

    result = cur.fetchone()

    conn.close()

    return bool(result)


def is_owner(user_id):
    return user_id == OWNER_ID


def get_admins():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM admins"
    )

    result = [
        row[0]
        for row in cur.fetchall()
    ]

    conn.close()

    return result


def add_admin(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
        (user_id,),
    )

    conn.commit()
    conn.close()


def remove_admin(user_id):
    if user_id == OWNER_ID:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM admins WHERE user_id = ?",
        (user_id,),
    )

    conn.commit()
    conn.close()


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_activity(user_id, action):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO activity_logs
        (
            user_id,
            action,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        action,
        datetime.now().isoformat(),
    ))

    conn.commit()
    conn.close()


# ============================================================
# BOTTOM KEYBOARD
# ============================================================

def bottom_keyboard():

    return ReplyKeyboardMarkup(
        [
            ["☰ Tugma"]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ============================================================
# MAIN MENU
# ============================================================

def main_menu(user_id):

    buttons = [
        [
            InlineKeyboardButton(
                "⭐ Stars ishlash",
                callback_data="stars",
            ),
            InlineKeyboardButton(
                "🎁 Gift olish",
                callback_data="gift",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Referal",
                callback_data="referral",
            ),
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="balance",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="statistics",
            ),
            InlineKeyboardButton(
                "📜 Qoidalar",
                callback_data="rules",
            ),
        ],
        [
            InlineKeyboardButton(
                "📢 Reklama",
                callback_data="advertising",
            ),
        ],
    ]

    if is_admin(user_id):

        buttons.append([
            InlineKeyboardButton(
                "⚙️ Admin panel",
                callback_data="admin",
            )
        ])

    return InlineKeyboardMarkup(buttons)


# ============================================================
# BACK BUTTONS
# ============================================================

def back_main():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back",
            )
        ]
    ])


def back_admin():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Admin panel",
                callback_data="admin",
            )
        ]
    ])


# ============================================================
# STARS MENU
# ============================================================

def stars_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⭐ Vazifalarni bajarish",
                callback_data="task",
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="balance",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Bosh menyu",
                callback_data="back",
            )
        ],
    ])


# ============================================================
# GIFT MENU
# ============================================================

def gift_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❤️ Yurak — 5 ⭐",
                callback_data="buygift:Heart:5",
            )
        ],
        [
            InlineKeyboardButton(
                "🧸 Teddy Bear — 10 ⭐",
                callback_data="buygift:Teddy_Bear:10",
            )
        ],
        [
            InlineKeyboardButton(
                "🌹 Rose — 15 ⭐",
                callback_data="buygift:Rose:15",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Bosh menyu",
                callback_data="back",
            )
        ],
    ])


# ============================================================
# MANDATORY CHANNELS
# ============================================================

def get_mandatory_channels():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            channel_id,
            title,
            username,
            invite_link
        FROM mandatory_channels
        WHERE active = 1
        ORDER BY id ASC
    """)

    result = cur.fetchall()

    conn.close()

    return result


def mandatory_keyboard():

    channels = get_mandatory_channels()

    buttons = []

    for channel in channels:

        title = channel[2] or "Kanal"
        username = channel[3]
        invite_link = channel[4]

        link = invite_link

        if not link and username:

            clean_username = username.replace(
                "@",
                "",
            )

            link = (
                f"https://t.me/"
                f"{clean_username}"
            )

        if link:

            buttons.append([
                InlineKeyboardButton(
                    f"📢 {title}",
                    url=link,
                )
            ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="checkmandatory",
        )
    ])

    return InlineKeyboardMarkup(buttons)


def mandatory_text():

    return (
        "🔒 <b>Majburiy obuna</b>\n\n"
        "Botdan foydalanish uchun quyidagi "
        "kanallarga obuna bo'ling.\n\n"
        "Obuna bo'lgach, "
        "<b>✅ Tekshirish</b> tugmasini bosing."
    )


async def check_mandatory(update, context):

    user_id = update.effective_user.id

    channels = get_mandatory_channels()

    if not channels:
        return True

    for channel in channels:

        channel_id = channel[1]

        if not channel_id:
            continue

        try:

            member = await context.bot.get_chat_member(
                chat_id=channel_id,
                user_id=user_id,
            )

            if member.status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                continue

            if (
                member.status
                == ChatMemberStatus.RESTRICTED
                and member.is_member
            ):
                continue

            return False

        except Exception as e:

            logger.warning(
                "Mandatory check error: %s",
                e,
            )

            continue

    return True


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    referral_id = None

    if context.args:

        try:

            referral_id = int(
                context.args[0]
            )

            if referral_id == user.id:
                referral_id = None

        except ValueError:

            referral_id = None

    existing = get_user(user.id)

    add_user(
        user,
        referral_id if not existing else None,
    )

    # Yangi user referral mukofoti
    if not existing and referral_id:

        if get_user(referral_id):

            change_balance(
                referral_id,
                REFERRAL_REWARD,
            )

            log_activity(
                referral_id,
                f"Referral +{REFERRAL_REWARD} ⭐",
            )

    log_activity(
        user.id,
        "/start",
    )

    # Adminlarga mandatory tekshiruv yo'q
    if not is_admin(user.id):

        allowed = await check_mandatory(
            update,
            context,
        )

        if not allowed:

            await update.message.reply_text(
                mandatory_text(),
                parse_mode="HTML",
                reply_markup=mandatory_keyboard(),
            )

            return

    text = (
        "⭐ <b>FrostStars</b>\n\n"
        f"Salom, <b>{user.first_name}</b>!\n\n"
        "Pastdagi <b>☰ Tugma</b>ni bosing "
        "va kerakli bo'limni tanlang."
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=bottom_keyboard(),
    )


# ============================================================
# STARS
# ============================================================

async def show_stars(query):

    text = (
        "⭐ <b>Stars ishlash</b>\n\n"
        "Kanallarga obuna bo'lib Stars ishlang.\n\n"
        "Har bir vazifa bajarilganda "
        "belgilangan miqdordagi Stars balansingizga qo'shiladi."
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=stars_menu(),
    )


# ============================================================
# TASK FUNCTIONS
# ============================================================

def get_tasks():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            channel_id,
            username,
            title,
            reward
        FROM channels
        WHERE active = 1
        ORDER BY id ASC
    """)

    result = cur.fetchall()

    conn.close()

    return result


def get_completed_task_ids(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT channel_id
        FROM completed_tasks
        WHERE user_id = ?
    """, (
        user_id,
    ))

    rows = cur.fetchall()

    conn.close()

    return {
        str(row[0])
        for row in rows
    }


def get_next_task(user_id):

    tasks = get_tasks()

    completed = get_completed_task_ids(
        user_id
    )

    for task in tasks:

        task_id = task[0]

        if str(task_id) not in completed:
            return task

    return None


def get_task_number(user_id):

    tasks = get_tasks()

    completed = get_completed_task_ids(
        user_id
    )

    completed_count = len(
        completed
    )

    return completed_count + 1, len(tasks)


# ============================================================
# SHOW NEXT TASK
# ============================================================

async def show_task(query):

    user_id = query.from_user.id

    task = get_next_task(
        user_id
    )

    task_number, total_tasks = get_task_number(
        user_id
    )

    # --------------------------------------------------------
    # BARCHA VAZIFALAR BAJARILGAN
    # --------------------------------------------------------

    if not task:

        await query.edit_message_text(
            "🎉 <b>Barcha vazifalarni bajardingiz!</b>\n\n"
            "⭐ Hozircha yangi vazifalar mavjud emas.\n\n"
            "Yangi vazifalar qo'shilsa, "
            "yana Stars ishlashingiz mumkin.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⭐ Stars",
                        callback_data="stars",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Bosh menyu",
                        callback_data="back",
                    )
                ],
            ]),
        )

        return

    # --------------------------------------------------------
    # TASK DATA
    # --------------------------------------------------------

    task_id = task[0]
    channel_id = task[1]
    username = task[2]
    title = task[3] or "Kanal"
    reward = float(task[4] or DEFAULT_TASK_REWARD)

    buttons = []

    # Kanalga o'tish
    if username:

        clean_username = username.replace(
            "@",
            "",
        )

        buttons.append([
            InlineKeyboardButton(
                f"📢 {title}",
                url=f"https://t.me/{clean_username}",
            )
        ])

    # Agar username bo'lmasa, ID bo'yicha
    # avtomatik link berib bo'lmaydi.
    # Shuning uchun faqat tekshirish chiqadi.

    buttons.append([
        InlineKeyboardButton(
            f"✅ Tekshirish • +{reward:g} ⭐",
            callback_data=f"checktask:{task_id}",
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 Stars",
            callback_data="stars",
        )
    ])

    text = (
        "⭐ <b>Stars ishlash</b>\n\n"
        f"📌 Vazifa: <b>{task_number}/{total_tasks}</b>\n\n"
        f"📢 <b>{title}</b>\n"
        f"🎁 Mukofot: <b>+{reward:g} ⭐</b>\n\n"
        "1️⃣ Kanalga obuna bo'ling.\n"
        "2️⃣ «✅ Tekshirish» tugmasini bosing.\n\n"
        "Obuna tasdiqlansa, mukofot avtomatik beriladi "
        "va keyingi vazifa shu xabarning o'zida ochiladi."
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# CHECK TASK
# ============================================================

async def check_task(
    query,
    context,
    task_id,
):

    user_id = query.from_user.id

    # --------------------------------------------------------
    # TASKNI TOPISH
    # --------------------------------------------------------

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            channel_id,
            username,
            title,
            reward
        FROM channels
        WHERE id = ?
        AND active = 1
    """, (
        task_id,
    ))

    task = cur.fetchone()

    conn.close()

    if not task:

        await query.answer(
            "❌ Vazifa topilmadi.",
            show_alert=True,
        )

        return

    channel_id = task[0]
    username = task[1]
    title = task[2] or "Kanal"
    reward = float(
        task[3] or DEFAULT_TASK_REWARD
    )

    # Telegram API uchun:
    # ID bo'lsa ID,
    # bo'lmasa @username
    check_id = channel_id or username

    if not check_id:

        await query.answer(
            "❌ Kanal ID yoki username kiritilmagan.",
            show_alert=True,
        )

        return

    # --------------------------------------------------------
    # AVVAL BAJARILGANMI?
    # --------------------------------------------------------

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM completed_tasks
        WHERE user_id = ?
        AND channel_id = ?
    """, (
        user_id,
        str(task_id),
    ))

    already_done = cur.fetchone()

    conn.close()

    if already_done:

        await query.answer(
            "⚠️ Bu vazifani avval bajargansiz.",
            show_alert=True,
        )

        await show_task(query)

        return

    # --------------------------------------------------------
    # SUBSCRIPTION CHECK
    # --------------------------------------------------------

    try:

        member = await context.bot.get_chat_member(
            chat_id=check_id,
            user_id=user_id,
        )

        subscribed = False

        if member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):

            subscribed = True

        elif (
            member.status
            == ChatMemberStatus.RESTRICTED
            and member.is_member
        ):

            subscribed = True

    except Exception as e:

        logger.exception(
            "Task check error: %s",
            e,
        )

        await query.answer(
            "❌ Kanalni tekshirishda xatolik.\n\n"
            "Bot kanalga admin ekanini tekshiring.",
            show_alert=True,
        )

        return

    # --------------------------------------------------------
    # OBUNA YO'Q
    # --------------------------------------------------------

    if not subscribed:

        await query.answer(
            "❌ Avval kanalga obuna bo'ling!",
            show_alert=True,
        )

        return

    # --------------------------------------------------------
    # DATABASEGA SAQLASH
    # --------------------------------------------------------

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO completed_tasks
            (
                user_id,
                channel_id,
                completed_at
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            str(task_id),
            datetime.now().isoformat(),
        ))

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()

        await query.answer(
            "⚠️ Bu vazifani avval bajargansiz.",
            show_alert=True,
        )

        await show_task(query)

        return

    conn.close()

    # --------------------------------------------------------
    # STARS BERISH
    # --------------------------------------------------------

    change_balance(
        user_id,
        reward,
    )

    log_activity(
        user_id,
        f"Task completed: {title} +{reward} ⭐",
    )

    # --------------------------------------------------------
    # USERGA XABAR
    # --------------------------------------------------------

    await query.answer(
        f"🎉 +{reward:g} ⭐ berildi!",
        show_alert=True,
    )

    # --------------------------------------------------------
    # ENG MUHIM QISM:
    # SHU XABARNING O'ZIDA KEYINGI VAZIFA
    # --------------------------------------------------------

    await show_task(query)


# ============================================================
# BALANCE
# ============================================================

async def show_balance(query):

    balance = get_balance(
        query.from_user.id
    )

    text = (
        "💰 <b>Balans</b>\n\n"
        f"⭐ <b>{balance:.2f}</b> Stars"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_main(),
    )


# ============================================================
# REFERRAL
# ============================================================

async def show_referral(
    query,
    context,
):

    user_id = query.from_user.id

    bot = await context.bot.get_me()

    link = (
        f"https://t.me/"
        f"{bot.username}"
        f"?start={user_id}"
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE referred_by = ?
    """, (
        user_id,
    ))

    referrals = cur.fetchone()[0]

    conn.close()

    text = (
        "👥 <b>Referal</b>\n\n"
        f"👤 Referallar: <b>{referrals}</b>\n"
        f"⭐ Har bir referal: "
        f"<b>{REFERRAL_REWARD:g} ⭐</b>\n\n"
        "🔗 <b>Sizning referal havolangiz:</b>\n"
        f"<code>{link}</code>"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_main(),
    )


# ============================================================
# STATISTICS
# ============================================================

async def show_statistics(query):

    user_id = query.from_user.id

    balance = get_balance(
        user_id
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM completed_tasks
        WHERE user_id = ?
    """, (
        user_id,
    ))

    tasks = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE referred_by = ?
    """, (
        user_id,
    ))

    referrals = cur.fetchone()[0]

    conn.close()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"⭐ Balans: <b>{balance:.2f}</b>\n"
        f"✅ Bajarilgan vazifalar: <b>{tasks}</b>\n"
        f"👥 Referallar: <b>{referrals}</b>"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_main(),
    )


# ============================================================
# RULES
# ============================================================

async def show_rules(query):

    text = (
        "📜 <b>Qoidalar</b>\n\n"
        "1️⃣ Vazifalarni halol bajaring.\n\n"
        "2️⃣ Har bir vazifa faqat bir marta "
        "bajariladi.\n\n"
        "3️⃣ Soxta akkauntlardan foydalanmang.\n\n"
        "4️⃣ Botdagi xatolardan foydalanishga "
        "urinmang.\n\n"
        "5️⃣ Qoidalarni buzish hisob cheklanishiga "
        "olib kelishi mumkin."
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_main(),
    )


# ============================================================
# GIFTS
# ============================================================

async def show_gifts(query):

    balance = get_balance(
        query.from_user.id
    )

    text = (
        "🎁 <b>Gift olish</b>\n\n"
        f"💰 Balansingiz: <b>{balance:.2f} ⭐</b>\n\n"
        "Kerakli giftni tanlang:"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=gift_menu(),
    )


async def buy_gift(
    query,
    gift_name,
    price,
):

    user_id = query.from_user.id

    balance = get_balance(
        user_id
    )

    if balance < price:

        await query.answer(
            "❌ Balansingiz yetarli emas.",
            show_alert=True,
        )

        return

    # --------------------------------------------------------
    # BALANSDAN AYIRISH
    # --------------------------------------------------------

    change_balance(
        user_id,
        -price,
    )

    # --------------------------------------------------------
    # BUYURTMA
    # --------------------------------------------------------

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO gift_requests
        (
            user_id,
            gift_name,
            price,
            status,
            created_at
        )
        VALUES (?, ?, ?, 'pending', ?)
    """, (
        user_id,
        gift_name,
        price,
        datetime.now().isoformat(),
    ))

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        f"Gift {gift_name} -{price} ⭐",
    )

    await query.answer(
        f"🎉 {gift_name} buyurtma qilindi!",
        show_alert=True,
    )

    await show_gifts(query)


# ============================================================
# ADVERTISING
# ============================================================

pending_ads = {}


async def show_advertising(query):

    pending_ads[
        query.from_user.id
    ] = True

    text = (
        "📢 <b>Reklama</b>\n\n"
        "Reklamangiz matnini yuboring.\n\n"
        "Admin reklama so'rovingizni ko'rib chiqadi."
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_main(),
    )


# ============================================================
# ADMIN MENU
# ============================================================

def admin_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="admin_stats",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Foydalanuvchilar",
                callback_data="admin_users",
            )
        ],
        [
            InlineKeyboardButton(
                "📝 Loglar",
                callback_data="admin_logs",
            )
        ],
        [
            InlineKeyboardButton(
                "👮 Adminlar",
                callback_data="admin_admins",
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Vazifa kanallari",
                callback_data="admin_channels",
            )
        ],
        [
            InlineKeyboardButton(
                "🔒 Majburiy kanallar",
                callback_data="admin_mandatory",
            )
        ],
        [
            InlineKeyboardButton(
                "🎁 Giftlar",
                callback_data="admin_gifts",
            )
        ],
        [
            InlineKeyboardButton(
                "📣 Reklama",
                callback_data="admin_ads",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back",
            )
        ],
    ])


async def show_admin(query):

    if not is_admin(
        query.from_user.id
    ):

        await query.answer(
            "❌ Siz admin emassiz.",
            show_alert=True,
        )

        return

    await query.edit_message_text(
        "⚙️ <b>Admin panel</b>\n\n"
        "Kerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


# ============================================================
# ADMIN STATS
# ============================================================

async def admin_stats(query):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )
    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM users"
    )
    total_balance = float(
        cur.fetchone()[0] or 0
    )

    cur.execute(
        "SELECT COUNT(*) FROM gift_requests"
    )
    gifts = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM advertiser_requests"
    )
    ads = cur.fetchone()[0]

    conn.close()

    text = (
        "📊 <b>Admin statistikasi</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"⭐ Umumiy balans: <b>{total_balance:.2f}</b>\n"
        f"🎁 Gift buyurtmalari: <b>{gifts}</b>\n"
        f"📢 Reklama so'rovlari: <b>{ads}</b>"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN USERS
# ============================================================

async def admin_users(query):

    users = get_all_users()

    text = (
        f"👥 <b>Foydalanuvchilar: {len(users)}</b>\n\n"
    )

    for user_id, username, first_name, balance in users[:30]:

        name = (
            first_name
            or username
            or str(user_id)
        )

        text += (
            f"• {name}\n"
            f"  ID: <code>{user_id}</code>\n"
            f"  ⭐ {float(balance or 0):.2f}\n\n"
        )

    if not users:

        text += "Foydalanuvchilar yo'q."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN LOGS
# ============================================================

async def admin_logs(query):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            action,
            created_at
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 30
    """)

    logs = cur.fetchall()

    conn.close()

    text = "📝 <b>Oxirgi loglar</b>\n\n"

    for user_id, action, created_at in logs:

        text += (
            f"• <code>{user_id}</code>\n"
            f"  {action}\n\n"
        )

    if not logs:

        text += "Loglar mavjud emas."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN ADMINS
# ============================================================

async def admin_admins(query):

    admins = get_admins()

    text = "👮 <b>Adminlar</b>\n\n"

    for admin_id in admins:

        crown = (
            " 👑"
            if admin_id == OWNER_ID
            else ""
        )

        text += (
            f"• <code>{admin_id}</code>{crown}\n"
        )

    text += (
        "\n/addadmin USER_ID\n"
        "/removeadmin USER_ID"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN CHANNELS
# ============================================================

async def admin_channels(query):

    tasks = get_tasks()

    text = "📢 <b>Vazifa kanallari</b>\n\n"

    for task in tasks:

        task_id, channel_id, username, title, reward = task

        text += (
            f"🆔 <code>{task_id}</code>\n"
            f"📢 {title}\n"
            f"🔗 {username or '-'}\n"
            f"⭐ {float(reward or 0):g}\n\n"
        )

    text += (
        "/addtask — kanal qo'shish\n"
        "/deltask ID — o'chirish"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN MANDATORY
# ============================================================

async def admin_mandatory(query):

    channels = get_mandatory_channels()

    text = "🔒 <b>Majburiy kanallar</b>\n\n"

    for channel in channels:

        cid = channel[0]
        channel_id = channel[1]
        title = channel[2]
        username = channel[3]

        text += (
            f"🆔 <code>{cid}</code>\n"
            f"📢 {title}\n"
            f"ID: <code>{channel_id}</code>\n"
            f"Username: {username or '-'}\n\n"
        )

    if not channels:

        text += "Majburiy kanallar yo'q.\n\n"

    text += (
        "/addmandatory — qo'shish\n"
        "/delmandatory ID — o'chirish"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN GIFTS
# ============================================================

async def admin_gifts(query):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            gift_name,
            price,
            status,
            created_at
        FROM gift_requests
        ORDER BY id DESC
        LIMIT 30
    """)

    gifts = cur.fetchall()

    conn.close()

    text = "🎁 <b>Gift buyurtmalari</b>\n\n"

    for user_id, gift, price, status, created in gifts:

        text += (
            f"👤 <code>{user_id}</code>\n"
            f"🎁 {gift}\n"
            f"⭐ {price:g}\n"
            f"📌 {status}\n\n"
        )

    if not gifts:

        text += "Buyurtmalar mavjud emas."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN ADS
# ============================================================

async def admin_ads(query):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            text,
            status,
            created_at
        FROM advertiser_requests
        ORDER BY id DESC
        LIMIT 20
    """)

    ads = cur.fetchall()

    conn.close()

    text = "📣 <b>Reklama so'rovlari</b>\n\n"

    for user_id, ad_text, status, created in ads:

        text += (
            f"👤 <code>{user_id}</code>\n"
            f"📄 {ad_text}\n"
            f"📌 {status}\n\n"
        )

    if not ads:

        text += "Reklama so'rovlari mavjud emas."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin(),
    )


# ============================================================
# ADMIN STATES
# ============================================================

admin_states = {}


# ============================================================
# ADD ADMIN
# ============================================================

async def add_admin_command(
    update,
    context,
):

    user_id = update.effective_user.id

    if not is_owner(user_id):
        return

    if not context.args:

        await update.message.reply_text(
            "Foydalanish:\n"
            "/addadmin USER_ID"
        )

        return

    try:

        new_admin = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "USER_ID raqam bo'lishi kerak."
        )

        return

    add_admin(new_admin)

    await update.message.reply_text(
        f"✅ {new_admin} admin qilindi."
    )


# ============================================================
# REMOVE ADMIN
# ============================================================

async def remove_admin_command(
    update,
    context,
):

    user_id = update.effective_user.id

    if not is_owner(user_id):
        return

    if not context.args:

        await update.message.reply_text(
            "Foydalanish:\n"
            "/removeadmin USER_ID"
        )

        return

    try:

        remove_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "USER_ID raqam bo'lishi kerak."
        )

        return

    remove_admin(remove_id)

    await update.message.reply_text(
        f"✅ {remove_id} adminlikdan olib tashlandi."
    )


# ============================================================
# ADD TASK
# ============================================================

async def add_task_command(
    update,
    context,
):

    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    admin_states[user_id] = {
        "state": "task_username"
    }

    await update.message.reply_text(
        "📢 Kanal username'ini yuboring.\n\n"
        "Masalan:\n"
        "@Cossmoss_00"
    )


# ============================================================
# DELETE TASK
# ============================================================

async def delete_task_command(
    update,
    context,
):

    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    if not context.args:

        await update.message.reply_text(
            "/deltask ID"
        )

        return

    try:

        task_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "ID raqam bo'lishi kerak."
        )

        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM channels WHERE id = ?",
        (task_id,),
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Vazifa o'chirildi."
    )


# ============================================================
# ADD MANDATORY
# ============================================================

async def add_mandatory_command(
    update,
    context,
):

    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    admin_states[user_id] = {
        "state": "mandatory_id"
    }

    await update.message.reply_text(
        "🔒 Kanal ID sini yuboring.\n\n"
        "Masalan:\n"
        "-1004425654134"
    )


# ============================================================
# DELETE MANDATORY
# ============================================================

async def delete_mandatory_command(
    update,
    context,
):

    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    if not context.args:

        await update.message.reply_text(
            "/delmandatory ID"
        )

        return

    try:

        mandatory_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "ID raqam bo'lishi kerak."
        )

        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM mandatory_channels WHERE id = ?",
        (mandatory_id,),
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Majburiy kanal o'chirildi."
    )


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(
    update,
    context,
):

    user = update.effective_user
    user_id = user.id

    text = (
        update.message.text
        or ""
    ).strip()

    # ========================================================
    # ☰ TUGMA
    # ========================================================

    if text == "☰ Tugma":

        try:

            await update.message.delete()

        except Exception:

            pass

        await update.effective_chat.send_message(
            "⭐ <b>FrostStars</b>\n\n"
            "Kerakli bo'limni tanlang:",
            parse_mode="HTML",
            reply_markup=main_menu(user_id),
        )

        return

    # ========================================================
    # ADVERTISING
    # ========================================================

    if pending_ads.get(user_id):

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO advertiser_requests
            (
                user_id,
                text,
                status,
                created_at
            )
            VALUES (?, ?, 'pending', ?)
        """, (
            user_id,
            text,
            datetime.now().isoformat(),
        ))

        conn.commit()
        conn.close()

        pending_ads.pop(
            user_id,
            None,
        )

        log_activity(
            user_id,
            "Advertisement request",
        )

        await update.message.reply_text(
            "✅ Reklama so'rovingiz yuborildi.",
            reply_markup=bottom_keyboard(),
        )

        return

    # ========================================================
    # ADMIN STATE
    # ========================================================

    state_data = admin_states.get(
        user_id
    )

    if not state_data:
        return

    state = state_data.get(
        "state"
    )

    # ========================================================
    # TASK USERNAME
    # ========================================================

    if state == "task_username":

        admin_states[user_id] = {
            "state": "task_title",
            "username": text,
        }

        await update.message.reply_text(
            "📛 Kanal nomini yuboring."
        )

        return

    # ========================================================
    # TASK TITLE
    # ========================================================

    if state == "task_title":

        admin_states[user_id][
            "state"
        ] = "task_reward"

        admin_states[user_id][
            "title"
        ] = text

        await update.message.reply_text(
            "⭐ Mukofot miqdorini yuboring.\n\n"
            "Masalan:\n"
            "0.1"
        )

        return

    # ========================================================
    # TASK REWARD
    # ========================================================

    if state == "task_reward":

        try:

            reward = float(text)

        except ValueError:

            await update.message.reply_text(
                "❌ Masalan: 0.1"
            )

            return

        data = admin_states.pop(
            user_id
        )

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO channels
            (
                channel_id,
                username,
                title,
                reward,
                active
            )
            VALUES (?, ?, ?, ?, 1)
        """, (
            "",
            data["username"],
            data["title"],
            reward,
        ))

        conn.commit()
        conn.close()

        await update.message.reply_text(
            "✅ Vazifa kanali qo'shildi."
        )

        return

    # ========================================================
    # MANDATORY ID
    # ========================================================

    if state == "mandatory_id":

        admin_states[user_id] = {
            "state": "mandatory_title",
            "channel_id": text,
        }

        await update.message.reply_text(
            "📛 Kanal nomini yuboring."
        )

        return

    # ========================================================
    # MANDATORY TITLE
    # ========================================================

    if state == "mandatory_title":

        admin_states[user_id][
            "state"
        ] = "mandatory_username"

        admin_states[user_id][
            "title"
        ] = text

        await update.message.reply_text(
            "🔗 Kanal username yoki invite linkini yuboring.\n\n"
            "Masalan:\n"
            "@Cossmoss_00"
        )

        return

    # ========================================================
    # MANDATORY USERNAME
    # ========================================================

    if state == "mandatory_username":

        data = admin_states.pop(
            user_id
        )

        channel_id = data[
            "channel_id"
        ]

        title = data[
            "title"
        ]

        username = ""
        invite_link = ""

        if text.startswith(
            "https://t.me/"
        ):

            invite_link = text

        else:

            username = text

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT OR REPLACE INTO mandatory_channels
            (
                channel_id,
                title,
                username,
                invite_link,
                active
            )
            VALUES (?, ?, ?, ?, 1)
        """, (
            channel_id,
            title,
            username,
            invite_link,
        ))

        conn.commit()
        conn.close()

        await update.message.reply_text(
            "✅ Majburiy kanal qo'shildi."
        )

        return


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(
    update,
    context,
):

    query = update.callback_query

    data = query.data or ""

    user_id = query.from_user.id

    # ========================================================
    # MANDATORY CHECK
    # ========================================================

    if data == "checkmandatory":

        await query.answer()

        allowed = await check_mandatory(
            update,
            context,
        )

        if not allowed:

            await query.edit_message_text(
                mandatory_text(),
                parse_mode="HTML",
                reply_markup=mandatory_keyboard(),
            )

            return

        await query.edit_message_text(
            "✅ <b>Tekshiruv muvaffaqiyatli!</b>\n\n"
            "Endi botdan foydalanishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=main_menu(user_id),
        )

        return

    # ========================================================
    # BACK
    # ========================================================

    if data == "back":

        await query.answer()

        await query.edit_message_text(
            "⭐ <b>FrostStars</b>\n\n"
            "Kerakli bo'limni tanlang:",
            parse_mode="HTML",
            reply_markup=main_menu(user_id),
        )

        return

    # ========================================================
    # STARS
    # ========================================================

    if data == "stars":

        await query.answer()

        await show_stars(query)

        return

    # ========================================================
    # TASK
    # ========================================================

    if data == "task":

        await query.answer()

        await show_task(query)

        return

    # ========================================================
    # CHECK TASK
    # ========================================================

    if data.startswith(
        "checktask:"
    ):

        try:

            task_id = int(
                data.split(
                    ":",
                    1,
                )[1]
            )

        except ValueError:

            await query.answer(
                "❌ Vazifa ID xato.",
                show_alert=True,
            )

            return

        # check_task ichida success alert beriladi
        await check_task(
            query,
            context,
            task_id,
        )

        return

    # ========================================================
    # GIFT
    # ========================================================

    if data == "gift":

        await query.answer()

        await show_gifts(query)

        return

    # ========================================================
    # BUY GIFT
    # ========================================================

    if data.startswith(
        "buygift:"
    ):

        parts = data.split(":")

        if len(parts) != 3:

            await query.answer(
                "❌ Gift ma'lumotida xato.",
                show_alert=True,
            )

            return

        gift_name = parts[1].replace(
            "_",
            " ",
        )

        try:

            price = float(
                parts[2]
            )

        except ValueError:

            await query.answer(
                "❌ Narx xato.",
                show_alert=True,
            )

            return

        await buy_gift(
            query,
            gift_name,
            price,
        )

        return

    # ========================================================
    # REFERRAL
    # ========================================================

    if data == "referral":

        await query.answer()

        await show_referral(
            query,
            context,
        )

        return

    # ========================================================
    # BALANCE
    # ========================================================

    if data == "balance":

        await query.answer()

        await show_balance(query)

        return

    # ========================================================
    # STATISTICS
    # ========================================================

    if data == "statistics":

        await query.answer()

        await show_statistics(query)

        return

    # ========================================================
    # RULES
    # ========================================================

    if data == "rules":

        await query.answer()

        await show_rules(query)

        return

    # ========================================================
    # ADVERTISING
    # ========================================================

    if data == "advertising":

        await query.answer()

        await show_advertising(query)

        return

    # ========================================================
    # ADMIN
    # ========================================================

    if data == "admin":

        await query.answer()

        await show_admin(query)

        return

    # ========================================================
    # ADMIN STATS
    # ========================================================

    if data == "admin_stats":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_stats(query)

        return

    # ========================================================
    # ADMIN USERS
    # ========================================================

    if data == "admin_users":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_users(query)

        return

    # ========================================================
    # ADMIN LOGS
    # ========================================================

    if data == "admin_logs":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_logs(query)

        return

    # ========================================================
    # ADMIN ADMINS
    # ========================================================

    if data == "admin_admins":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_admins(query)

        return

    # ========================================================
    # ADMIN TASK CHANNELS
    # ========================================================

    if data == "admin_channels":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_channels(query)

        return

    # ========================================================
    # ADMIN MANDATORY
    # ========================================================

    if data == "admin_mandatory":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_mandatory(query)

        return

    # ========================================================
    # ADMIN GIFTS
    # ========================================================

    if data == "admin_gifts":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_gifts(query)

        return

    # ========================================================
    # ADMIN ADS
    # ========================================================

    if data == "admin_ads":

        await query.answer()

        if not is_admin(user_id):
            return

        await admin_ads(query)

        return


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context,
):

    logger.exception(
        "Unhandled exception:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    init_db()

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # --------------------------------------------------------
    # ADMIN COMMANDS
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "addadmin",
            add_admin_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "removeadmin",
            remove_admin_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "addtask",
            add_task_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "deltask",
            delete_task_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "addmandatory",
            add_mandatory_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "delmandatory",
            delete_mandatory_command,
        )
    )

    # --------------------------------------------------------
    # INLINE CALLBACKS
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "========================================"
    )

    logger.info(
        "FROSTSTARS BOT IS RUNNING!"
    )

    logger.info(
        "========================================"
    )

    application.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
