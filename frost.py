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

# Siz yuborgan kanal ID
MAIN_CHANNEL_ID = -1004425654134


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            balance REAL DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            created_at TEXT
        )
    """)

    # COMPLETED TASKS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            created_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    # GIFT REQUESTS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            gift_name TEXT,
            price REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # TASK CHANNELS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
    """)

    # ADMINS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT
        )
    """)

    # ACTIVITY LOGS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
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
            username TEXT DEFAULT '',
            title TEXT,
            invite_link TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    # OWNER
    cur.execute("""
        INSERT OR IGNORE INTO admins
        (user_id, added_at)
        VALUES (?, ?)
    """, (
        OWNER_ID,
        datetime.now().isoformat()
    ))

    # DEFAULT TASK CHANNEL
    cur.execute("""
        SELECT 1
        FROM channels
        WHERE username = ?
        LIMIT 1
    """, ("@Cossmoss_00",))

    if not cur.fetchone():
        cur.execute("""
            INSERT INTO channels
            (username, title, reward, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            "@Cossmoss_00",
            "Cossmoss",
            DEFAULT_TASK_REWARD,
            datetime.now().isoformat()
        ))

    cur.execute("""
        SELECT 1
        FROM channels
        WHERE username = ?
        LIMIT 1
    """, ("@PromptLab_UZ",))

    if not cur.fetchone():
        cur.execute("""
            INSERT INTO channels
            (username, title, reward, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            "@PromptLab_UZ",
            "PromptLab UZ",
            DEFAULT_TASK_REWARD,
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()


# =========================================================
# USERS
# =========================================================

def add_user(user):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users
        (
            user_id,
            username,
            first_name,
            balance,
            referral_count,
            referred_by,
            created_at
        )
        VALUES (?, ?, ?, 0, 0, NULL, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.now().isoformat()
    ))

    cur.execute("""
        UPDATE users
        SET username = ?,
            first_name = ?
        WHERE user_id = ?
    """, (
        user.username or "",
        user.first_name or "",
        user.id
    ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row


def change_balance(user_id, amount):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (
        amount,
        user_id
    ))

    conn.commit()
    conn.close()


def get_all_users():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        ORDER BY created_at DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


# =========================================================
# ADMIN
# =========================================================

def is_admin(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM admins WHERE user_id = ?",
        (user_id,)
    )

    result = cur.fetchone()
    conn.close()

    return result is not None


def is_owner(user_id):
    return user_id == OWNER_ID


def get_admins():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM admins
        ORDER BY added_at ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def add_admin(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO admins
        (user_id, added_at)
        VALUES (?, ?)
    """, (
        user_id,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def remove_admin(user_id):
    if user_id == OWNER_ID:
        return False

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM admins WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return True


# =========================================================
# LOG
# =========================================================

def log_activity(user_id, action, details=""):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO activity_logs
        (user_id, action, details, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        action,
        details,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# =========================================================
# USER MENU
# =========================================================

def user_menu(user_id):
    buttons = [
        ["⭐ Stars", "🎁 Gift"],
        ["👥 Referral", "📊 Statistics"],
        ["📜 Rules", "📢 Advertising"],
    ]

    if is_admin(user_id):
        buttons.append(["⚙️ Admin panel"])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True
    )


# =========================================================
# ADMIN MENU
# =========================================================

def admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["📊 Admin statistics"],
            ["👥 Users", "📝 Activity logs"],
            ["👑 Admins", "🔐 Mandatory channels"],
            ["📢 Task channels", "🎁 Gift requests"],
            ["📣 Advertising requests"],
            ["⬅️ Back"],
        ],
        resize_keyboard=True
    )


# =========================================================
# MANDATORY CHANNELS
# =========================================================

def get_mandatory_channels():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM mandatory_channels
        ORDER BY id ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


async def check_mandatory(user_id, context):
    channels = get_mandatory_channels()

    if not channels:
        return True

    for channel in channels:
        try:
            member = await context.bot.get_chat_member(
                channel["channel_id"],
                user_id
            )

            if member.status in (
                "member",
                "administrator",
                "creator"
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
                "Mandatory check error: %s",
                e
            )

            # Xatolik bo'lsa foydalanuvchini bloklamaymiz
            continue

    return True


