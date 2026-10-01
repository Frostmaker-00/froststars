import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
        "BOT_TOKEN topilmadi. FadeHost Environment Variables bo'limiga "
        "BOT_TOKEN qo'shing."
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

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def ensure_columns(cur, table, columns):
    """
    Eski database uchun yetishmayotgan columnlarni qo'shadi.
    """
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}

    for column, definition in columns.items():
        if column not in existing:
            try:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )
                logger.info(
                    "Database migration: %s.%s qo'shildi",
                    table,
                    column,
                )
            except Exception as e:
                logger.warning(
                    "Migration xatosi %s.%s: %s",
                    table,
                    column,
                    e,
                )


def init_db():
    conn = db()
    cur = conn.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            balance REAL DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            created_at TEXT
        )
        """
    )

    ensure_columns(
        cur,
        "users",
        {
            "username": "TEXT DEFAULT ''",
            "first_name": "TEXT DEFAULT ''",
            "balance": "REAL DEFAULT 0",
            "referral_count": "INTEGER DEFAULT 0",
            "referred_by": "INTEGER DEFAULT NULL",
            "created_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # COMPLETED TASKS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            created_at TEXT,
            UNIQUE(user_id, task_id)
        )
        """
    )

    ensure_columns(
        cur,
        "completed_tasks",
        {
            "user_id": "INTEGER",
            "task_id": "INTEGER",
            "created_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # GIFTS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_name TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    ensure_columns(
        cur,
        "gift_requests",
        {
            "user_id": "INTEGER",
            "gift_name": "TEXT",
            "price": "REAL DEFAULT 0",
            "status": "TEXT DEFAULT 'pending'",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # TASK CHANNELS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
        """
    )

    ensure_columns(
        cur,
        "channels",
        {
            "username": "TEXT",
            "title": "TEXT",
            "reward": "REAL DEFAULT 0.1",
            "created_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # ADMINS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT
        )
        """
    )

    ensure_columns(
        cur,
        "admins",
        {
            "added_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # ACTIVITY LOGS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT
        )
        """
    )

    ensure_columns(
        cur,
        "activity_logs",
        {
            "user_id": "INTEGER",
            "action": "TEXT",
            "details": "TEXT",
            "created_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # ADVERTISING
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
        """
    )

    ensure_columns(
        cur,
        "advertiser_requests",
        {
            "user_id": "INTEGER",
            "text": "TEXT",
            "status": "TEXT DEFAULT 'pending'",
            "created_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # MANDATORY CHANNELS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            username TEXT,
            title TEXT,
            invite_link TEXT,
            created_at TEXT
        )
        """
    )

    ensure_columns(
        cur,
        "mandatory_channels",
        {
            "channel_id": "TEXT",
            "username": "TEXT",
            "title": "TEXT",
            "invite_link": "TEXT",
            "created_at": "TEXT",
        },
    )

    # --------------------------------------------------------
    # OWNER
    # --------------------------------------------------------

    cur.execute(
        """
        INSERT OR IGNORE INTO admins (user_id, added_at)
        VALUES (?, ?)
        """,
        (OWNER_ID, now()),
    )

    # --------------------------------------------------------
    # DEFAULT TASK CHANNELS
    # --------------------------------------------------------

    cur.execute("SELECT COUNT(*) AS count FROM channels")
    count = cur.fetchone()["count"]

    if count == 0:
        cur.execute(
            """
            INSERT INTO channels
            (username, title, reward, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "Cossmoss_00",
                "Cossmoss",
                DEFAULT_TASK_REWARD,
                now(),
            ),
        )

        cur.execute(
            """
            INSERT INTO channels
            (username, title, reward, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "PromptLab_UZ",
                "PromptLab UZ",
                DEFAULT_TASK_REWARD,
                now(),
            ),
        )

    conn.commit()
    conn.close()

    logger.info("Database tayyor: %s", DB_PATH)


# ============================================================
# USER FUNCTIONS
# ============================================================

def add_user(user):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user.id,),
    )

    exists = cur.fetchone()

    if not exists:
        cur.execute(
            """
            INSERT INTO users
            (
                user_id,
                username,
                first_name,
                balance,
                referral_count,
                referred_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.username or "",
                user.first_name or "",
                0,
                0,
                None,
                now(),
            ),
        )
    else:
        cur.execute(
            """
            UPDATE users
            SET username = ?,
                first_name = ?
            WHERE user_id = ?
            """,
            (
                user.username or "",
                user.first_name or "",
                user.id,
            ),
        )

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

    cur.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
        """,
        (amount, user_id),
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM users
        ORDER BY created_at DESC
        """
    )

    result = cur.fetchall()
    conn.close()

    return result


def get_user_count():
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS count FROM users")
    result = cur.fetchone()["count"]

    conn.close()

    return result


# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def is_admin(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM admins WHERE user_id = ?",
        (user_id,),
    )

    result = cur.fetchone()
    conn.close()

    return result is not None


def is_owner(user_id):
    return user_id == OWNER_ID


def get_admins():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM admins
        ORDER BY added_at ASC
        """
    )

    result = cur.fetchall()
    conn.close()

    return result


def add_admin(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO admins
        (user_id, added_at)
        VALUES (?, ?)
        """,
        (user_id, now()),
    )

    conn.commit()
    conn.close()


