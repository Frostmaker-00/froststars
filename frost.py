import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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


# =========================================================
# CONFIG
# =========================================================

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


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("FrostStars")


# =========================================================
# DATABASE
# =========================================================

def db():
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
    conn = db()
    cur = conn.cursor()

    # USERS
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

    # TASKS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id TEXT,
            completed_at TEXT,
            UNIQUE(user_id, channel_id)
        )
    """)

    # GIFTS
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

    # CHANNELS
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

    # ADMINS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)

    # LOGS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            created_at TEXT
        )
    """)

    # ADVERTISING
    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    # MANDATORY CHANNELS
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

    # MIGRATION
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

    # OWNER
    cur.execute(
        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
        (OWNER_ID,),
    )

    # DEFAULT TASK CHANNELS
    cur.execute("SELECT COUNT(*) FROM channels")
    count = cur.fetchone()[0]

    if count == 0:
        cur.execute("""
            INSERT INTO channels
            (channel_id, username, title, reward, active)
            VALUES (?, ?, ?, ?, 1)
        """, (
            "-1004425654134",
            "@Cossmoss_00",
            "Cosmos",
            DEFAULT_TASK_REWARD,
        ))

        cur.execute("""
            INSERT INTO channels
            (channel_id, username, title, reward, active)
            VALUES (?, ?, ?, ?, 1)
        """, (
            "",
            "@PromptLab_UZ",
            "PromptLab UZ",
            DEFAULT_TASK_REWARD,
        ))

    conn.commit()
    conn.close()


# =========================================================
# USERS
# =========================================================

def add_user(user, referred_by=None):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user.id,),
    )

    exists = cur.fetchone()

    if not exists:
        cur.execute("""
            INSERT INTO users
            (user_id, username, first_name, balance, referred_by, created_at)
            VALUES (?, ?, ?, 0, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            referred_by,
            datetime.now().isoformat(),
        ))

    else:
        cur.execute("""
            UPDATE users
            SET username = ?, first_name = ?
            WHERE user_id = ?
        """, (
            user.username or "",
            user.first_name or "",
            user.id,
        ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
    )

    result = cur.fetchone()

    conn.close()

    return result


def change_balance(user_id, amount):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (amount, user_id))

    conn.commit()
    conn.close()


def get_balance(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,),
    )

    result = cur.fetchone()

    conn.close()

    return result[0] if result else 0


def get_all_users():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, username, first_name, balance
        FROM users
        ORDER BY user_id DESC
    """)

    result = cur.fetchall()

    conn.close()

    return result


def get_user_count():
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    result = cur.fetchone()[0]

    conn.close()

    return result


# =========================================================
# ADMINS
# =========================================================

def is_admin(user_id):
    conn = db()
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
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT user_id FROM admins")
    result = cur.fetchall()

    conn.close()

    return [x[0] for x in result]


def add_admin(user_id):
    conn = db()
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

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM admins WHERE user_id = ?",
        (user_id,),
    )

    conn.commit()
    conn.close()


# =========================================================
# LOGS
# =========================================================

def log_activity(user_id, action):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO activity_logs
        (user_id, action, created_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        action,
        datetime.now().isoformat(),
    ))

    conn.commit()
    conn.close()


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard(user_id):
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


def back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back",
            )
        ]
    ])


def stars_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⭐ Vazifa",
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
                "🔙 Orqaga",
                callback_data="back",
            )
        ],
    ])


def gift_keyboard():
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
                callback_data="buygift:Teddy Bear:10",
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
                "🔙 Orqaga",
                callback_data="back",
            )
        ],
    ])


# =========================================================
# MANDATORY CHANNELS
# =========================================================