async def send_mandatory_message(message, context):
    channels = get_mandatory_channels()

    buttons = []

    for channel in channels:
        link = channel["invite_link"]

        if not link and channel["username"]:
            username = channel["username"].replace("@", "")
            link = f"https://t.me/{username}"

        if link:
            buttons.append([
                InlineKeyboardButton(
                    f"📢 {channel['title']}",
                    url=link
                )
            ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="mandatory:check"
        )
    ])

    await message.reply_text(
        "🔐 Botdan foydalanish uchun kanallarga obuna bo‘ling:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    add_user(user)

    # Referral
    if context.args:
        try:
            referrer_id = int(context.args[0])

            current = get_user(user.id)
            referrer = get_user(referrer_id)

            if (
                referrer
                and current
                and current["referred_by"] is None
                and referrer_id != user.id
            ):
                conn = db()
                cur = conn.cursor()

                cur.execute("""
                    UPDATE users
                    SET referred_by = ?
                    WHERE user_id = ?
                """, (
                    referrer_id,
                    user.id
                ))

                cur.execute("""
                    UPDATE users
                    SET referral_count = referral_count + 1,
                        balance = balance + ?
                    WHERE user_id = ?
                """, (
                    REFERRAL_REWARD,
                    referrer_id
                ))

                conn.commit()
                conn.close()

                log_activity(
                    referrer_id,
                    "referral",
                    f"New referral: {user.id}"
                )

        except Exception as e:
            logger.warning(
                "Referral error: %s",
                e
            )

    if not await check_mandatory(
        user.id,
        context
    ):
        await send_mandatory_message(
            update.message,
            context
        )
        return

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "⭐ FrostStars botiga xush kelibsiz!\n\n"
        "Quyidagi menyudan foydalaning:",
        reply_markup=user_menu(user.id)
    )


# =========================================================
# STARS MENU
# =========================================================