def remove_admin(user_id):
    if user_id == OWNER_ID:
        return False

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM admins WHERE user_id = ?",
        (user_id,),
    )

    deleted = cur.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


# ============================================================
# LOGGING TO DATABASE
# ============================================================

def log_activity(user_id, action, details=""):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO activity_logs
        (user_id, action, details, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            action,
            details,
            now(),
        ),
    )

    conn.commit()
    conn.close()


# ============================================================
# USER MENU
# ============================================================

def user_menu(user_id):
    keyboard = [
        [
            InlineKeyboardButton(
                "⭐ Stars",
                callback_data="stars",
            ),
            InlineKeyboardButton(
                "🎁 Gift",
                callback_data="gift",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Referral",
                callback_data="referral",
            ),
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="statistics",
            ),
        ],
        [
            InlineKeyboardButton(
                "📜 Rules",
                callback_data="rules",
            ),
            InlineKeyboardButton(
                "📢 Advertising",
                callback_data="advertising",
            ),
        ],
    ]

    if is_admin(user_id):
        keyboard.append(
            [
                InlineKeyboardButton(
                    "👑 Admin Panel",
                    callback_data="admin_panel",
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


def admin_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="admin_stats",
            ),
            InlineKeyboardButton(
                "👥 Users",
                callback_data="admin_users",
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 Logs",
                callback_data="admin_logs",
            ),
            InlineKeyboardButton(
                "👑 Admins",
                callback_data="admin_admins",
            ),
        ],
        [
            InlineKeyboardButton(
                "📢 Task Channels",
                callback_data="admin_channels",
            ),
            InlineKeyboardButton(
                "🔐 Mandatory",
                callback_data="admin_mandatory",
            ),
        ],
        [
            InlineKeyboardButton(
                "🎁 Gifts",
                callback_data="admin_gifts",
            ),
            InlineKeyboardButton(
                "📣 Advertising",
                callback_data="admin_ads",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# MANDATORY CHANNELS
# ============================================================

def get_mandatory_channels():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM mandatory_channels
        ORDER BY id ASC
        """
    )

    result = cur.fetchall()
    conn.close()

    return result


async def check_mandatory(user_id, bot):
    channels = get_mandatory_channels()

    if not channels:
        return True

    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel["channel_id"],
                user_id=user_id,
            )

            if member.status in (
                "member",
                "administrator",
                "creator",
            ):
                continue

            if (
                member.status == "restricted"
                and getattr(member, "is_member", False)
            ):
                continue

            return False

        except Exception as e:
            logger.warning(
                "Mandatory channel check xatosi: %s",
                e,
            )

            # Kanalni tekshirishning iloji bo'lmasa,
            # foydalanuvchini bloklab qo'ymaslik uchun davom etamiz.
            continue

    return True


async def mandatory_message(update, context):
    channels = get_mandatory_channels()

    if not channels:
        return True

    keyboard = []

    for channel in channels:
        username = channel["username"]

        if username:
            if not username.startswith("@"):
                username = "@" + username

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📢 {channel['title'] or username}",
                        url=f"https://t.me/{username.lstrip('@')}",
                    )
                ]
            )
        elif channel["invite_link"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📢 {channel['title'] or 'Kanal'}",
                        url=channel["invite_link"],
                    )
                ]
            )

    keyboard.append(
        [
            InlineKeyboardButton(
                "✅ Tekshirish",
                callback_data="check_mandatory",
            )
        ]
    )

    text = (
        "🔐 <b>Botdan foydalanish uchun quyidagi kanallarga "
        "obuna bo'ling.</b>\n\n"
        "Obuna bo'lgach, <b>✅ Tekshirish</b> tugmasini bosing."
    )

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )

    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    return False


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    add_user(user)

    # Referral
    if context.args:
        try:
            referrer_id = int(context.args[0])

            if (
                referrer_id != user.id
                and get_user(user.id)["referred_by"] is None
            ):
                referrer = get_user(referrer_id)

                if referrer:
                    conn = db()
                    cur = conn.cursor()

                    cur.execute(
                        """
                        UPDATE users
                        SET referred_by = ?
                        WHERE user_id = ?
                        """,
                        (
                            referrer_id,
                            user.id,
                        ),
                    )

                    cur.execute(
                        """
                        UPDATE users
                        SET referral_count = referral_count + 1,
                            balance = balance + ?
                        WHERE user_id = ?
                        """,
                        (
                            REFERRAL_REWARD,
                            referrer_id,
                        ),
                    )

                    conn.commit()
                    conn.close()

                    log_activity(
                        user.id,
                        "referral",
                        f"referrer={referrer_id}",
                    )

        except Exception as e:
            logger.warning("Referral xatosi: %s", e)

    # Adminlar mandatory checkdan o'tkazilmaydi
    if not is_admin(user.id):
        if not await check_mandatory(user.id, context.bot):
            await mandatory_message(update, context)
            return

    name = user.first_name or "do'st"

    text = (
        f"👋 Salom, <b>{name}</b>!\n\n"
        "⭐ <b>FrostStars</b> botiga xush kelibsiz!\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang."
    )

    await update.message.reply_text(
        text,
        reply_markup=user_menu(user.id),
        parse_mode="HTML",
    )

    log_activity(user.id, "start")


# ============================================================
# STARS
# ============================================================

def get_task_channels():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM channels
        ORDER BY id ASC
        """
    )

    result = cur.fetchall()
    conn.close()

    return result


async def show_stars(update, context):
    user_id = update.effective_user.id

    user = get_user(user_id)

    if not user:
        add_user(update.effective_user)
        user = get_user(user_id)

    channels = get_task_channels()

    keyboard = []

    for channel in channels:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📢 {channel['title']} +{channel['reward']} ⭐",
                    callback_data=f"task:{channel['id']}",
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="balance",
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back",
            )
        ]
    )

    text = (
        "⭐ <b>Stars</b>\n\n"
        f"💰 Balansingiz: <b>{user['balance']:.2f} ⭐</b>\n\n"
        "Kanallarga obuna bo'lib Stars yig'ing:"
    )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def show_task(update, context, task_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM channels WHERE id = ?",
        (task_id,),
    )

    channel = cur.fetchone()
    conn.close()

    if not channel:
        await update.callback_query.answer(
            "❌ Vazifa topilmadi.",
            show_alert=True,
        )
        return

    username = channel["username"]

    keyboard = []

    if username:
        clean_username = username.lstrip("@")

        keyboard.append(
            [
                InlineKeyboardButton(
                    "📢 Kanalga o'tish",
                    url=f"https://t.me/{clean_username}",
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "✅ Obunani tekshirish",
                callback_data=f"checktask:{task_id}",
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="stars",
            )
        ]
    )

    await update.callback_query.edit_message_text(
        f"📢 <b>{channel['title']}</b>\n\n"
        f"Obuna bo'ling va <b>+{channel['reward']} ⭐</b> oling.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def check_task(update, context, task_id):
    user_id = update.effective_user.id

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM channels WHERE id = ?",
        (task_id,),
    )

    channel = cur.fetchone()

    if not channel:
        conn.close()

        await update.callback_query.answer(
            "❌ Vazifa topilmadi.",
            show_alert=True,
        )
        return

    cur.execute(
        """
        SELECT id
        FROM completed_tasks
        WHERE user_id = ?
        AND task_id = ?
        """,
        (
            user_id,
            task_id,
        ),
    )

    already = cur.fetchone()

    if already:
        conn.close()

        await update.callback_query.answer(
            "⚠️ Bu vazifani oldin bajargansiz.",
            show_alert=True,
        )
        return

    username = channel["username"]

    if not username:
        conn.close()

        await update.callback_query.answer(
            "❌ Kanal username'i mavjud emas.",
            show_alert=True,
        )
        return

    try:
        member = await context.bot.get_chat_member(
            chat_id=f"@{username.lstrip('@')}",
            user_id=user_id,
        )

        subscribed = (
            member.status in (
                "member",
                "administrator",
                "creator",
            )
            or (
                member.status == "restricted"
                and getattr(member, "is_member", False)
            )
        )

        if not subscribed:
            conn.close()

            await update.callback_query.answer(
                "❌ Avval kanalga obuna bo'ling.",
                show_alert=True,
            )
            return

    except Exception as e:
        conn.close()

        logger.warning(
            "Task channel tekshirish xatosi: %s",
            e,
        )

        await update.callback_query.answer(
            "❌ Kanalni tekshirib bo'lmadi. "
            "Bot kanalga admin ekanini tekshiring.",
            show_alert=True,
        )
        return

    cur.execute(
        """
        INSERT INTO completed_tasks
        (user_id, task_id, created_at)
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            task_id,
            now(),
        ),
    )

    cur.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
        """,
        (
            channel["reward"],
            user_id,
        ),
    )

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        "task_completed",
        f"task={task_id};reward={channel['reward']}",
    )

    await update.callback_query.answer(
        f"✅ +{channel['reward']} ⭐ qo'shildi!",
        show_alert=True,
    )

    await show_stars(update, context)


