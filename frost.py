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
# 🇺🇿 FROSTSTARS
# TELEGRAM BOT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "starbot.db"

# ============================================================
# BOT CONFIG
# ============================================================

# Telegram BotFather tokenini KODGA yozmang.
# FadeHost -> Environment Variables -> BOT_TOKEN
TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError(
        "\n"
        "==================================================\n"
        "🇺🇿 FROSTSTARS BOT\n"
        "==================================================\n"
        "❌ BOT_TOKEN topilmadi!\n\n"
        "FadeHost'da Environment Variables bo'limiga:\n\n"
        "Name: BOT_TOKEN\n"
        "Value: BotFather tokeni\n\n"
        "qo'shing va botni Redeploy qiling.\n"
        "==================================================\n"
    )

# ASOSIY OWNER TELEGRAM ID
OWNER_ID = 6383248812

# Mukofotlar
DEFAULT_TASK_REWARD = 0.1
REFERRAL_REWARD = 1.5


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("FrostStars")


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            referred_by INTEGER,
            referrals INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            completed_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            gift_id TEXT,
            gift_name TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            title TEXT,
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            details TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            title TEXT,
            created_at TEXT
        )
    """)

    # OWNER avtomatik admin
    cur.execute("""
        INSERT OR IGNORE INTO admins(user_id, added_at)
        VALUES (?, ?)
    """, (OWNER_ID, now()))

    # Standart topshiriq kanallari
    count = cur.execute(
        "SELECT COUNT(*) AS c FROM channels"
    ).fetchone()["c"]

    if count == 0:
        cur.execute("""
            INSERT OR IGNORE INTO channels
            (channel_id, title, reward, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            "@Cossmoss_00",
            "Cossmoss",
            0.1,
            now(),
        ))

        cur.execute("""
            INSERT OR IGNORE INTO channels
            (channel_id, title, reward, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            "@PromptLab_UZ",
            "PromptLab UZ",
            0.1,
            now(),
        ))

    conn.commit()
    conn.close()


# ============================================================
# USER FUNCTIONS
# ============================================================

def add_user(user, referred_by=None):
    conn = db()
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user.id,),
    ).fetchone()

    if existing:
        cur.execute("""
            UPDATE users
            SET username=?, first_name=?
            WHERE user_id=?
        """, (
            user.username or "",
            user.first_name or "",
            user.id,
        ))

        conn.commit()
        conn.close()
        return False

    referrer = None

    if referred_by:
        try:
            referred_by = int(referred_by)
        except (ValueError, TypeError):
            referred_by = None

        if referred_by and referred_by != user.id:
            referrer = cur.execute(
                "SELECT * FROM users WHERE user_id=?",
                (referred_by,),
            ).fetchone()

    cur.execute("""
        INSERT INTO users
        (
            user_id,
            username,
            first_name,
            balance,
            referred_by,
            referrals,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        0,
        referrer["user_id"] if referrer else None,
        0,
        now(),
    ))

    if referrer:
        cur.execute("""
            UPDATE users
            SET balance=balance+?,
                referrals=referrals+1
            WHERE user_id=?
        """, (
            REFERRAL_REWARD,
            referrer["user_id"],
        ))

    conn.commit()
    conn.close()

    return True


def get_user(user_id):
    conn = db()

    row = conn.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,),
    ).fetchone()

    conn.close()

    return row


def change_balance(user_id, amount):
    conn = db()

    conn.execute("""
        UPDATE users
        SET balance=balance+?
        WHERE user_id=?
    """, (
        amount,
        user_id,
    ))

    conn.commit()
    conn.close()


# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def is_admin(user_id):
    conn = db()

    row = conn.execute(
        "SELECT user_id FROM admins WHERE user_id=?",
        (user_id,),
    ).fetchone()

    conn.close()

    return row is not None


def is_owner(user_id):
    return user_id == OWNER_ID


def get_admins():
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM admins
        ORDER BY added_at ASC
    """).fetchall()

    conn.close()

    return rows


def add_admin(user_id):
    conn = db()

    conn.execute("""
        INSERT OR IGNORE INTO admins(user_id, added_at)
        VALUES (?, ?)
    """, (
        user_id,
        now(),
    ))

    conn.commit()
    conn.close()


def remove_admin(user_id):
    if user_id == OWNER_ID:
        return False

    conn = db()

    conn.execute(
        "DELETE FROM admins WHERE user_id=?",
        (user_id,),
    )

    conn.commit()
    conn.close()

    return True


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_activity(user, action, details=""):
    try:
        conn = db()

        conn.execute("""
            INSERT INTO activity_logs
            (
                user_id,
                username,
                action,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user.id if user else 0,
            user.username if user and user.username else "",
            action,
            details,
            now(),
        ))

        conn.commit()
        conn.close()

    except Exception:
        logger.exception("Activity log error")


# ============================================================
# KEYBOARDS
# ============================================================

def user_menu(user_id):
    buttons = [
        ["⭐ Stars ishlash"],
        ["👥 Referal", "📊 Statistika"],
        ["💳 Gift olish"],
        ["ℹ️ Qoidalar", "📢 Reklama"],
    ]

    if is_admin(user_id):
        buttons.append(["👑 Admin panel"])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["📊 Bot statistikasi"],
            ["👥 Foydalanuvchilar", "📜 Faoliyat loglari"],
            ["👑 Adminlar"],
            ["📌 Majburiy kanallar"],
            ["📢 Topshiriq kanallari"],
            ["🎁 Gift so‘rovlari"],
            ["📣 Reklama so‘rovlari"],
            ["🔙 Orqaga"],
        ],
        resize_keyboard=True,
    )