async def stars_menu(update, context):
    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 Stars ishlash",
                callback_data="stars:tasks"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="stars:balance"
            )
        ]
    ]

    await update.message.reply_text(
        "⭐ Stars bo‘limi:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# TASK FUNCTIONS
# =========================================================

def get_task_channels():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM channels
        ORDER BY id ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def get_completed_task_ids(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT task_id
        FROM completed_tasks
        WHERE user_id = ?
    """, (
        user_id,
    ))

    rows = cur.fetchall()
    conn.close()

    return {row["task_id"] for row in rows}


async def send_next_task(query, context):
    user_id = query.from_user.id

    channels = get_task_channels()
    completed = get_completed_task_ids(user_id)

    remaining = [
        channel
        for channel in channels
        if channel["id"] not in completed
    ]

    if not remaining:
        await query.message.reply_text(
            "🎉 Barcha vazifalarni bajardingiz!\n\n"
            "⭐ Yangi vazifalar keyinroq qo‘shiladi."
        )
        return

    channel = remaining[0]

    username = (channel["username"] or "").replace("@", "")

    keyboard = []

    if username:
        keyboard.append([
            InlineKeyboardButton(
                f"📢 {channel['title']}",
                url=f"https://t.me/{username}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "✅ Vazifani bajarish",
            callback_data=f"task:{channel['id']}"
        )
    ])

    await query.message.reply_text(
        "🎯 Stars ishlash\n\n"
        f"📢 Kanal: {channel['title']}\n"
        f"⭐ Mukofot: +{channel['reward']} Stars\n\n"
        "1. Kanalga obuna bo‘ling.\n"
        "2. «Vazifani bajarish» tugmasini bosing.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_tasks(update, context):
    query = update.callback_query

    await query.answer()

    # Shu xabarni almashtirish uchun eski xabarni edit qilamiz
    user_id = query.from_user.id

    channels = get_task_channels()
    completed = get_completed_task_ids(user_id)

    remaining = [
        channel
        for channel in channels
        if channel["id"] not in completed
    ]

    if not remaining:
        await query.edit_message_text(
            "🎉 Barcha vazifalarni bajardingiz!"
        )
        return

    channel = remaining[0]

    username = (channel["username"] or "").replace("@", "")

    keyboard = []

    if username:
        keyboard.append([
            InlineKeyboardButton(
                f"📢 {channel['title']}",
                url=f"https://t.me/{username}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "✅ Vazifani bajarish",
            callback_data=f"task:{channel['id']}"
        )
    ])

    await query.edit_message_text(
        "🎯 Stars ishlash\n\n"
        f"📢 Kanal: {channel['title']}\n"
        f"⭐ Mukofot: +{channel['reward']} Stars\n\n"
        "1️⃣ Kanalga obuna bo‘ling.\n"
        "2️⃣ «Vazifani bajarish» tugmasini bosing.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def check_task(update, context):
    query = update.callback_query

    user_id = query.from_user.id

    try:
        task_id = int(
            query.data.split(":")[1]
        )
    except Exception:
        await query.answer(
            "❌ Vazifa ID xato.",
            show_alert=True
        )
        return

    # Callbackni darhol javoblaymiz
    await query.answer(
        "⏳ Tekshirilmoqda..."
    )

    # Vazifani olish
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM channels
        WHERE id = ?
    """, (
        task_id,
    ))

    channel = cur.fetchone()

    cur.execute("""
        SELECT 1
        FROM completed_tasks
        WHERE user_id = ?
        AND task_id = ?
    """, (
        user_id,
        task_id
    ))

    already = cur.fetchone()

    conn.close()

    if not channel:
        await query.answer(
            "❌ Vazifa topilmadi.",
            show_alert=True
        )
        return

    if already:
        await query.answer(
            "⚠️ Bu vazifa oldin bajarilgan.",
            show_alert=True
        )

        # Eski xabarni o'chirish
        try:
            await query.message.delete()
        except Exception:
            pass

        return

    username = channel["username"]

    if not username:
        await query.answer(
            "❌ Kanal username mavjud emas.",
            show_alert=True
        )
        return

    # =====================================================
    # OBUNANI TEKSHIRISH
    # =====================================================

    try:
        member = await context.bot.get_chat_member(
            username,
            user_id
        )

        subscribed = member.status in (
            "member",
            "administrator",
            "creator"
        )

        if (
            member.status == "restricted"
            and getattr(member, "is_member", False)
        ):
            subscribed = True

        if not subscribed:
            await query.answer(
                "❌ Avval kanalga obuna bo‘ling!",
                show_alert=True
            )
            return

    except Exception as e:
        logger.exception(
            "Kanal tekshirishda xato"
        )

        await query.answer(
            "❌ Kanalni tekshirib bo‘lmadi. "
            "Bot kanalga admin ekanini tekshiring.",
            show_alert=True
        )
        return

    # =====================================================
    # REWARD BERISH
    # =====================================================

    conn = db()
    cur = conn.cursor()

    try:
        # Ikki marta bosishdan himoya
        cur.execute("""
            SELECT 1
            FROM completed_tasks
            WHERE user_id = ?
            AND task_id = ?
        """, (
            user_id,
            task_id
        ))

        if cur.fetchone():
            conn.close()

            await query.answer(
                "⚠️ Vazifa allaqachon bajarilgan.",
                show_alert=True
            )
            return

        # Completed task
        cur.execute("""
            INSERT INTO completed_tasks
            (
                user_id,
                task_id,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            task_id,
            datetime.now().isoformat()
        ))

        # Balance
        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (
            channel["reward"],
            user_id
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        conn.close()

        logger.exception(
            "Reward error"
        )

        await query.answer(
            "❌ Stars berishda xatolik.",
            show_alert=True
        )
        return

    conn.close()

    log_activity(
        user_id,
        "task_completed",
        f"{channel['title']} +{channel['reward']} Stars"
    )

    # =====================================================
    # ESKI XABARNI O'CHIRISH
    # =====================================================

    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(
            "Old task message delete error: %s",
            e
        )

    # =====================================================
    # KEYINGI VAZIFA
    # =====================================================

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ Vazifa bajarildi!\n"
            f"⭐ +{channel['reward']} Stars qo‘shildi."
        )
    )

    # Keyingi taskni yangi xabar qilib chiqaramiz
    channels = get_task_channels()
    completed = get_completed_task_ids(user_id)

    remaining = [
        c for c in channels
        if c["id"] not in completed
    ]

    if not remaining:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "🎉 Barcha vazifalarni bajardingiz!\n\n"
                "⭐ Yangi vazifalar keyinroq qo‘shiladi."
            )
        )
        return

    next_channel = remaining[0]

    next_username = (
        next_channel["username"] or ""
    ).replace("@", "")

    keyboard = []

    if next_username:
        keyboard.append([
            InlineKeyboardButton(
                f"📢 {next_channel['title']}",
                url=f"https://t.me/{next_username}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "✅ Vazifani bajarish",
            callback_data=f"task:{next_channel['id']}"
        )
    ])

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            "🎯 Keyingi vazifa\n\n"
            f"📢 Kanal: {next_channel['title']}\n"
            f"⭐ Mukofot: +{next_channel['reward']} Stars\n\n"
            "Kanalga obuna bo‘ling va "
            "«Vazifani bajarish» tugmasini bosing."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# BALANCE
# =========================================================

async def show_balance(update, context):
    query = update.callback_query

    await query.answer()

    row = get_user(query.from_user.id)

    await query.edit_message_text(
        "💰 Sizning balansingiz:\n\n"
        f"⭐ {row['balance']:.2f}"
    )


# =========================================================
# GIFTS
# =========================================================

def get_available_gifts():
    return [
        ("❤️ Heart", 5),
        ("🧸 Teddy Bear", 10),
        ("🌹 Rose", 15),
    ]


async def gifts(update, context):
    keyboard = []

    for name, price in get_available_gifts():
        keyboard.append([
            InlineKeyboardButton(
                f"{name} — ⭐ {price}",
                callback_data=f"gift:{price}:{name}"
            )
        ])

    await update.message.reply_text(
        "🎁 Gift olish\n\n"
        "Kerakli sovg‘ani tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_gift(update, context):
    query = update.callback_query

    await query.answer()

    try:
        _, price, name = query.data.split(":", 2)
        price = float(price)

    except Exception:
        await query.answer(
            "❌ Gift xatosi.",
            show_alert=True
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Tasdiqlash",
                callback_data=f"giftconfirm:{price}:{name}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Bekor qilish",
                callback_data="giftcancel"
            )
        ]
    ]

    await query.edit_message_text(
        f"🎁 {name}\n\n"
        f"💰 Narxi: ⭐ {price}\n\n"
        "Sotib olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirm_gift(update, context):
    query = update.callback_query

    await query.answer()

    try:
        _, price, name = query.data.split(":", 2)
        price = float(price)

    except Exception:
        return

    user_id = query.from_user.id
    row = get_user(user_id)

    if row["balance"] < price:
        await query.message.reply_text(
            f"❌ Yetarli Stars yo‘q.\n\n"
            f"Kerak: ⭐ {price}\n"
            f"Sizda: ⭐ {row['balance']:.2f}"
        )
        return

    change_balance(
        user_id,
        -price
    )

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO gift_requests
        (
            user_id,
            gift_name,
            price,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, 'pending', ?, ?)
    """, (
        user_id,
        name,
        price,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        "gift_request",
        f"#{request_id} {name} {price}"
    )

    await query.edit_message_text(
        "✅ Gift so‘rovi yuborildi!\n\n"
        f"🎁 {name}\n"
        f"⭐ {price}\n"
        f"🆔 So‘rov: #{request_id}"
    )


# =========================================================
# REFERRAL
# =========================================================

async def referral(update, context):
    user = update.effective_user
    row = get_user(user.id)

    bot = await context.bot.get_me()

    link = (
        f"https://t.me/{bot.username}?start={user.id}"
    )

    await update.message.reply_text(
        "👥 Referral\n\n"
        f"⭐ Har bir referral: {REFERRAL_REWARD}\n"
        f"👤 Referral soni: {row['referral_count']}\n\n"
        f"🔗 Sizning linkingiz:\n{link}"
    )


# =========================================================
# STATISTICS
# =========================================================

async def statistics(update, context):
    user = update.effective_user
    row = get_user(user.id)

    await update.message.reply_text(
        "📊 Statistikangiz\n\n"
        f"🆔 ID: {user.id}\n"
        f"⭐ Balans: {row['balance']:.2f}\n"
        f"👥 Referral: {row['referral_count']}"
    )


# =========================================================
# RULES
# =========================================================

async def rules(update, context):
    await update.message.reply_text(
        "📜 FrostStars qoidalari\n\n"
        "1. Vazifalarni halol bajaring.\n"
        "2. Bir vazifani qayta bajarib bo‘lmaydi.\n"
        "3. Soxta akkauntlardan foydalanmang.\n"
        "4. Texnik xatolardan foydalanishga urinmang.\n"
        "5. Gift olish uchun yetarli Stars bo‘lishi kerak."
    )


# =========================================================
# ADVERTISING
# =========================================================

async def advertising(update, context):
    context.user_data["state"] = "advertisement"

    await update.message.reply_text(
        "📢 Reklama berish\n\n"
        "Reklamangiz haqida ma'lumot yuboring.\n\n"
        "Masalan:\n"
        "Kanal: @kanal\n"
        "Reklama turi: post\n"
        "Muddat: 1 kun"
    )


async def save_advertisement(update, context):
    user = update.effective_user
    text = update.message.text

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO advertiser_requests
        (user_id, text, status, created_at)
        VALUES (?, ?, 'pending', ?)
    """, (
        user.id,
        text,
        datetime.now().isoformat()
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    context.user_data.pop(
        "state",
        None
    )

    await update.message.reply_text(
        "✅ Reklama so‘rovi yuborildi!\n\n"
        f"🆔 #{request_id}"
    )


# =========================================================
# ADMIN STATISTICS
# =========================================================

async def admin_statistics(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM users"
    )
    balance = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM gift_requests"
    )
    gifts_count = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM advertiser_requests"
    )
    ads_count = cur.fetchone()[0]

    conn.close()

    await update.message.reply_text(
        "📊 Admin statistikasi\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"⭐ Umumiy balans: {balance:.2f}\n"
        f"🎁 Gift so‘rovlari: {gifts_count}\n"
        f"📢 Reklama so‘rovlari: {ads_count}"
    )


# =========================================================
# ADMIN USERS
# =========================================================

async def admin_users(update, context):
    users = get_all_users()

    if not users:
        await update.message.reply_text(
            "Foydalanuvchilar yo‘q."
        )
        return

    text = "👥 Foydalanuvchilar:\n\n"

    for user in users[:50]:
        username = (
            f"@{user['username']}"
            if user["username"]
            else "username yo‘q"
        )

        text += (
            f"🆔 {user['user_id']}\n"
            f"👤 {user['first_name']} ({username})\n"
            f"⭐ {user['balance']:.2f}\n"
            f"👥 Ref: {user['referral_count']}\n\n"
        )

    await update.message.reply_text(text)


# =========================================================
# ACTIVITY LOGS
# =========================================================

async def activity_logs(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "📝 Loglar yo‘q."
        )
        return

    text = "📝 Oxirgi loglar:\n\n"

    for row in rows:
        text += (
            f"#{row['id']} | "
            f"{row['user_id']} | "
            f"{row['action']}\n"
            f"{row['details']}\n\n"
        )

    await update.message.reply_text(text)


# =========================================================
# ADMINS
# =========================================================

async def admin_list(update, context):
    admins = get_admins()

    text = "👑 Adminlar:\n\n"

    for admin in admins:
        role = (
            "👑 OWNER"
            if admin["user_id"] == OWNER_ID
            else "🛡 ADMIN"
        )

        text += (
            f"{role}\n"
            f"🆔 {admin['user_id']}\n\n"
        )

    await update.message.reply_text(text)


# =========================================================
# TASK CHANNEL ADMIN
# =========================================================

async def task_channels(update, context):
    channels = get_task_channels()

    text = "📢 Vazifa kanallari:\n\n"

    for channel in channels:
        text += (
            f"🆔 {channel['id']}\n"
            f"📢 {channel['title']}\n"
            f"🔗 {channel['username']}\n"
            f"⭐ {channel['reward']}\n\n"
        )

    text += (
        "/addtask — qo‘shish\n"
        "/deltask ID — o‘chirish"
    )

    await update.message.reply_text(text)


# =========================================================
# MANDATORY ADMIN
# =========================================================

async def mandatory_channels(update, context):
    channels = get_mandatory_channels()

    text = "🔐 Majburiy kanallar:\n\n"

    if not channels:
        text += "Kanal yo‘q.\n"

    for channel in channels:
        text += (
            f"🆔 {channel['id']}\n"
            f"📌 {channel['channel_id']}\n"
            f"📢 {channel['title']}\n"
            f"🔗 {channel['invite_link']}\n\n"
        )

    text += (
        "/addmandatory — qo‘shish\n"
        "/delmandatory ID — o‘chirish"
    )

    await update.message.reply_text(text)


# =========================================================
# GIFT REQUESTS ADMIN
# =========================================================

async def gift_requests(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM gift_requests
        ORDER BY id DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "🎁 Gift so‘rovlari yo‘q."
        )
        return

    for row in rows:
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"giftstatus:{row['id']}:approved"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"giftstatus:{row['id']}:rejected"
                )
            ],
            [
                InlineKeyboardButton(
                    "📦 Delivered",
                    callback_data=f"giftstatus:{row['id']}:delivered"
                )
            ]
        ]

        await update.message.reply_text(
            f"🎁 Gift #{row['id']}\n\n"
            f"👤 User: {row['user_id']}\n"
            f"🎁 {row['gift_name']}\n"
            f"⭐ {row['price']}\n"
            f"📌 {row['status']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def gift_status(update, context):
    query = update.callback_query

    await query.answer()

    try:
        _, request_id, status = query.data.split(":")
        request_id = int(request_id)
    except Exception:
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM gift_requests WHERE id = ?",
        (request_id,)
    )

    request = cur.fetchone()

    if not request:
        conn.close()
        return

    old_status = request["status"]

    if status == "approved":
        if old_status != "pending":
            conn.close()
            return

    elif status == "rejected":
        if old_status != "pending":
            conn.close()
            return

        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (
            request["price"],
            request["user_id"]
        ))

    elif status == "delivered":
        if old_status != "approved":
            conn.close()
            return

    cur.execute("""
        UPDATE gift_requests
        SET status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        status,
        datetime.now().isoformat(),
        request_id
    ))

    conn.commit()
    conn.close()

    await query.message.reply_text(
        f"✅ Gift #{request_id}: {status}"
    )