# ============================================================
# BALANCE
# ============================================================

async def show_balance(update, context):
    user = get_user(update.effective_user.id)

    if not user:
        add_user(update.effective_user)
        user = get_user(update.effective_user.id)

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="stars",
            )
        ]
    ]

    await update.callback_query.edit_message_text(
        "💰 <b>Sizning balansingiz</b>\n\n"
        f"⭐ <b>{user['balance']:.2f} Stars</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


# ============================================================
# REFERRAL
# ============================================================

async def show_referral(update, context):
    user_id = update.effective_user.id

    user = get_user(user_id)

    if not user:
        add_user(update.effective_user)
        user = get_user(user_id)

    bot_username = context.bot.username

    referral_link = (
        f"https://t.me/{bot_username}?start={user_id}"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📤 Share",
                switch_inline_query=(
                    f"FrostStars botiga qo'shiling:\n{referral_link}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back",
            )
        ],
    ]

    await update.callback_query.edit_message_text(
        "👥 <b>Referral</b>\n\n"
        f"👤 Taklif qilganlar: <b>{user['referral_count']}</b>\n"
        f"💰 Har bir referral: <b>{REFERRAL_REWARD} ⭐</b>\n\n"
        "🔗 Sizning referral linkingiz:\n"
        f"<code>{referral_link}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


# ============================================================
# STATISTICS
# ============================================================

async def show_statistics(update, context):
    user = get_user(update.effective_user.id)

    if not user:
        add_user(update.effective_user)
        user = get_user(update.effective_user.id)

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM completed_tasks
        WHERE user_id = ?
        """,
        (user["user_id"],),
    )

    tasks = cur.fetchone()["count"]

    conn.close()

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back",
            )
        ]
    ]

    await update.callback_query.edit_message_text(
        "📊 <b>Statistika</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"⭐ Balans: <b>{user['balance']:.2f}</b>\n"
        f"📋 Bajarilgan vazifalar: <b>{tasks}</b>\n"
        f"👥 Referral: <b>{user['referral_count']}</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


# ============================================================
# RULES
# ============================================================

async def show_rules(update, context):
    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back",
            )
        ]
    ]

    text = (
        "📜 <b>FrostStars qoidalari</b>\n\n"
        "1️⃣ Vazifalarni faqat bir marta bajarish mumkin.\n\n"
        "2️⃣ Soxta obuna yoki boshqa usullar bilan tizimni "
        "aldash taqiqlanadi.\n\n"
        "3️⃣ Gift so'rovlari admin tomonidan ko'rib chiqiladi.\n\n"
        "4️⃣ Referral orqali bonus olish mumkin.\n\n"
        "5️⃣ Botdan foydalanishda halol bo'ling."
    )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


# ============================================================
# GIFTS
# ============================================================

GIFTS = {
    "❤️ Heart": 5,
    "🧸 Teddy Bear": 10,
    "🌹 Rose": 15,
}


async def show_gifts(update, context):
    keyboard = []

    for gift_name, price in GIFTS.items():
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{gift_name} — {price} ⭐",
                    callback_data=f"giftconfirm:{gift_name}",
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back",
            )
        ]
    )

    user = get_user(update.effective_user.id)

    await update.callback_query.edit_message_text(
        "🎁 <b>Gift</b>\n\n"
        f"💰 Balansingiz: <b>{user['balance']:.2f} ⭐</b>\n\n"
        "Kerakli giftni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def confirm_gift(update, context, gift_name):
    if gift_name not in GIFTS:
        await update.callback_query.answer(
            "❌ Gift topilmadi.",
            show_alert=True,
        )
        return

    price = GIFTS[gift_name]

    user = get_user(update.effective_user.id)

    if not user:
        add_user(update.effective_user)
        user = get_user(update.effective_user.id)

    if user["balance"] < price:
        await update.callback_query.answer(
            "❌ Balansingiz yetarli emas.",
            show_alert=True,
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Tasdiqlash",
                callback_data=f"buygift:{gift_name}",
            ),
            InlineKeyboardButton(
                "❌ Bekor qilish",
                callback_data="gift",
            ),
        ]
    ]

    await update.callback_query.edit_message_text(
        f"🎁 <b>{gift_name}</b>\n\n"
        f"Narxi: <b>{price} ⭐</b>\n\n"
        "Sotib olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def buy_gift(update, context, gift_name):
    if gift_name not in GIFTS:
        await update.callback_query.answer(
            "❌ Gift topilmadi.",
            show_alert=True,
        )
        return

    price = GIFTS[gift_name]
    user_id = update.effective_user.id

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,),
    )

    user = cur.fetchone()

    if not user or user["balance"] < price:
        conn.close()

        await update.callback_query.answer(
            "❌ Balansingiz yetarli emas.",
            show_alert=True,
        )
        return

    cur.execute(
        """
        UPDATE users
        SET balance = balance - ?
        WHERE user_id = ?
        """,
        (
            price,
            user_id,
        ),
    )

    cur.execute(
        """
        INSERT INTO gift_requests
        (
            user_id,
            gift_name,
            price,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            gift_name,
            price,
            "pending",
            now(),
            now(),
        ),
    )

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        "gift_request",
        f"{gift_name};price={price}",
    )

    await update.callback_query.answer(
        "✅ Gift so'rovi yuborildi!",
        show_alert=True,
    )

    await update.callback_query.edit_message_text(
        "🎁 <b>So'rov qabul qilindi!</b>\n\n"
        f"Gift: <b>{gift_name}</b>\n"
        f"Narx: <b>{price} ⭐</b>\n\n"
        "Admin so'rovni ko'rib chiqadi.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="back",
                    )
                ]
            ]
        ),
        parse_mode="HTML",
    )