def get_mandatory_channels():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, channel_id, title, username, invite_link
        FROM mandatory_channels
        WHERE active = 1
        ORDER BY id
    """)

    result = cur.fetchall()

    conn.close()

    return result


async def check_mandatory(update, context):
    user_id = update.effective_user.id

    channels = get_mandatory_channels()

    if not channels:
        return True

    for channel in channels:
        channel_id = channel[1]

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
                member.status == ChatMemberStatus.RESTRICTED
                and member.is_member
            ):
                continue

            return False

        except Exception as e:
            logger.warning(
                "Mandatory channel check error: %s",
                e,
            )

    return True


def mandatory_message():
    channels = get_mandatory_channels()

    buttons = []

    for channel in channels:
        title = channel[2] or "Kanal"

        link = channel[4]

        if not link and channel[3]:
            username = channel[3]

            if username.startswith("@"):
                username = username[1:]

            link = f"https://t.me/{username}"

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

    return (
        "🔒 Botdan foydalanish uchun quyidagi kanallarga "
        "obuna bo'ling.\n\n"
        "Obuna bo'lgach, «Tekshirish» tugmasini bosing.",
        InlineKeyboardMarkup(buttons),
    )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    referral_id = None

    if context.args:
        try:
            referral_id = int(context.args[0])

            if referral_id == user.id:
                referral_id = None

        except:
            referral_id = None

    add_user(user, referral_id)

    # Referral reward
    if referral_id:
        old_user = get_user(user.id)

        if old_user and old_user[4] == referral_id:
            # User already has this referrer
            pass

        else:
            conn = db()
            cur = conn.cursor()

            cur.execute("""
                UPDATE users
                SET referred_by = ?
                WHERE user_id = ?
            """, (
                referral_id,
                user.id,
            ))

            conn.commit()
            conn.close()

            if get_user(referral_id):
                change_balance(
                    referral_id,
                    REFERRAL_REWARD,
                )

                log_activity(
                    referral_id,
                    f"Referral: {user.id}",
                )

    log_activity(user.id, "/start")

    if not is_admin(user.id):
        allowed = await check_mandatory(update, context)

        if not allowed:
            text, markup = mandatory_message()

            await update.message.reply_text(
                text,
                reply_markup=markup,
            )

            return

    text = (
        "⭐ <b>FrostStars</b>\n\n"
        f"Salom, <b>{user.first_name}</b>!\n\n"
        "Kerakli bo'limni tanlang:"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard(user.id),
    )


# =========================================================
# STARS
# =========================================================

def get_task_channels():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, channel_id, username, title, reward
        FROM channels
        WHERE active = 1
        ORDER BY id
    """)

    result = cur.fetchall()

    conn.close()

    return result


async def show_stars(query):
    text = (
        "⭐ <b>Stars ishlash</b>\n\n"
        "Kanallarga obuna bo'lib Stars ishlashingiz mumkin.\n\n"
        f"Har bir vazifa uchun mukofot: "
        f"<b>{DEFAULT_TASK_REWARD} ⭐</b>"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=stars_keyboard(),
    )