# =========================================================
# ADD ADMIN
# =========================================================

async def add_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/addadmin USER_ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo‘lishi kerak."
        )
        return

    if not get_user(user_id):
        await update.message.reply_text(
            "❌ User avval botni ishlatgan bo‘lishi kerak."
        )
        return

    add_admin(user_id)

    await update.message.reply_text(
        f"✅ {user_id} admin qilindi."
    )


# =========================================================
# REMOVE ADMIN
# =========================================================

async def remove_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/removeadmin USER_ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo‘lishi kerak."
        )
        return

    if remove_admin(user_id):
        await update.message.reply_text(
            f"✅ {user_id} adminlikdan olindi."
        )
    else:
        await update.message.reply_text(
            "❌ Ownerni olib tashlab bo‘lmaydi."
        )


# =========================================================
# ADD TASK
# =========================================================

async def add_task_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "task_username"

    await update.message.reply_text(
        "📢 Kanal username yuboring.\n\n"
        "Masalan: @mychannel"
    )


async def delete_task_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/deltask ID"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto‘g‘ri."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM channels WHERE id = ?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Vazifa o‘chirildi."
    )


# =========================================================
# ADD MANDATORY
# =========================================================

async def add_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "mandatory_id"

    await update.message.reply_text(
        "🔐 Kanal ID yuboring.\n\n"
        "Masalan:\n"
        "-1004425654134"
    )