# ============================================================
# ADVERTISING
# ============================================================

async def show_advertising(update, context):
    context.user_data["state"] = "advertisement"

    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Bekor qilish",
                callback_data="back",
            )
        ]
    ]

    await update.callback_query.edit_message_text(
        "📢 <b>Advertising</b>\n\n"
        "Reklamangiz haqida ma'lumot yuboring.\n\n"
        "Masalan:\n"
        "• Kanal nomi\n"
        "• Kanal username\n"
        "• Reklama matni\n"
        "• Kerakli vaqt\n\n"
        "✍️ Xabaringizni yozing:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def save_advertisement(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO advertiser_requests
        (
            user_id,
            text,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            text,
            "pending",
            now(),
        ),
    )

    conn.commit()
    conn.close()

    context.user_data.pop("state", None)

    log_activity(
        user_id,
        "advertisement_request",
        text[:500],
    )

    await update.message.reply_text(
        "✅ <b>Reklama so'rovingiz yuborildi!</b>\n\n"
        "Admin ko'rib chiqadi.",
        reply_markup=user_menu(user_id),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN STATISTICS
# ============================================================

async def admin_stats(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM users")
    users = cur.fetchone()["c"]

    cur.execute(
        """
        SELECT COALESCE(SUM(balance), 0) AS total
        FROM users
        """
    )

    total_balance = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS c FROM channels"
    )

    channels = cur.fetchone()["c"]

    cur.execute(
        "SELECT COUNT(*) AS c FROM mandatory_channels"
    )

    mandatory = cur.fetchone()["c"]

    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM gift_requests
        WHERE status = 'pending'
        """
    )

    pending_gifts = cur.fetchone()["c"]

    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM advertiser_requests
        WHERE status = 'pending'
        """
    )

    pending_ads = cur.fetchone()["c"]

    conn.close()

    text = (
        "📊 <b>Admin Statistics</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"⭐ Total balance: <b>{total_balance:.2f}</b>\n"
        f"📢 Task channels: <b>{channels}</b>\n"
        f"🔐 Mandatory channels: <b>{mandatory}</b>\n"
        f"🎁 Pending gifts: <b>{pending_gifts}</b>\n"
        f"📣 Pending ads: <b>{pending_ads}</b>"
    )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN USERS