async def show_task(query, context):
    tasks = get_task_channels()

    if not tasks:
        await query.edit_message_text(
            "⭐ Hozircha vazifalar mavjud emas.",
            reply_markup=back_keyboard(),
        )
        return

    for task in tasks:
        task_id, channel_id, username, title, reward = task

        link = None

        if username:
            u = username

            if u.startswith("@"):
                u = u[1:]

            link = f"https://t.me/{u}"

        buttons = []

        if link:
            buttons.append([
                InlineKeyboardButton(
                    f"📢 {title}",
                    url=link,
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                f"✅ Tekshirish • +{reward} ⭐",
                callback_data=f"checktask:{task_id}",
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="stars",
            )
        ])

        await query.edit_message_text(
            (
                "⭐ <b>Vazifa</b>\n\n"
                f"📢 <b>{title}</b>\n"
                f"🎁 Mukofot: <b>{reward} ⭐</b>\n\n"
                "Kanalga obuna bo'ling va "
                "«Tekshirish» tugmasini bosing."
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

        break


async def check_task(query, context, task_id):
    user_id = query.from_user.id

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT channel_id, username, title, reward
        FROM channels
        WHERE id = ? AND active = 1
    """, (task_id,))

    task = cur.fetchone()

    conn.close()

    if not task:
        await query.answer(
            "Vazifa topilmadi.",
            show_alert=True,
        )
        return

    channel_id, username, title, reward = task

    if not channel_id and username:
        channel_id = username

    try:
        member = await context.bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id,
        )

        subscribed = (
            member.status
            in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            )
        )

        if (
            member.status == ChatMemberStatus.RESTRICTED
            and member.is_member
        ):
            subscribed = True

    except Exception as e:
        logger.error(
            "Task subscription check error: %s",
            e,
        )

        await query.answer(
            "Kanalni tekshirishda xatolik. "
            "Bot kanalga admin qilinganini tekshiring.",
            show_alert=True,
        )

        return

    if not subscribed:
        await query.answer(
            "❌ Avval kanalga obuna bo'ling.",
            show_alert=True,
        )
        return

    conn = db()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO completed_tasks
            (user_id, channel_id, completed_at)
            VALUES (?, ?, ?)
        """, (
            user_id,
            str(channel_id),
            datetime.now().isoformat(),
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()

        await query.answer(
            "⚠️ Bu vazifani avval bajargansiz.",
            show_alert=True,
        )

        return

    conn.close()

    change_balance(user_id, reward)

    log_activity(
        user_id,
        f"Task completed: {title} +{reward}",
    )

    await query.answer(
        f"🎉 +{reward} ⭐ qo'shildi!",
        show_alert=True,
    )

    await show_stars(query)


# =========================================================
# BALANCE
# =========================================================

async def show_balance(query):
    balance = get_balance(query.from_user.id)

    text = (
        "💰 <b>Balansingiz</b>\n\n"
        f"⭐ <b>{balance:.2f}</b> Stars"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


# =========================================================
# REFERRAL
# =========================================================

async def show_referral(query, context):
    user_id = query.from_user.id

    me = await context.bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start={user_id}"
    )

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users WHERE referred_by = ?",
        (user_id,),
    )

    count = cur.fetchone()[0]

    conn.close()

    text = (
        "👥 <b>Referal</b>\n\n"
        f"Taklif qilganlaringiz: <b>{count}</b>\n"
        f"Har bir referal: <b>{REFERRAL_REWARD} ⭐</b>\n\n"
        "🔗 Sizning referal havolangiz:\n"
        f"<code>{link}</code>"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


# =========================================================
# STATISTICS
# =========================================================

async def show_statistics(query):
    user_id = query.from_user.id

    balance = get_balance(user_id)

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM completed_tasks WHERE user_id = ?",
        (user_id,),
    )

    tasks = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM users WHERE referred_by = ?",
        (user_id,),
    )

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
        reply_markup=back_keyboard(),
    )


# =========================================================
# RULES
# =========================================================