async def delete_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "/delmandatory ID"
        )
        return

    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID noto‘g‘ri."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM mandatory_channels WHERE id = ?",
        (channel_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Majburiy kanal o‘chirildi."
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(update, context):
    user = update.effective_user
    text = update.message.text

    add_user(user)

    if not await check_mandatory(
        user.id,
        context
    ):
        await send_mandatory_message(
            update.message,
            context
        )
        return

    state = context.user_data.get("state")

    # Advertisement
    if state == "advertisement":
        await save_advertisement(
            update,
            context
        )
        return

    # =====================================================
    # ADMIN STATES
    # =====================================================

    if is_admin(user.id):

        if state == "task_username":

            username = text.strip()

            if not username.startswith("@"):
                username = "@" + username

            context.user_data["task_username"] = username
            context.user_data["state"] = "task_title"

            await update.message.reply_text(
                "📢 Kanal nomini yuboring."
            )
            return

        if state == "task_title":

            context.user_data["task_title"] = text.strip()
            context.user_data["state"] = "task_reward"

            await update.message.reply_text(
                "⭐ Rewardni yuboring.\n\n"
                "Masalan: 0.1"
            )
            return

        if state == "task_reward":

            try:
                reward = float(
                    text.replace(",", ".")
                )
            except ValueError:
                await update.message.reply_text(
                    "❌ Reward raqam bo‘lishi kerak."
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

            cur.execute("""
                INSERT INTO channels
                (username, title, reward, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                username,
                title,
                reward,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Vazifa qo‘shildi!\n\n"
                f"📢 {title}\n"
                f"🔗 {username}\n"
                f"⭐ {reward}"
            )
            return

        if state == "mandatory_id":

            channel_id = text.strip()

            try:
                chat = await context.bot.get_chat(
                    channel_id
                )
            except Exception:
                await update.message.reply_text(
                    "❌ Kanal topilmadi.\n\n"
                    "Bot kanalga admin ekanini tekshiring."
                )
                return

            if chat.type != "channel":
                await update.message.reply_text(
                    "❌ Bu channel emas."
                )
                return

            context.user_data["mandatory_id"] = channel_id
            context.user_data["mandatory_username"] = (
                chat.username or ""
            )
            context.user_data["mandatory_chat_title"] = (
                chat.title or ""
            )
            context.user_data["state"] = "mandatory_title"

            await update.message.reply_text(
                "📢 Kanal nomini yuboring."
            )
            return

        if state == "mandatory_title":

            context.user_data["mandatory_title"] = text.strip()
            context.user_data["state"] = "mandatory_link"

            await update.message.reply_text(
                "🔗 Kanal linkini yuboring."
            )
            return

        if state == "mandatory_link":

            channel_id = context.user_data.get(
                "mandatory_id"
            )

            username = context.user_data.get(
                "mandatory_username",
                ""
            )

            title = context.user_data.get(
                "mandatory_title"
            )

            invite_link = text.strip()

            conn = db()
            cur = conn.cursor()

            try:
                cur.execute("""
                    INSERT INTO mandatory_channels
                    (
                        channel_id,
                        username,
                        title,
                        invite_link,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    channel_id,
                    username,
                    title,
                    invite_link,
                    datetime.now().isoformat()
                ))

                conn.commit()

            except sqlite3.IntegrityError:
                conn.close()

                await update.message.reply_text(
                    "❌ Bu kanal allaqachon mavjud."
                )
                return

            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Majburiy kanal qo‘shildi!"
            )
            return

    # =====================================================
    # USER BUTTONS
    # =====================================================

    if text == "⭐ Stars":
        await stars_menu(
            update,
            context
        )
        return

    if text == "🎁 Gift":
        await gifts(
            update,
            context
        )
        return

    if text == "👥 Referral":
        await referral(
            update,
            context
        )
        return

    if text == "📊 Statistics":
        await statistics(
            update,
            context
        )
        return

    if text == "📜 Rules":
        await rules(
            update,
            context
        )
        return

    if text == "📢 Advertising":
        await advertising(
            update,
            context
        )
        return

    # =====================================================
    # ADMIN BUTTONS
    # =====================================================

    if text == "⚙️ Admin panel":

        if is_admin(user.id):
            await update.message.reply_text(
                "⚙️ Admin panel:",
                reply_markup=admin_menu()
            )
        return

    if text == "📊 Admin statistics":

        if is_admin(user.id):
            await admin_statistics(
                update,
                context
            )
        return

    if text == "👥 Users":

        if is_admin(user.id):
            await admin_users(
                update,
                context
            )
        return

    if text == "📝 Activity logs":

        if is_admin(user.id):
            await activity_logs(
                update,
                context
            )
        return

    if text == "👑 Admins":

        if is_admin(user.id):
            await admin_list(
                update,
                context
            )
        return

    if text == "🔐 Mandatory channels":

        if is_admin(user.id):
            await mandatory_channels(
                update,
                context
            )
        return

    if text == "📢 Task channels":

        if is_admin(user.id):
            await task_channels(
                update,
                context
            )
        return

    if text == "🎁 Gift requests":

        if is_admin(user.id):
            await gift_requests(
                update,
                context
            )
        return

    if text == "📣 Advertising requests":
        return

    if text == "⬅️ Back":

        await update.message.reply_text(
            "🏠 Asosiy menyu:",
            reply_markup=user_menu(user.id)
        )
        return

    await update.message.reply_text(
        "👇 Menyudan foydalaning.",
        reply_markup=user_menu(user.id)
    )


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def callback_handler(update, context):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # Mandatory
    if data == "mandatory:check":

        await query.answer()

        if await check_mandatory(
            user_id,
            context
        ):
            await query.edit_message_text(
                "✅ Barcha kanallarga obuna bo‘lgansiz!"
            )
        else:
            await query.answer(
                "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
                show_alert=True
            )

        return

    # Stars
    if data == "stars:tasks":
        await show_tasks(
            update,
            context
        )
        return

    if data == "stars:balance":
        await show_balance(
            update,
            context
        )
        return

    # Task
    if data.startswith("task:"):
        await check_task(
            update,
            context
        )
        return

    # Gift
    if data.startswith("giftconfirm:"):
        await confirm_gift(
            update,
            context
        )
        return

    if data.startswith("gift:"):
        await show_gift(
            update,
            context
        )
        return

    if data == "giftcancel":
        await query.answer()
        await query.edit_message_text(
            "❌ Bekor qilindi."
        )
        return

    # Gift status
    if data.startswith("giftstatus:"):

        if not is_admin(user_id):
            await query.answer(
                "❌ Admin emas.",
                show_alert=True
            )
            return

        await gift_status(
            update,
            context
        )
        return

    await query.answer()


# =========================================================
# ERROR
# =========================================================

async def error_handler(update, context):
    logger.exception(
        "BOT ERROR:",
        exc_info=context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    logger.info(
        "Starting FrostStars..."
    )

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # COMMANDS
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "addadmin",
            add_admin_command
        )
    )

    application.add_handler(
        CommandHandler(
            "removeadmin",
            remove_admin_command
        )
    )

    application.add_handler(
        CommandHandler(
            "addtask",
            add_task_command
        )
    )

    application.add_handler(
        CommandHandler(
            "deltask",
            delete_task_command
        )
    )

    application.add_handler(
        CommandHandler(
            "addmandatory",
            add_mandatory_command
        )
    )

    application.add_handler(
        CommandHandler(
            "delmandatory",
            delete_mandatory_command
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
            text_handler
        )
    )

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