# ============================================================

async def admin_users(update, context):
    users = get_all_users()

    text = "👥 <b>Users</b>\n\n"

    if not users:
        text += "Hozircha user yo'q."
    else:
        for user in users[:50]:
            username = (
                f"@{user['username']}"
                if user["username"]
                else "username yo'q"
            )

            text += (
                f"🆔 <code>{user['user_id']}</code>\n"
                f"👤 {username}\n"
                f"⭐ {user['balance']:.2f}\n"
                f"👥 Ref: {user['referral_count']}\n\n"
            )

    if len(users) > 50:
        text += f"\n... va yana {len(users) - 50} ta user."

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN LOGS
# ============================================================

async def admin_logs(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 30
        """
    )

    logs = cur.fetchall()
    conn.close()

    text = "📋 <b>Oxirgi 30 ta log</b>\n\n"

    if not logs:
        text += "Loglar mavjud emas."
    else:
        for item in logs:
            details = item["details"] or ""

            text += (
                f"🆔 {item['user_id']}\n"
                f"⚙️ {item['action']}\n"
                f"📝 {details[:100]}\n"
                f"🕐 {item['created_at']}\n\n"
            )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN ADMINS
# ============================================================

async def admin_admins(update, context):
    admins = get_admins()

    text = "👑 <b>Admins</b>\n\n"

    for admin in admins:
        role = "OWNER" if admin["user_id"] == OWNER_ID else "ADMIN"

        text += (
            f"🆔 <code>{admin['user_id']}</code>\n"
            f"👑 {role}\n\n"
        )

    text += (
        "Admin qo'shish:\n"
        "<code>/addadmin USER_ID</code>\n\n"
        "Adminni o'chirish:\n"
        "<code>/removeadmin USER_ID</code>"
    )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN TASK CHANNELS
# ============================================================

async def admin_channels(update, context):
    channels = get_task_channels()

    text = "📢 <b>Task Channels</b>\n\n"

    if not channels:
        text += "Kanallar yo'q."
    else:
        for channel in channels:
            text += (
                f"🆔 ID: <code>{channel['id']}</code>\n"
                f"📢 {channel['title']}\n"
                f"🔗 @{channel['username']}\n"
                f"⭐ Reward: {channel['reward']}\n\n"
            )

    text += (
        "Kanal qo'shish:\n"
        "<code>/addtask</code>\n\n"
        "Kanal o'chirish:\n"
        "<code>/deltask ID</code>"
    )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN MANDATORY
# ============================================================

async def admin_mandatory(update, context):
    channels = get_mandatory_channels()

    text = "🔐 <b>Mandatory Channels</b>\n\n"

    if not channels:
        text += "Majburiy kanallar yo'q.\n\n"
    else:
        for channel in channels:
            text += (
                f"🆔 ID: <code>{channel['id']}</code>\n"
                f"📢 {channel['title']}\n"
                f"🆔 Channel ID: <code>{channel['channel_id']}</code>\n"
                f"🔗 {channel['invite_link'] or '-'}\n\n"
            )

    text += (
        "Qo'shish:\n"
        "<code>/addmandatory</code>\n\n"
        "O'chirish:\n"
        "<code>/delmandatory ID</code>"
    )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN GIFTS
# ============================================================

async def admin_gifts(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM gift_requests
        ORDER BY id DESC
        LIMIT 30
        """
    )

    gifts = cur.fetchall()
    conn.close()

    text = "🎁 <b>Gift Requests</b>\n\n"

    if not gifts:
        text += "Gift so'rovlari yo'q."
    else:
        for gift in gifts:
            text += (
                f"🆔 ID: <code>{gift['id']}</code>\n"
                f"👤 User: <code>{gift['user_id']}</code>\n"
                f"🎁 {gift['gift_name']}\n"
                f"⭐ {gift['price']}\n"
                f"📌 {gift['status']}\n\n"
            )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN ADS