# ============================================================
# MANDATORY CHANNEL CHECK
# ============================================================

async def check_mandatory(update, context):
    user = update.effective_user

    if not user:
        return True

    conn = db()

    channels = conn.execute("""
        SELECT *
        FROM mandatory_channels
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    if not channels:
        return True

    not_joined = []

    for channel in channels:
        try:
            member = await context.bot.get_chat_member(
                channel["channel_id"],
                user.id,
            )

            if member.status not in (
                "member",
                "administrator",
                "creator",
            ):
                not_joined.append(channel)

        except Exception:
            not_joined.append(channel)

    if not_joined:
        buttons = []

        for channel in not_joined:
            channel_id = str(channel["channel_id"]).strip()

            if channel_id.startswith("@"):
                username = channel_id[1:]

                buttons.append([
                    InlineKeyboardButton(
                        f"📢 {channel['title']}",
                        url=f"https://t.me/{username}",
                    )
                ])

        buttons.append([
            InlineKeyboardButton(
                "🔎 Tekshirish",
                callback_data="mandatory:check",
            )
        ])

        message = update.effective_message

        if message:
            await message.reply_text(
                "📌 Botdan foydalanish uchun "
                "quyidagi kanallarga a'zo bo'ling:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        return False

    return True


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    referred_by = None

    if context.args:
        referred_by = context.args[0]

    new_user = add_user(
        user,
        referred_by,
    )

    log_activity(
        user,
        "/start",
        f"new_user={new_user}",
    )

    if not await check_mandatory(update, context):
        return

    await update.message.reply_text(
        f"Salom, {user.first_name}! 👋\n\n"
        "⭐ FrostStars botiga xush kelibsiz!",
        reply_markup=user_menu(user.id),
    )


# ============================================================
# STARS MENU
# ============================================================

async def send_stars_menu(bot, user_id):
    if not is_admin(user_id):
        pass

    conn = db()

    channels = conn.execute("""
        SELECT *
        FROM channels
        ORDER BY id ASC
    """).fetchall()

    completed = conn.execute("""
        SELECT task_id
        FROM completed_tasks
        WHERE user_id=?
    """, (
        user_id,
    )).fetchall()

    conn.close()

    completed_ids = {
        row["task_id"]
        for row in completed
    }

    buttons = []

    for channel in channels:
        if channel["id"] in completed_ids:
            text = f"✅ {channel['title']}"
        else:
            text = (
                f"⭐ {channel['title']} "
                f"+{channel['reward']} Stars"
            )

        buttons.append([
            InlineKeyboardButton(
                text,
                callback_data=f"task:{channel['id']}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:main",
        )
    ])

    return (
        "⭐ Stars ishlash\n\n"
        "Topshiriqlardan birini tanlang:",
        InlineKeyboardMarkup(buttons),
    )


async def stars_menu(update, context):
    user = update.effective_user

    if not user:
        return

    if not await check_mandatory(update, context):
        return

    text, markup = await send_stars_menu(
        context.bot,
        user.id,
    )

    log_activity(
        user,
        "stars_menu",
    )

    await update.message.reply_text(
        text,
        reply_markup=markup,
    )


async def show_stars_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    text, markup = await send_stars_menu(
        context.bot,
        user_id,
    )

    await query.edit_message_text(
        text,
        reply_markup=markup,
    )


# ============================================================
# TASK
# ============================================================

async def show_task(update, context, task_id):
    query = update.callback_query

    conn = db()

    channel = conn.execute("""
        SELECT *
        FROM channels
        WHERE id=?
    """, (
        task_id,
    )).fetchone()

    conn.close()

    if not channel:
        await query.answer(
            "Topshiriq topilmadi.",
            show_alert=True,
        )
        return

    username = str(
        channel["channel_id"]
    ).strip().lstrip("@")

    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Kanalga kirish",
                url=f"https://t.me/{username}",
            )
        ],
        [
            InlineKeyboardButton(
                "🔎 Tekshirish",
                callback_data=f"check:{task_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back:stars",
            )
        ],
    ]

    await query.edit_message_text(
        f"⭐ {channel['title']}\n\n"
        f"Mukofot: +{channel['reward']} Stars\n\n"
        "1. Kanalga a'zo bo'ling.\n"
        "2. Keyin «Tekshirish» tugmasini bosing.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def check_task(update, context, task_id):
    query = update.callback_query
    user_id = query.from_user.id

    conn = db()

    channel = conn.execute("""
        SELECT *
        FROM channels
        WHERE id=?
    """, (
        task_id,
    )).fetchone()

    if not channel:
        conn.close()

        await query.answer(
            "Topshiriq topilmadi.",
            show_alert=True,
        )
        return

    already = conn.execute("""
        SELECT id
        FROM completed_tasks
        WHERE user_id=? AND task_id=?
    """, (
        user_id,
        task_id,
    )).fetchone()

    conn.close()

    if already:
        await query.answer(
            "Bu topshiriq allaqachon bajarilgan.",
            show_alert=True,
        )
        return

    try:
        member = await context.bot.get_chat_member(
            channel["channel_id"],
            user_id,
        )

        if member.status not in (
            "member",
            "administrator",
            "creator",
        ):
            await query.answer(
                "Avval kanalga a'zo bo'ling.",
                show_alert=True,
            )
            return

    except Exception:
        logger.exception(
            "Channel membership check error"
        )

        await query.answer(
            "Kanalni tekshirib bo'lmadi. "
            "Bot kanalga admin ekanini tekshiring.",
            show_alert=True,
        )
        return

    conn = db()

    try:
        conn.execute("""
            INSERT INTO completed_tasks
            (
                user_id,
                task_id,
                completed_at
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            task_id,
            now(),
        ))

        conn.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE user_id=?
        """, (
            channel["reward"],
            user_id,
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()

        await query.answer(
            "Bu topshiriq allaqachon bajarilgan.",
            show_alert=True,
        )
        return

    finally:
        try:
            conn.close()
        except Exception:
            pass

    log_activity(
        query.from_user,
        "task_completed",
        f"task_id={task_id}",
    )

    await query.answer(
        f"✅ +{channel['reward']} Stars qo‘shildi!",
        show_alert=True,
    )

    await query.edit_message_text(
        "✅ Topshiriq bajarildi!\n\n"
        f"⭐ +{channel['reward']} Stars",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "⭐ Boshqa topshiriqlar",
                    callback_data="back:stars",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Bosh menyu",
                    callback_data="back:main",
                )
            ],
        ]),
    )


# ============================================================
# REFERRAL
# ============================================================

async def referral(update, context):
    user = update.effective_user

    me = await context.bot.get_me()

    if not me.username:
        await update.message.reply_text(
            "❌ Bot username'i topilmadi."
        )
        return

    link = (
        f"https://t.me/{me.username}"
        f"?start={user.id}"
    )

    row = get_user(user.id)

    referrals = row["referrals"] if row else 0
    balance = row["balance"] if row else 0

    log_activity(
        user,
        "referral",
    )

    await update.message.reply_text(
        "👥 Referal tizimi\n\n"
        f"🔗 Sizning referal havolangiz:\n"
        f"{link}\n\n"
        f"👥 Referallar: {referrals}\n"
        f"⭐ Balans: {balance:.2f}\n\n"
        f"Har bir yangi referal uchun "
        f"+{REFERRAL_REWARD} Stars.",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 Orqaga"]],
            resize_keyboard=True,
        ),
    )


# ============================================================
# STATISTICS
# ============================================================

async def statistics(update, context):
    user = update.effective_user

    row = get_user(user.id)

    conn = db()

    tasks = conn.execute("""
        SELECT COUNT(*) AS c
        FROM completed_tasks
        WHERE user_id=?
    """, (
        user.id,
    )).fetchone()["c"]

    conn.close()

    balance = row["balance"] if row else 0
    referrals = row["referrals"] if row else 0

    log_activity(
        user,
        "statistics",
    )

    await update.message.reply_text(
        "📊 Sizning statistikangiz\n\n"
        f"⭐ Balans: {balance:.2f} Stars\n"
        f"✅ Bajarilgan topshiriqlar: {tasks}\n"
        f"👥 Referallar: {referrals}",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 Orqaga"]],
            resize_keyboard=True,
        ),
    )


# ============================================================
# RULES
# ============================================================

async def rules(update, context):
    log_activity(
        update.effective_user,
        "rules",
    )

    await update.message.reply_text(
        "ℹ️ Qoidalar\n\n"
        "1. Topshiriqlarni haqiqiy bajaring.\n"
        "2. Soxta akkauntlardan foydalanmang.\n"
        "3. Bot tizimlaridan adolatli foydalaning.\n"
        "4. Qoidalarni buzgan akkaunt cheklanishi mumkin.",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 Orqaga"]],
            resize_keyboard=True,
        ),
    )


# ============================================================
# GIFTS
# ============================================================

def get_available_gifts():
    return [
        ("gift_1", "💖 Yurak", 5),
        ("gift_2", "🧸 Teddy Bear", 10),
        ("gift_3", "🌹 Gul", 15),
    ]


async def gifts(update, context):
    user_id = update.effective_user.id

    row = get_user(user_id)

    balance = row["balance"] if row else 0

    buttons = []

    for gift_id, name, price in get_available_gifts():
        buttons.append([
            InlineKeyboardButton(
                f"{name} — {price} ⭐",
                callback_data=f"gift:{gift_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:main",
        )
    ])

    log_activity(
        update.effective_user,
        "gifts",
    )

    await update.message.reply_text(
        f"💳 Gift olish\n\n"
        f"⭐ Sizning balansingiz: {balance:.2f}\n\n"
        "Giftni tanlang:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_gifts_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    row = get_user(user_id)
    balance = row["balance"] if row else 0

    buttons = []

    for gift_id, name, price in get_available_gifts():
        buttons.append([
            InlineKeyboardButton(
                f"{name} — {price} ⭐",
                callback_data=f"gift:{gift_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:main",
        )
    ])

    await query.edit_message_text(
        f"💳 Gift olish\n\n"
        f"⭐ Sizning balansingiz: {balance:.2f}\n\n"
        "Giftni tanlang:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_gift(update, context, gift_id):
    query = update.callback_query

    gift = None

    for item in get_available_gifts():
        if item[0] == gift_id:
            gift = item
            break

    if not gift:
        await query.answer(
            "Gift topilmadi.",
            show_alert=True,
        )
        return

    _, name, price = gift

    await query.edit_message_text(
        f"{name}\n\n"
        f"Narxi: {price} ⭐\n\n"
        "Sotib olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"confirmgift:{gift_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Orqaga",
                    callback_data="back:gifts",
                )
            ],
        ]),
    )


async def confirm_gift(update, context, gift_id):
    query = update.callback_query
    user_id = query.from_user.id

    gift = None

    for item in get_available_gifts():
        if item[0] == gift_id:
            gift = item
            break

    if not gift:
        await query.answer(
            "Gift topilmadi.",
            show_alert=True,
        )
        return

    _, name, price = gift

    conn = db()

    row = conn.execute("""
        SELECT *
        FROM users
        WHERE user_id=?
    """, (
        user_id,
    )).fetchone()

    if not row or row["balance"] < price:
        conn.close()

        await query.answer(
            "Balansingiz yetarli emas.",
            show_alert=True,
        )
        return

    try:
        conn.execute("""
            UPDATE users
            SET balance=balance-?
            WHERE user_id=?
        """, (
            price,
            user_id,
        ))

        cur = conn.execute("""
            INSERT INTO gift_requests
            (
                user_id,
                price,
                status,
                created_at,
                gift_id,
                gift_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            price,
            "pending",
            now(),
            gift_id,
            name,
        ))

        request_id = cur.lastrowid

        conn.commit()

    except Exception:
        conn.rollback()
        conn.close()

        logger.exception(
            "Gift order error"
        )

        await query.answer(
            "Xatolik yuz berdi. Qayta urinib ko‘ring.",
            show_alert=True,
        )
        return

    conn.close()

    log_activity(
        query.from_user,
        "gift_order",
        f"request_id={request_id}, gift={name}",
    )

    await query.edit_message_text(
        "✅ Gift so‘rovi yuborildi!\n\n"
        f"🎁 {name}\n"
        f"⭐ {price} Stars\n"
        f"🆔 So‘rov: #{request_id}\n\n"
        "Admin tekshirganidan keyin "
        "buyurtma qayta ishlanadi."
    )

    # Adminlarga xabar
    for admin in get_admins():
        try:
            await context.bot.send_message(
                admin["user_id"],
                "🎁 Yangi Gift so‘rovi!\n\n"
                f"🆔 #{request_id}\n"
                f"👤 User: {query.from_user.id}\n"
                f"@{query.from_user.username or '-'}\n"
                f"🎁 {name}\n"
                f"⭐ {price}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ Tasdiqlash",
                            callback_data=f"giftapprove:{request_id}",
                        ),
                        InlineKeyboardButton(
                            "❌ Rad etish",
                            callback_data=f"giftreject:{request_id}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "📦 Yetkazildi",
                            callback_data=f"giftdelivered:{request_id}",
                        )
                    ],
                ]),
            )

        except Exception:
            logger.exception(
                "Admin notification error"
            )