async def show_rules(query):
    text = (
        "📜 <b>Qoidalar</b>\n\n"
        "1️⃣ Vazifalarni halol bajaring.\n"
        "2️⃣ Bir vazifadan faqat bir marta foydalanish mumkin.\n"
        "3️⃣ Soxta akkauntlardan foydalanmang.\n"
        "4️⃣ Botdagi texnik xatolardan foydalanishga "
        "urinmang.\n"
        "5️⃣ Qoidalarni buzish hisob bloklanishiga olib "
        "kelishi mumkin."
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


# =========================================================
# GIFTS
# =========================================================

async def show_gifts(query):
    text = (
        "🎁 <b>Gift olish</b>\n\n"
        "Balansingizdagi Stars orqali gift tanlang:"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=gift_keyboard(),
    )


async def buy_gift(query, gift_name, price):
    user_id = query.from_user.id

    balance = get_balance(user_id)

    if balance < price:
        await query.answer(
            "❌ Balansingiz yetarli emas.",
            show_alert=True,
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO gift_requests
        (user_id, gift_name, price, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
    """, (
        user_id,
        gift_name,
        price,
        datetime.now().isoformat(),
    ))

    conn.commit()
    conn.close()

    change_balance(user_id, -price)

    log_activity(
        user_id,
        f"Gift requested: {gift_name} {price}",
    )

    await query.answer(
        "🎉 Buyurtmangiz qabul qilindi!",
        show_alert=True,
    )

    await show_gifts(query)


# =========================================================
# ADVERTISING
# =========================================================

async def show_advertising(query):
    text = (
        "📢 <b>Reklama</b>\n\n"
        "Reklama berish uchun quyidagi xabarda "
        "reklamangiz matnini yuboring.\n\n"
        "Masalan:\n"
        "• Kanal reklama\n"
        "• Bot reklama\n"
        "• Mahsulot reklama"
    )

    context_user_state = query.from_user.id

    # State
    pending_ads[context_user_state] = True

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


# =========================================================
# ADMIN PANEL
# =========================================================

def admin_keyboard():
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
                "🎁 Gift buyurtmalari",
                callback_data="admin_gifts",
            )
        ],
        [
            InlineKeyboardButton(
                "📣 Reklamalar",
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
    if not is_admin(query.from_user.id):
        await query.answer(
            "❌ Siz admin emassiz.",
            show_alert=True,
        )
        return

    await query.edit_message_text(
        "⚙️ <b>Admin panel</b>\n\nKerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


async def admin_stats(query):
    users = get_user_count()

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
    total_balance = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM gift_requests")
    gifts = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM advertiser_requests")
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
        reply_markup=back_admin_keyboard(),
    )


def back_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Admin panel",
                callback_data="admin",
            )
        ]
    ])


async def admin_users(query):
    users = get_all_users()

    text = f"👥 <b>Foydalanuvchilar: {len(users)}</b>\n\n"

    for user in users[:30]:
        user_id, username, first_name, balance = user

        name = first_name or username or str(user_id)

        text += (
            f"• {name} — "
            f"<code>{user_id}</code> — "
            f"{balance:.2f} ⭐\n"
        )

    if len(users) > 30:
        text += "\n... va yana foydalanuvchilar bor."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin_keyboard(),
    )


async def admin_logs(query):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, action, created_at
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 30
    """)

    logs = cur.fetchall()

    conn.close()

    text = "📝 <b>Oxirgi loglar</b>\n\n"

    for user_id, action, created_at in logs:
        text += (
            f"• <code>{user_id}</code> — "
            f"{action}\n"
        )

    if not logs:
        text += "Loglar mavjud emas."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin_keyboard(),
    )


async def admin_admins(query):
    admins = get_admins()

    text = "👮 <b>Adminlar</b>\n\n"

    for admin_id in admins:
        owner = " 👑" if admin_id == OWNER_ID else ""

        text += (
            f"• <code>{admin_id}</code>{owner}\n"
        )

    text += (
        "\nAdmin qo'shish:\n"
        "<code>/addadmin USER_ID</code>\n\n"
        "Admin o'chirish:\n"
        "<code>/removeadmin USER_ID</code>"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin_keyboard(),
    )


async def admin_channels(query):
    channels = get_task_channels()

    text = "📢 <b>Vazifa kanallari</b>\n\n"

    for task in channels:
        task_id, channel_id, username, title, reward = task

        text += (
            f"🆔 <code>{task_id}</code>\n"
            f"📢 {title}\n"
            f"🔗 {username}\n"
            f"⭐ {reward}\n\n"
        )

    text += (
        "/addtask — kanal qo'shish\n"
        "/deltask ID — kanal o'chirish"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin_keyboard(),
    )


async def admin_mandatory(query):
    channels = get_mandatory_channels()

    text = "🔒 <b>Majburiy kanallar</b>\n\n"

    for channel in channels:
        cid, channel_id, title, username, invite = channel

        text += (
            f"🆔 <code>{cid}</code>\n"
            f"📢 {title}\n"
            f"ID: <code>{channel_id}</code>\n"
            f"Username: {username or '-'}\n\n"
        )

    text += (
        "/addmandatory — qo'shish\n"
        "/delmandatory ID — o'chirish"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin_keyboard(),
    )


async def admin_gifts(query):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, gift_name, price, status, created_at
        FROM gift_requests
        ORDER BY id DESC
        LIMIT 30
    """)

    gifts = cur.fetchall()

    conn.close()

    text = "🎁 <b>Gift buyurtmalari</b>\n\n"

    for user_id, gift, price, status, created in gifts:
        text += (
            f"• <code>{user_id}</code> — "
            f"{gift} — {price} ⭐ — {status}\n"
        )

    if not gifts:
        text += "Buyurtmalar yo'q."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin_keyboard(),
    )


async def admin_ads(query):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, text, status, created_at
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
            f"Status: {status}\n\n"
        )

    if not ads:
        text += "Reklama so'rovlari yo'q."

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_admin_keyboard(),
    )


# =========================================================
# ADMIN COMMANDS
# =========================================================

async def add_admin_command(update, context):
    user_id = update.effective_user.id

    if not is_owner(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n/addadmin USER_ID"
        )
        return

    try:
        new_admin = int(context.args[0])
    except:
        await update.message.reply_text(
            "USER_ID raqam bo'lishi kerak."
        )
        return

    add_admin(new_admin)

    await update.message.reply_text(
        f"✅ {new_admin} admin qilindi."
    )


async def remove_admin_command(update, context):
    user_id = update.effective_user.id

    if not is_owner(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n/removeadmin USER_ID"
        )
        return

    try:
        remove_id = int(context.args[0])
    except:
        await update.message.reply_text(
            "USER_ID raqam bo'lishi kerak."
        )
        return

    remove_admin(remove_id)

    await update.message.reply_text(
        f"✅ {remove_id} adminlikdan olib tashlandi."
    )


# =========================================================
# ADMIN TASK ADD
# =========================================================

admin_states = {}
pending_ads = {}


async def add_task_command(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    admin_states[user_id] = {
        "state": "task_channel"
    }

    await update.message.reply_text(
        "📢 Vazifa kanali username'ini yuboring.\n\n"
        "Masalan:\n"
        "@Cossmoss_00"
    )


async def delete_task_command(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n/deltask ID"
        )
        return

    try:
        task_id = int(context.args[0])
    except:
        await update.message.reply_text(
            "ID raqam bo'lishi kerak."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM channels WHERE id = ?",
        (task_id,),
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Vazifa kanali o'chirildi."
    )


# =========================================================
# MANDATORY ADD
# =========================================================

async def add_mandatory_command(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    admin_states[user_id] = {
        "state": "mandatory_id"
    }

    await update.message.reply_text(
        "🔒 Majburiy kanal ID sini yuboring.\n\n"
        "Masalan:\n"
        "-1004425654134"
    )


async def delete_mandatory_command(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n/delmandatory ID"
        )
        return

    try:
        channel_id = int(context.args[0])
    except:
        await update.message.reply_text(
            "ID raqam bo'lishi kerak."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM mandatory_channels WHERE id = ?",
        (channel_id,),
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Majburiy kanal o'chirildi."
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(update, context):
    user = update.effective_user
    user_id = user.id

    text = update.message.text.strip()

    # ADVERTISEMENT
    if pending_ads.get(user_id):

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO advertiser_requests
            (user_id, text, status, created_at)
            VALUES (?, ?, 'pending', ?)
        """, (
            user_id,
            text,
            datetime.now().isoformat(),
        ))

        conn.commit()
        conn.close()

        pending_ads.pop(user_id, None)

        log_activity(
            user_id,
            "Advertising request",
        )

        await update.message.reply_text(
            "✅ Reklama so'rovingiz adminlarga yuborildi."
        )

        return

    # ADMIN STATES
    state_data = admin_states.get(user_id)

    if not state_data:
        return

    state = state_data.get("state")

    # TASK CHANNEL
    if state == "task_channel":

        admin_states[user_id] = {
            "state": "task_title",
            "username": text,
        }

        await update.message.reply_text(
            "📛 Kanal nomini yuboring."
        )

        return

    if state == "task_title":

        admin_states[user_id]["state"] = "task_reward"
        admin_states[user_id]["title"] = text

        await update.message.reply_text(
            "⭐ Mukofot miqdorini yuboring.\n\n"
            "Masalan: 0.1"
        )

        return

    if state == "task_reward":

        try:
            reward = float(text)
        except:
            await update.message.reply_text(
                "❌ Masalan: 0.1"
            )
            return

        data = admin_states.pop(user_id)

        username = data["username"]
        title = data["title"]

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO channels
            (channel_id, username, title, reward, active)
            VALUES (?, ?, ?, ?, 1)
        """, (
            "",
            username,
            title,
            reward,
        ))

        conn.commit()
        conn.close()

        await update.message.reply_text(
            "✅ Vazifa kanali qo'shildi."
        )

        return

    # MANDATORY CHANNEL
    if state == "mandatory_id":

        admin_states[user_id] = {
            "state": "mandatory_title",
            "channel_id": text,
        }

        await update.message.reply_text(
            "📛 Kanal nomini yuboring."
        )

        return

    if state == "mandatory_title":

        admin_states[user_id]["state"] = "mandatory_username"
        admin_states[user_id]["title"] = text

        await update.message.reply_text(
            "🔗 Kanal username yoki invite linkini yuboring.\n\n"
            "Masalan:\n"
            "@Cossmoss_00"
        )

        return

    if state == "mandatory_username":

        data = admin_states.pop(user_id)

        channel_id = data["channel_id"]
        title = data["title"]

        username = text
        invite_link = ""

        if text.startswith("https://t.me/"):
            invite_link = text

        elif text.startswith("@"):
            username = text

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            INSERT OR REPLACE INTO mandatory_channels
            (channel_id, title, username, invite_link, active)
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


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    await query.answer()

    data = query.data

    user_id = query.from_user.id

    # MANDATORY
    if data == "checkmandatory":

        allowed = await check_mandatory(update, context)

        if not allowed:
            text, markup = mandatory_message()

            await query.edit_message_text(
                text,
                reply_markup=markup,
            )

            return

        await query.edit_message_text(
            "✅ Obuna tekshirildi!\n\n"
            "Endi botdan foydalanishingiz mumkin.",
            reply_markup=main_keyboard(user_id),
        )

        return

    # BACK
    if data == "back":

        await query.edit_message_text(
            "⭐ <b>FrostStars</b>\n\n"
            "Kerakli bo'limni tanlang:",
            parse_mode="HTML",
            reply_markup=main_keyboard(user_id),
        )

        return

    # STARS
    if data == "stars":

        await show_stars(query)

        return

    # TASK
    if data == "task":

        await show_task(query, context)

        return

    # CHECK TASK
    if data.startswith("checktask:"):

        task_id = data.split(":", 1)[1]

        try:
            task_id = int(task_id)
        except:
            await query.answer(
                "Xato vazifa ID.",
                show_alert=True,
            )
            return

        await check_task(
            query,
            context,
            task_id,
        )

        return

    # BALANCE
    if data == "balance":

        await show_balance(query)

        return

    # REFERRAL
    if data == "referral":

        await show_referral(
            query,
            context,
        )

        return

    # STATISTICS
    if data == "statistics":

        await show_statistics(query)

        return

    # RULES
    if data == "rules":

        await show_rules(query)

        return

    # GIFT
    if data == "gift":

        await show_gifts(query)

        return

    # BUY GIFT
    if data.startswith("buygift:"):

        parts = data.split(":")

        if len(parts) != 3:
            return

        gift_name = parts[1]

        try:
            price = float(parts[2])
        except:
            return

        await buy_gift(
            query,
            gift_name,
            price,
        )

        return

    # ADVERTISING
    if data == "advertising":

        await show_advertising(query)

        return

    # ADMIN
    if data == "admin":

        await show_admin(query)

        return

    if data == "admin_stats":

        await admin_stats(query)

        return

    if data == "admin_users":

        await admin_users(query)

        return

    if data == "admin_logs":

        await admin_logs(query)

        return

    if data == "admin_admins":

        await admin_admins(query)

        return

    if data == "admin_channels":

        await admin_channels(query)

        return

    if data == "admin_mandatory":

        await admin_mandatory(query)

        return

    if data == "admin_gifts":

        await admin_gifts(query)

        return

    if data == "admin_ads":

        await admin_ads(query)

        return


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update, context):
    logger.exception(
        "Unhandled exception:",
        exc_info=context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # COMMANDS
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

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

    # CALLBACKS
    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # TEXT
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    # ERRORS
    application.add_error_handler(
        error_handler
    )

    logger.info(
        "FROSTSTARS BOT IS RUNNING!"
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
    