# ============================================================

async def admin_ads(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM advertiser_requests
        ORDER BY id DESC
        LIMIT 30
        """
    )

    ads = cur.fetchall()
    conn.close()

    text = "📣 <b>Advertising Requests</b>\n\n"

    if not ads:
        text += "Reklama so'rovlari yo'q."
    else:
        for ad in ads:
            text += (
                f"🆔 ID: <code>{ad['id']}</code>\n"
                f"👤 User: <code>{ad['user_id']}</code>\n"
                f"📌 {ad['status']}\n"
                f"📝 {ad['text'][:300]}\n\n"
            )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN COMMANDS
# ============================================================

async def add_admin_command(update, context):
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await update.message.reply_text(
            "❌ Faqat owner bu buyruqdan foydalanishi mumkin."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/addadmin USER_ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ USER_ID raqam bo'lishi kerak."
        )
        return

    add_admin(target_id)

    await update.message.reply_text(
        f"✅ <code>{target_id}</code> admin qilindi.",
        parse_mode="HTML",
    )


async def remove_admin_command(update, context):
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await update.message.reply_text(
            "❌ Faqat owner bu buyruqdan foydalanishi mumkin."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/removeadmin USER_ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ USER_ID raqam bo'lishi kerak."
        )
        return

    if target_id == OWNER_ID:
        await update.message.reply_text(
            "❌ Ownerni o'chirib bo'lmaydi."
        )
        return

    removed = remove_admin(target_id)

    if removed:
        await update.message.reply_text(
            f"✅ <code>{target_id}</code> adminlikdan olindi.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "❌ Bu user admin emas."
        )


async def add_task_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "add_task_username"

    await update.message.reply_text(
        "📢 Yangi task kanal qo'shish.\n\n"
        "1-qadam:\n"
        "Kanal username'ini yuboring.\n\n"
        "Masalan:\n"
        "<code>@MyChannel</code>",
        parse_mode="HTML",
    )


async def delete_task_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/deltask ID"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM channels WHERE id = ?",
        (task_id,),
    )

    deleted = cur.rowcount > 0

    conn.commit()
    conn.close()

    if deleted:
        await update.message.reply_text(
            "✅ Task kanal o'chirildi."
        )
    else:
        await update.message.reply_text(
            "❌ Bunday ID topilmadi."
        )


async def add_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "mandatory_channel_id"

    await update.message.reply_text(
        "🔐 Mandatory kanal qo'shish.\n\n"
        "1-qadam:\n"
        "Kanal ID sini yuboring.\n\n"
        "Masalan:\n"
        "<code>-1001234567890</code>",
        parse_mode="HTML",
    )


async def delete_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Foydalanish:\n"
            "/delmandatory ID"
        )
        return

    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo'lishi kerak."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM mandatory_channels
        WHERE id = ?
        """,
        (channel_id,),
    )

    deleted = cur.rowcount > 0

    conn.commit()
    conn.close()

    if deleted:
        await update.message.reply_text(
            "✅ Mandatory kanal o'chirildi."
        )
    else:
        await update.message.reply_text(
            "❌ Bunday ID topilmadi."
        )


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user or not update.message:
        return

    add_user(user)

    state = context.user_data.get("state")

    # --------------------------------------------------------
    # ADVERTISEMENT
    # --------------------------------------------------------

    if state == "advertisement":
        await save_advertisement(update, context)
        return

    # --------------------------------------------------------
    # ADD TASK - USERNAME
    # --------------------------------------------------------

    if state == "add_task_username":
        if not is_admin(user.id):
            context.user_data.pop("state", None)
            return

        username = update.message.text.strip()

        if username.startswith("https://t.me/"):
            username = username.replace(
                "https://t.me/",
                "",
                1,
            )

        username = username.lstrip("@").split("/")[0].strip()

        if not username:
            await update.message.reply_text(
                "❌ Username noto'g'ri.\n"
                "Masalan: @MyChannel"
            )
            return

        context.user_data["task_username"] = username
        context.user_data["state"] = "add_task_title"

        await update.message.reply_text(
            "2-qadam:\n\n"
            "Kanal nomini yuboring."
        )
        return

    # --------------------------------------------------------
    # ADD TASK - TITLE
    # --------------------------------------------------------

    if state == "add_task_title":
        if not is_admin(user.id):
            context.user_data.pop("state", None)
            return

        title = update.message.text.strip()

        if not title:
            await update.message.reply_text(
                "❌ Kanal nomi bo'sh bo'lmasin."
            )
            return

        context.user_data["task_title"] = title
        context.user_data["state"] = "add_task_reward"

        await update.message.reply_text(
            "3-qadam:\n\n"
            "Reward miqdorini yuboring.\n\n"
            "Masalan:\n"
            "<code>0.1</code>",
            parse_mode="HTML",
        )
        return

    # --------------------------------------------------------
    # ADD TASK - REWARD
    # --------------------------------------------------------

    if state == "add_task_reward":
        if not is_admin(user.id):
            context.user_data.pop("state", None)
            return

        try:
            reward = float(update.message.text.strip())

            if reward <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "❌ Reward musbat son bo'lishi kerak.\n"
                "Masalan: 0.1"
            )
            return

        username = context.user_data.get(
            "task_username"
        )

        title = context.user_data.get(
            "task_title"
        )

        conn = db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO channels
            (
                username,
                title,
                reward,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                title,
                reward,
                now(),
            ),
        )

        conn.commit()
        conn.close()

        context.user_data.pop("state", None)
        context.user_data.pop("task_username", None)
        context.user_data.pop("task_title", None)

        await update.message.reply_text(
            "✅ <b>Task kanal qo'shildi!</b>\n\n"
            f"📢 @{username}\n"
            f"📌 {title}\n"
            f"⭐ Reward: {reward}",
            reply_markup=user_menu(user.id),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # MANDATORY - CHANNEL ID
    # --------------------------------------------------------

    if state == "mandatory_channel_id":
        if not is_admin(user.id):
            context.user_data.pop("state", None)
            return

        channel_id = update.message.text.strip()

        try:
            int(channel_id)
        except ValueError:
            await update.message.reply_text(
                "❌ Channel ID noto'g'ri.\n"
                "Masalan: -1001234567890"
            )
            return

        context.user_data["mandatory_channel_id"] = channel_id
        context.user_data["state"] = "mandatory_title"

        await update.message.reply_text(
            "2-qadam:\n\n"
            "Kanal nomini yuboring."
        )
        return

    # --------------------------------------------------------
    # MANDATORY - TITLE
    # --------------------------------------------------------

    if state == "mandatory_title":
        if not is_admin(user.id):
            context.user_data.pop("state", None)
            return

        title = update.message.text.strip()

        if not title:
            await update.message.reply_text(
                "❌ Kanal nomi bo'sh bo'lmasin."
            )
            return

        context.user_data["mandatory_title"] = title
        context.user_data["state"] = "mandatory_link"

        await update.message.reply_text(
            "3-qadam:\n\n"
            "Kanal username yoki invite linkini yuboring.\n\n"
            "Masalan:\n"
            "<code>@MyChannel</code>\n"
            "yoki\n"
            "<code>https://t.me/+xxxxx</code>",
            parse_mode="HTML",
        )
        return

    # --------------------------------------------------------
    # MANDATORY - LINK
    # --------------------------------------------------------

    if state == "mandatory_link":
        if not is_admin(user.id):
            context.user_data.pop("state", None)
            return

        link = update.message.text.strip()

        channel_id = context.user_data.get(
            "mandatory_channel_id"
        )

        title = context.user_data.get(
            "mandatory_title"
        )

        username = ""

        if link.startswith("@"):
            username = link.lstrip("@")

        elif "t.me/" in link:
            part = link.split("t.me/", 1)[1]
            part = part.split("?", 1)[0]
            part = part.strip("/")

            if not part.startswith("+"):
                username = part

        conn = db()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                INSERT INTO mandatory_channels
                (
                    channel_id,
                    username,
                    title,
                    invite_link,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    channel_id,
                    username,
                    title,
                    link,
                    now(),
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()

            await update.message.reply_text(
                "❌ Bu channel ID allaqachon mavjud."
            )
            return

        conn.close()

        context.user_data.pop("state", None)
        context.user_data.pop("mandatory_channel_id", None)
        context.user_data.pop("mandatory_title", None)

        await update.message.reply_text(
            "✅ <b>Mandatory kanal qo'shildi!</b>\n\n"
            f"📢 {title}\n"
            f"🆔 {channel_id}",
            reply_markup=user_menu(user.id),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # MANDATORY CHECK FOR NORMAL USERS
    # --------------------------------------------------------

    if not is_admin(user.id):
        if not await check_mandatory(user.id, context.bot):
            await mandatory_message(update, context)
            return

    # --------------------------------------------------------
    # NORMAL TEXT
    # --------------------------------------------------------

    text = update.message.text.strip()

    if text == "⭐ Stars":
        await update.message.reply_text(
            "⭐ Stars bo'limini tugmalar orqali oching.",
            reply_markup=user_menu(user.id),
        )
        return

    await update.message.reply_text(
        "👇 Menyudan kerakli bo'limni tanlang.",
        reply_markup=user_menu(user.id),
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    try:
        await query.answer()
    except Exception:
        pass

    user = update.effective_user

    if not user:
        return

    add_user(user)

    data = query.data or ""

    logger.info(
        "Callback: user=%s data=%s",
        user.id,
        data,
    )

    # --------------------------------------------------------
    # MANDATORY CHECK
    # --------------------------------------------------------

    if data == "check_mandatory":
        if is_admin(user.id):
            await query.edit_message_text(
                "✅ Siz adminsiz.\n\n"
                "Asosiy menyu:",
                reply_markup=user_menu(user.id),
            )
            return

        ok = await check_mandatory(
            user.id,
            context.bot,
        )

        if ok:
            await query.edit_message_text(
                "✅ Obuna tekshirildi!\n\n"
                "Endi botdan foydalanishingiz mumkin.",
                reply_markup=user_menu(user.id),
            )
        else:
            await mandatory_message(
                update,
                context,
            )

        return

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if data == "back":
        context.user_data.pop("state", None)

        await query.edit_message_text(
            "🏠 <b>Asosiy menyu</b>\n\n"
            "Kerakli bo'limni tanlang:",
            reply_markup=user_menu(user.id),
            parse_mode="HTML",
        )
        return

    # --------------------------------------------------------
    # STARS
    # --------------------------------------------------------

    if data == "stars":
        if not is_admin(user.id):
            if not await check_mandatory(
                user.id,
                context.bot,
            ):
                await mandatory_message(
                    update,
                    context,
                )
                return

        await show_stars(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # BALANCE
    # --------------------------------------------------------

    if data == "balance":
        await show_balance(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # TASK
    # --------------------------------------------------------

    if data.startswith("task:"):
        try:
            task_id = int(
                data.split(":", 1)[1]
            )
        except ValueError:
            await query.answer(
                "❌ Xato task ID.",
                show_alert=True,
            )
            return

        await show_task(
            update,
            context,
            task_id,
        )
        return

    # --------------------------------------------------------
    # CHECK TASK
    # --------------------------------------------------------

    if data.startswith("checktask:"):
        try:
            task_id = int(
                data.split(":", 1)[1]
            )
        except ValueError:
            await query.answer(
                "❌ Xato task ID.",
                show_alert=True,
            )
            return

        await check_task(
            update,
            context,
            task_id,
        )
        return

    # --------------------------------------------------------
    # REFERRAL
    # --------------------------------------------------------

    if data == "referral":
        await show_referral(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    if data == "statistics":
        await show_statistics(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # RULES
    # --------------------------------------------------------

    if data == "rules":
        await show_rules(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # GIFTS
    # --------------------------------------------------------

    if data == "gift":
        await show_gifts(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # GIFT CONFIRM
    # --------------------------------------------------------

    if data.startswith("giftconfirm:"):
        gift_name = data.split(
            "giftconfirm:",
            1,
        )[1]

        await confirm_gift(
            update,
            context,
            gift_name,
        )
        return

    # --------------------------------------------------------
    # BUY GIFT
    # --------------------------------------------------------

    if data.startswith("buygift:"):
        gift_name = data.split(
            "buygift:",
            1,
        )[1]

        await buy_gift(
            update,
            context,
            gift_name,
        )
        return

    # --------------------------------------------------------
    # ADVERTISING
    # --------------------------------------------------------

    if data == "advertising":
        context.user_data["state"] = "advertisement"

        await show_advertising(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN PANEL
    # --------------------------------------------------------

    if data == "admin_panel":
        if not is_admin(user.id):
            await query.answer(
                "❌ Siz admin emassiz.",
                show_alert=True,
            )
            return

        context.user_data.pop("state", None)

        await query.edit_message_text(
            "👑 <b>Admin Panel</b>\n\n"
            "Kerakli bo'limni tanlang:",
            reply_markup=admin_menu(),
            parse_mode="HTML",
        )
        return

    # --------------------------------------------------------
    # ADMIN STATISTICS
    # --------------------------------------------------------

    if data == "admin_stats":
        if not is_admin(user.id):
            return

        await admin_stats(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN USERS
    # --------------------------------------------------------

    if data == "admin_users":
        if not is_admin(user.id):
            return

        await admin_users(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN LOGS
    # --------------------------------------------------------

    if data == "admin_logs":
        if not is_admin(user.id):
            return

        await admin_logs(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN ADMINS
    # --------------------------------------------------------

    if data == "admin_admins":
        if not is_admin(user.id):
            return

        await admin_admins(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN CHANNELS
    # --------------------------------------------------------

    if data == "admin_channels":
        if not is_admin(user.id):
            return

        await admin_channels(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN MANDATORY
    # --------------------------------------------------------

    if data == "admin_mandatory":
        if not is_admin(user.id):
            return

        await admin_mandatory(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN GIFTS
    # --------------------------------------------------------

    if data == "admin_gifts":
        if not is_admin(user.id):
            return

        await admin_gifts(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN ADS
    # --------------------------------------------------------

    if data == "admin_ads":
        if not is_admin(user.id):
            return

        await admin_ads(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # UNKNOWN CALLBACK
    # --------------------------------------------------------

    await query.answer(
        "⚠️ Bu tugma hozir mavjud emas.",
        show_alert=True,
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Telegram bot error:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    logger.info("FrostStars ishga tushmoqda...")

    init_db()

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "addadmin",
            add_admin_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "removeadmin",
            remove_admin_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "addtask",
            add_task_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "deltask",
            delete_task_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "addmandatory",
            add_mandatory_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "delmandatory",
            delete_mandatory_command,
        )
    )

    # --------------------------------------------------------
    # CALLBACKS
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            callback_handler,
        )
    )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    app.add_error_handler(
        error_handler,
    )

    logger.info(
        "=========================================="
    )
    logger.info(
        "✅ FROSTSTARS BOT IS RUNNING!"
    )
    logger.info(
        "=========================================="
    )

    app.run_polling(
        drop_pending_updates=True,
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