# ============================================================
# ADMIN STATISTICS
# ============================================================

async def admin_statistics(update, context):
    if not is_admin(update.effective_user.id):
        return

    conn = db()

    users = conn.execute(
        "SELECT COUNT(*) AS c FROM users"
    ).fetchone()["c"]

    tasks = conn.execute(
        "SELECT COUNT(*) AS c FROM completed_tasks"
    ).fetchone()["c"]

    gifts = conn.execute(
        "SELECT COUNT(*) AS c FROM gift_requests"
    ).fetchone()["c"]

    pending = conn.execute("""
        SELECT COUNT(*) AS c
        FROM gift_requests
        WHERE status='pending'
    """).fetchone()["c"]

    admins = conn.execute(
        "SELECT COUNT(*) AS c FROM admins"
    ).fetchone()["c"]

    conn.close()

    await update.message.reply_text(
        "📊 Bot statistikasi\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"✅ Bajarilgan topshiriqlar: {tasks}\n"
        f"🎁 Gift so‘rovlari: {gifts}\n"
        f"⏳ Kutilayotgan Giftlar: {pending}\n"
        f"👑 Adminlar: {admins}",
        reply_markup=admin_menu(),
    )


# ============================================================
# ADMIN USERS
# ============================================================

async def admin_users(update, context):
    if not is_admin(update.effective_user.id):
        return

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM users
        ORDER BY created_at DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    if not rows:
        await update.message.reply_text(
            "Foydalanuvchilar yo‘q.",
            reply_markup=admin_menu(),
        )
        return

    text = "👥 Oxirgi foydalanuvchilar:\n\n"

    for row in rows:
        text += (
            f"🆔 {row['user_id']}\n"
            f"👤 @{row['username'] or '-'}\n"
            f"⭐ {row['balance']:.2f}\n"
            f"📅 {row['created_at']}\n\n"
        )

    await update.message.reply_text(
        text[:4000],
        reply_markup=admin_menu(),
    )


# ============================================================
# ACTIVITY LOGS
# ============================================================

async def activity_logs(update, context):
    if not is_admin(update.effective_user.id):
        return

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 30
    """).fetchall()

    conn.close()

    if not rows:
        await update.message.reply_text(
            "Loglar mavjud emas.",
            reply_markup=admin_menu(),
        )
        return

    text = "📜 Faoliyat loglari\n\n"

    for row in rows:
        text += (
            f"🕐 {row['created_at']}\n"
            f"👤 {row['user_id']} "
            f"@{row['username'] or '-'}\n"
            f"⚙️ {row['action']}\n"
            f"📝 {row['details'] or '-'}\n\n"
        )

    await update.message.reply_text(
        text[:4000],
        reply_markup=admin_menu(),
    )


# ============================================================
# ADMINS
# ============================================================

async def admin_list(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    admins = get_admins()

    text = "👑 Adminlar\n\n"

    for admin in admins:
        owner = (
            " 👑 OWNER"
            if admin["user_id"] == OWNER_ID
            else ""
        )

        text += (
            f"🆔 {admin['user_id']}{owner}\n"
            f"📅 {admin['added_at']}\n\n"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Admin qo‘shish",
                callback_data="admin:add",
            )
        ],
        [
            InlineKeyboardButton(
                "➖ Admin olib tashlash",
                callback_data="admin:remove",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back:admin",
            )
        ],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# TASK CHANNELS
# ============================================================

async def task_channels(update, context):
    if not is_admin(update.effective_user.id):
        return

    conn = db()

    channels = conn.execute("""
        SELECT *
        FROM channels
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    text = "📢 Topshiriq kanallari\n\n"

    if not channels:
        text += "Hozircha kanal yo‘q.\n"

    for ch in channels:
        text += (
            f"#{ch['id']} — {ch['title']}\n"
            f"{ch['channel_id']}\n"
            f"⭐ Mukofot: {ch['reward']}\n\n"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Kanal qo‘shish",
                callback_data="taskchannel:add",
            )
        ]
    ]

    for ch in channels:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {ch['title']}",
                callback_data=f"taskchannel:delete:{ch['id']}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:admin",
        )
    ])

    await update.message.reply_text(
        text[:4000],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# MANDATORY CHANNELS
# ============================================================

async def mandatory_channels(update, context):
    if not is_admin(update.effective_user.id):
        return

    conn = db()

    channels = conn.execute("""
        SELECT *
        FROM mandatory_channels
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    text = "📌 Majburiy kanallar\n\n"

    if not channels:
        text += "Majburiy kanal yo‘q.\n"

    for ch in channels:
        text += (
            f"#{ch['id']} — {ch['title']}\n"
            f"{ch['channel_id']}\n\n"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Kanal qo‘shish",
                callback_data="mandatory:add",
            )
        ]
    ]

    for ch in channels:
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ {ch['title']}",
                callback_data=f"mandatory:edit:{ch['id']}",
            ),
            InlineKeyboardButton(
                "🗑",
                callback_data=f"mandatory:delete:{ch['id']}",
            ),
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:admin",
        )
    ])

    await update.message.reply_text(
        text[:4000],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# GIFT REQUESTS
# ============================================================

async def gift_requests(update, context):
    if not is_admin(update.effective_user.id):
        return

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM gift_requests
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    text = "🎁 Gift so‘rovlari\n\n"

    if not rows:
        text += "So‘rovlar yo‘q."

    for row in rows:
        text += (
            f"#{row['id']}\n"
            f"👤 {row['user_id']}\n"
            f"🎁 {row['gift_name']}\n"
            f"⭐ {row['price']}\n"
            f"📌 {row['status']}\n"
            f"🕐 {row['created_at']}\n\n"
        )

    await update.message.reply_text(
        text[:4000],
        reply_markup=admin_menu(),
    )


# ============================================================
# GIFT STATUS
# ============================================================

async def gift_status(
    update,
    context,
    request_id,
    status,
):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer(
            "❌ Siz admin emassiz.",
            show_alert=True,
        )
        return

    conn = db()

    request = conn.execute("""
        SELECT *
        FROM gift_requests
        WHERE id=?
    """, (
        request_id,
    )).fetchone()

    if not request:
        conn.close()

        await query.answer(
            "So‘rov topilmadi.",
            show_alert=True,
        )
        return

    old_status = request["status"]

    # Bir xil statusni qayta o'zgartirmaslik
    if old_status == status:
        conn.close()

        await query.answer(
            "Bu status allaqachon qo‘yilgan.",
            show_alert=True,
        )
        return

    conn.execute("""
        UPDATE gift_requests
        SET status=?
        WHERE id=?
    """, (
        status,
        request_id,
    ))

    # Faqat pending -> rejected bo'lganda balans qaytariladi
    if (
        status == "rejected"
        and old_status == "pending"
    ):
        conn.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE user_id=?
        """, (
            request["price"],
            request["user_id"],
        ))

    conn.commit()
    conn.close()

    status_names = {
        "approved": "✅ Tasdiqlandi",
        "rejected": "❌ Rad etildi",
        "delivered": "📦 Yetkazildi",
    }

    status_text = status_names.get(
        status,
        status,
    )

    await query.answer(
        status_text,
        show_alert=True,
    )

    try:
        extra = ""

        if status == "rejected":
            extra = (
                "\n\n❗ Rad etilgani uchun "
                "Stars balansingizga qaytarildi."
            )

        await context.bot.send_message(
            request["user_id"],
            f"🎁 Gift so‘rovi #{request_id}\n\n"
            f"Gift: {request['gift_name']}\n"
            f"Holat: {status_text}"
            f"{extra}",
        )

    except Exception:
        logger.exception(
            "Gift user notification error"
        )

    await query.edit_message_text(
        f"🎁 Gift so‘rovi #{request_id}\n\n"
        f"👤 User: {request['user_id']}\n"
        f"🎁 {request['gift_name']}\n"
        f"⭐ {request['price']}\n\n"
        f"Holat: {status_text}"
    )


# ============================================================
# ADVERTISING
# ============================================================

async def advertising(update, context):
    context.user_data[
        "awaiting_advertisement"
    ] = True

    await update.message.reply_text(
        "📢 Reklama\n\n"
        "Reklamangizni bitta xabar qilib yuboring.\n"
        "U adminlarga ko‘rib chiqish uchun yuboriladi.",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 Orqaga"]],
            resize_keyboard=True,
        ),
    )


async def save_advertisement(update, context):
    user = update.effective_user

    message = (
        update.message.text or ""
    ).strip()

    if not message:
        await update.message.reply_text(
            "❌ Reklama matni bo‘sh bo‘lmasin."
        )
        return

    conn = db()

    cur = conn.execute("""
        INSERT INTO advertiser_requests
        (
            user_id,
            username,
            message,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        message,
        "pending",
        now(),
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    context.user_data[
        "awaiting_advertisement"
    ] = False

    log_activity(
        user,
        "advertisement_request",
        f"request_id={request_id}",
    )

    await update.message.reply_text(
        "✅ Reklama so‘rovingiz adminlarga yuborildi.\n\n"
        f"🆔 So‘rov: #{request_id}",
        reply_markup=user_menu(user.id),
    )

    for admin in get_admins():
        try:
            await context.bot.send_message(
                admin["user_id"],
                "📢 Yangi reklama so‘rovi!\n\n"
                f"🆔 #{request_id}\n"
                f"👤 {user.id}\n"
                f"@{user.username or '-'}\n\n"
                f"{message}",
            )

        except Exception:
            logger.exception(
                "Advertisement admin notification error"
            )


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(update, context):
    user = update.effective_user

    if not user or not update.message:
        return

    text = (
        update.message.text or ""
    ).strip()

    # --------------------------------------------------------
    # REKLAMA HOLATI
    # --------------------------------------------------------

    if context.user_data.get(
        "awaiting_advertisement"
    ):
        if text == "🔙 Orqaga":
            context.user_data[
                "awaiting_advertisement"
            ] = False

            await update.message.reply_text(
                "🏠 Bosh menyu.",
                reply_markup=user_menu(user.id),
            )
            return

        await save_advertisement(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # TASK CHANNEL ADD
    # --------------------------------------------------------

    if context.user_data.get(
        "task_channel_add"
    ):
        step = context.user_data[
            "task_channel_add"
        ]

        if step == "username":
            username = text.strip()

            if not username.startswith("@"):
                await update.message.reply_text(
                    "❌ Username @ bilan boshlansin.\n"
                    "Masalan: @example"
                )
                return

            context.user_data[
                "task_channel_username"
            ] = username

            context.user_data[
                "task_channel_add"
            ] = "title"

            await update.message.reply_text(
                "Kanal nomini yuboring:"
            )
            return

        if step == "title":
            context.user_data[
                "task_channel_title"
            ] = text

            context.user_data[
                "task_channel_add"
            ] = "reward"

            await update.message.reply_text(
                "Mukofotni kiriting.\n"
                f"Masalan: {DEFAULT_TASK_REWARD}"
            )
            return

        if step == "reward":
            try:
                reward = float(
                    text.replace(",", ".")
                )

                if reward <= 0:
                    raise ValueError

            except ValueError:
                await update.message.reply_text(
                    "❌ Mukofot musbat raqam bo‘lishi kerak.\n"
                    "Masalan: 0.1"
                )
                return

            username = context.user_data[
                "task_channel_username"
            ]

            title = context.user_data[
                "task_channel_title"
            ]

            conn = db()

            try:
                conn.execute("""
                    INSERT INTO channels
                    (
                        channel_id,
                        title,
                        reward,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    username,
                    title,
                    reward,
                    now(),
                ))

                conn.commit()

                await update.message.reply_text(
                    "✅ Topshiriq kanali qo‘shildi.",
                    reply_markup=admin_menu(),
                )

            except sqlite3.IntegrityError:
                await update.message.reply_text(
                    "❌ Bu kanal allaqachon mavjud.",
                    reply_markup=admin_menu(),
                )

            finally:
                conn.close()

            context.user_data.pop(
                "task_channel_add",
                None,
            )

            context.user_data.pop(
                "task_channel_username",
                None,
            )

            context.user_data.pop(
                "task_channel_title",
                None,
            )

            return

    # --------------------------------------------------------
    # MANDATORY CHANNEL ADD
    # --------------------------------------------------------

    if context.user_data.get(
        "mandatory_add"
    ):
        step = context.user_data[
            "mandatory_add"
        ]

        if step == "username":
            username = text.strip()

            if not username.startswith("@"):
                await update.message.reply_text(
                    "❌ Username @ bilan boshlansin.\n"
                    "Masalan: @example"
                )
                return

            context.user_data[
                "mandatory_username"
            ] = username

            context.user_data[
                "mandatory_add"
            ] = "title"

            await update.message.reply_text(
                "Kanal nomini yuboring:"
            )
            return

        if step == "title":
            username = context.user_data[
                "mandatory_username"
            ]

            title = text

            conn = db()

            try:
                conn.execute("""
                    INSERT INTO mandatory_channels
                    (
                        channel_id,
                        title,
                        created_at
                    )
                    VALUES (?, ?, ?)
                """, (
                    username,
                    title,
                    now(),
                ))

                conn.commit()

                await update.message.reply_text(
                    "✅ Majburiy kanal qo‘shildi.",
                    reply_markup=admin_menu(),
                )

            except sqlite3.IntegrityError:
                await update.message.reply_text(
                    "❌ Bu kanal allaqachon mavjud.",
                    reply_markup=admin_menu(),
                )

            finally:
                conn.close()

            context.user_data.pop(
                "mandatory_add",
                None,
            )

            context.user_data.pop(
                "mandatory_username",
                None,
            )

            return

    # --------------------------------------------------------
    # MANDATORY EDIT
    # --------------------------------------------------------

    if context.user_data.get(
        "mandatory_edit"
    ):
        channel_id = context.user_data[
            "mandatory_edit"
        ]

        if not text.startswith("@"):
            await update.message.reply_text(
                "❌ Username @ bilan boshlansin."
            )
            return

        conn = db()

        conn.execute("""
            UPDATE mandatory_channels
            SET channel_id=?
            WHERE id=?
        """, (
            text,
            channel_id,
        ))

        conn.commit()
        conn.close()

        context.user_data.pop(
            "mandatory_edit",
            None,
        )

        await update.message.reply_text(
            "✅ Majburiy kanal yangilandi.",
            reply_markup=admin_menu(),
        )
        return

    # --------------------------------------------------------
    # ADMIN ADD
    # --------------------------------------------------------

    if context.user_data.get(
        "admin_add"
    ):
        if not is_admin(user.id):
            context.user_data.pop(
                "admin_add",
                None,
            )
            return

        try:
            new_admin = int(text)

            if new_admin <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "❌ Telegram ID raqam bo‘lishi kerak."
            )
            return

        add_admin(new_admin)

        context.user_data.pop(
            "admin_add",
            None,
        )

        await update.message.reply_text(
            f"✅ {new_admin} admin qilindi.",
            reply_markup=admin_menu(),
        )
        return

    # --------------------------------------------------------
    # ADMIN REMOVE
    # --------------------------------------------------------

    if context.user_data.get(
        "admin_remove"
    ):
        if not is_owner(user.id):
            context.user_data.pop(
                "admin_remove",
                None,
            )

            await update.message.reply_text(
                "❌ Faqat Owner adminlarni olib tashlashi mumkin."
            )
            return

        try:
            remove_id = int(text)

            if remove_id <= 0:
                raise ValueError

        except ValueError:
            await update.message.reply_text(
                "❌ Telegram ID raqam bo‘lishi kerak."
            )
            return

        if remove_id == OWNER_ID:
            await update.message.reply_text(
                "❌ Ownerni olib tashlab bo‘lmaydi."
            )
            return

        remove_admin(remove_id)

        context.user_data.pop(
            "admin_remove",
            None,
        )

        await update.message.reply_text(
            f"✅ {remove_id} adminlikdan chiqarildi.",
            reply_markup=admin_menu(),
        )
        return

    # ========================================================
    # USER MENU
    # ========================================================

    if text == "⭐ Stars ishlash":
        await stars_menu(
            update,
            context,
        )
        return

    if text == "👥 Referal":
        await referral(
            update,
            context,
        )
        return

    if text == "📊 Statistika":
        await statistics(
            update,
            context,
        )
        return

    if text == "💳 Gift olish":
        await gifts(
            update,
            context,
        )
        return

    if text == "ℹ️ Qoidalar":
        await rules(
            update,
            context,
        )
        return

    if text == "📢 Reklama":
        await advertising(
            update,
            context,
        )
        return

    if text == "🔙 Orqaga":
        await update.message.reply_text(
            "🏠 Bosh menyu",
            reply_markup=user_menu(user.id),
        )
        return

    # ========================================================
    # ADMIN MENU
    # ========================================================

    if text == "👑 Admin panel":
        if not is_admin(user.id):
            await update.message.reply_text(
                "❌ Siz admin emassiz."
            )
            return

        log_activity(
            user,
            "admin_panel",
        )

        await update.message.reply_text(
            "👑 Admin panel",
            reply_markup=admin_menu(),
        )
        return

    if text == "📊 Bot statistikasi":
        if is_admin(user.id):
            await admin_statistics(
                update,
                context,
            )
        return

    if text == "👥 Foydalanuvchilar":
        if is_admin(user.id):
            await admin_users(
                update,
                context,
            )
        return

    if text == "📜 Faoliyat loglari":
        if is_admin(user.id):
            await activity_logs(
                update,
                context,
            )
        return

    if text == "👑 Adminlar":
        if is_admin(user.id):
            await admin_list(
                update,
                context,
            )
        return

    if text == "📌 Majburiy kanallar":
        if is_admin(user.id):
            await mandatory_channels(
                update,
                context,
            )
        return

    if text == "📢 Topshiriq kanallari":
        if is_admin(user.id):
            await task_channels(
                update,
                context,
            )
        return

    if text == "🎁 Gift so‘rovlari":
        if is_admin(user.id):
            await gift_requests(
                update,
                context,
            )
        return

    if text == "📣 Reklama so‘rovlari":
        if not is_admin(user.id):
            return

        conn = db()

        rows = conn.execute("""
            SELECT *
            FROM advertiser_requests
            ORDER BY id DESC
            LIMIT 20
        """).fetchall()

        conn.close()

        text_out = "📣 Reklama so‘rovlari\n\n"

        if not rows:
            text_out += "So‘rovlar yo‘q."

        for row in rows:
            text_out += (
                f"#{row['id']}\n"
                f"👤 {row['user_id']}\n"
                f"@{row['username'] or '-'}\n"
                f"📌 {row['status']}\n"
                f"🕐 {row['created_at']}\n"
                f"📝 {row['message']}\n\n"
            )

        await update.message.reply_text(
            text_out[:4000],
            reply_markup=admin_menu(),
        )

        return


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(update, context):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""
    user_id = query.from_user.id

    # ========================================================
    # BACK -> MAIN
    # ========================================================

    if data == "back:main":
        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            user_id,
            "🏠 Bosh menyu",
            reply_markup=user_menu(user_id),
        )
        return

    # ========================================================
    # BACK -> ADMIN
    # ========================================================

    if data == "back:admin":
        if not is_admin(user_id):
            return

        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            user_id,
            "👑 Admin panel",
            reply_markup=admin_menu(),
        )
        return

    # ========================================================
    # BACK -> STARS
    # ========================================================

    if data == "back:stars":
        if not await check_mandatory(
            update,
            context,
        ):
            return

        text, markup = await send_stars_menu(
            context.bot,
            user_id,
        )

        await query.edit_message_text(
            text,
            reply_markup=markup,
        )
        return

    # ========================================================
    # BACK -> GIFTS
    # ========================================================

    if data == "back:gifts":
        await show_gifts_callback(
            update,
            context,
        )
        return

    # ========================================================
    # MANDATORY CHECK
    # ========================================================

    if data == "mandatory:check":
        if await check_mandatory(
            update,
            context,
        ):
            try:
                await query.edit_message_text(
                    "✅ Barcha majburiy kanallarga "
                    "a'zo bo‘lgansiz.\n\n"
                    "Endi botdan foydalanishingiz mumkin."
                )
            except Exception:
                pass

            await context.bot.send_message(
                user_id,
                "🏠 Bosh menyu",
                reply_markup=user_menu(user_id),
            )

        return

    # ========================================================
    # TASK
    # ========================================================

    if data.startswith("task:"):
        try:
            task_id = int(
                data.split(":")[1]
            )
        except (ValueError, IndexError):
            return

        await show_task(
            update,
            context,
            task_id,
        )
        return

    if data.startswith("check:"):
        try:
            task_id = int(
                data.split(":")[1]
            )
        except (ValueError, IndexError):
            return

        await check_task(
            update,
            context,
            task_id,
        )
        return

    # ========================================================
    # GIFTS
    # ========================================================

    if data.startswith("gift:"):
        gift_id = data.split(
            ":",
            1,
        )[1]

        await show_gift(
            update,
            context,
            gift_id,
        )
        return

    if data.startswith("confirmgift:"):
        gift_id = data.split(
            ":",
            1,
        )[1]

        await confirm_gift(
            update,
            context,
            gift_id,
        )
        return

    # ========================================================
    # GIFT ADMIN
    # ========================================================

    if data.startswith("giftapprove:"):
        if not is_admin(user_id):
            return

        try:
            request_id = int(
                data.split(":")[1]
            )
        except (ValueError, IndexError):
            return

        await gift_status(
            update,
            context,
            request_id,
            "approved",
        )
        return

    if data.startswith("giftreject:"):
        if not is_admin(user_id):
            return

        try:
            request_id = int(
                data.split(":")[1]
            )
        except (ValueError, IndexError):
            return

        await gift_status(
            update,
            context,
            request_id,
            "rejected",
        )
        return

    if data.startswith("giftdelivered:"):
        if not is_admin(user_id):
            return

        try:
            request_id = int(
                data.split(":")[1]
            )
        except (ValueError, IndexError):
            return

        await gift_status(
            update,
            context,
            request_id,
            "delivered",
        )
        return

    # ========================================================
    # ADMIN ADD
    # ========================================================

    if data == "admin:add":
        if not is_admin(user_id):
            return

        context.user_data[
            "admin_add"
        ] = True

        await query.edit_message_text(
            "➕ Yangi adminning Telegram ID "
            "raqamini yuboring.\n\n"
            "Masalan:\n"
            "123456789"
        )
        return

    # ========================================================
    # ADMIN REMOVE
    # ========================================================

    if data == "admin:remove":
        if not is_owner(user_id):
            await query.answer(
                "❌ Faqat Owner adminni "
                "olib tashlashi mumkin.",
                show_alert=True,
            )
            return

        context.user_data[
            "admin_remove"
        ] = True

        await query.edit_message_text(
            "➖ Olib tashlanadigan adminning "
            "Telegram ID raqamini yuboring."
        )
        return

    # ========================================================
    # TASK CHANNEL ADD
    # ========================================================

    if data == "taskchannel:add":
        if not is_admin(user_id):
            return

        context.user_data[
            "task_channel_add"
        ] = "username"

        await query.edit_message_text(
            "📢 Kanal username'ini yuboring.\n\n"
            "Masalan:\n"
            "@example"
        )
        return

    # ========================================================
    # TASK CHANNEL DELETE
    # ========================================================

    if data.startswith(
        "taskchannel:delete:"
    ):
        if not is_admin(user_id):
            return

        try:
            channel_id = int(
                data.split(":")[2]
            )
        except (ValueError, IndexError):
            return

        conn = db()

        conn.execute(
            "DELETE FROM channels WHERE id=?",
            (channel_id,),
        )

        conn.commit()
        conn.close()

        await query.edit_message_text(
            "✅ Topshiriq kanali o‘chirildi.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Admin panel",
                        callback_data="back:admin",
                    )
                ]
            ]),
        )
        return

    # ========================================================
    # MANDATORY ADD
    # ========================================================

    if data == "mandatory:add":
        if not is_admin(user_id):
            return

        context.user_data[
            "mandatory_add"
        ] = "username"

        await query.edit_message_text(
            "📌 Majburiy kanal username'ini "
            "yuboring.\n\n"
            "Masalan:\n"
            "@example"
        )
        return

    # ========================================================
    # MANDATORY EDIT
    # ========================================================

    if data.startswith(
        "mandatory:edit:"
    ):
        if not is_admin(user_id):
            return

        try:
            channel_id = int(
                data.split(":")[2]
            )
        except (ValueError, IndexError):
            return

        context.user_data[
            "mandatory_edit"
        ] = channel_id

        await query.edit_message_text(
            "✏️ Yangi kanal username'ini "
            "yuboring."
        )
        return

    # ========================================================
    # MANDATORY DELETE
    # ========================================================

    if data.startswith(
        "mandatory:delete:"
    ):
        if not is_admin(user_id):
            return

        try:
            channel_id = int(
                data.split(":")[2]
            )
        except (ValueError, IndexError):
            return

        conn = db()

        conn.execute("""
            DELETE FROM mandatory_channels
            WHERE id=?
        """, (
            channel_id,
        ))

        conn.commit()
        conn.close()

        await query.edit_message_text(
            "✅ Majburiy kanal o‘chirildi.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Admin panel",
                        callback_data="back:admin",
                    )
                ]
            ]),
        )
        return


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update, context):
    logger.error(
        "Unhandled exception",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

# ============================================================
# MAIN
# ============================================================

def main():
    # DATABASE JADVALLARINI YARATISH
    init_db()

    application = Application.builder().token(TOKEN).build()

    # /start
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # Inline buttons
    application.add_handler(
        CallbackQueryHandler(
            callback_handler,
        )
    )

    # Text messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    # Errors
    application.add_error_handler(
        error_handler,
    )

    print("✅ FROSTSTARS BOT IS RUNNING!")

    # BOTNI DOIMIY ISHLATIB TURADI
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
