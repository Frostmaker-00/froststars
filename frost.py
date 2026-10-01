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

    # =====================================================
    # USERS
    # =====================================================

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

    # =====================================================
    # USERS MIGRATION
    # =====================================================
    # Eski starbot.db uchun.
    # Yetishmayotgan ustunlarni avtomatik qo'shadi.

    cur.execute("PRAGMA table_info(users)")

    existing_user_columns = {
        row["name"]
        for row in cur.fetchall()
    }

    if "referral_count" not in existing_user_columns:
        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN referral_count INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass

    if "referred_by" not in existing_user_columns:
        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN referred_by INTEGER DEFAULT NULL
            """)
        except sqlite3.OperationalError:
            pass

    if "username" not in existing_user_columns:
        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN username TEXT DEFAULT ''
            """)
        except sqlite3.OperationalError:
            pass

    if "first_name" not in existing_user_columns:
        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN first_name TEXT DEFAULT ''
            """)
        except sqlite3.OperationalError:
            pass

    if "balance" not in existing_user_columns:
        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN balance REAL DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass

    if "created_at" not in existing_user_columns:
        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN created_at TEXT
            """)
        except sqlite3.OperationalError:
            pass

    # =====================================================
    # COMPLETED TASKS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            created_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    # =====================================================
    # GIFT REQUESTS
    # =====================================================

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

    # =====================================================
    # TASK CHANNELS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
    """)

    # =====================================================
    # CHANNELS MIGRATION
    # =====================================================

    cur.execute("PRAGMA table_info(channels)")

    existing_columns = {
        row["name"]
        for row in cur.fetchall()
    }

    if "username" not in existing_columns:
        try:
            cur.execute("""
                ALTER TABLE channels
                ADD COLUMN username TEXT
            """)
        except sqlite3.OperationalError:
            pass

    if "title" not in existing_columns:
        try:
            cur.execute("""
                ALTER TABLE channels
                ADD COLUMN title TEXT
            """)
        except sqlite3.OperationalError:
            pass

    if "reward" not in existing_columns:
        try:
            cur.execute("""
                ALTER TABLE channels
                ADD COLUMN reward REAL DEFAULT 0.1
            """)
        except sqlite3.OperationalError:
            pass

    if "created_at" not in existing_columns:
        try:
            cur.execute("""
                ALTER TABLE channels
                ADD COLUMN created_at TEXT
            """)
        except sqlite3.OperationalError:
            pass

    # =====================================================
    # ADMINS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT
        )
    """)

    # =====================================================
    # ACTIVITY LOGS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT
        )
    """)

    # =====================================================
    # ADVERTISER REQUESTS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    # =====================================================
    # MANDATORY CHANNELS
    # =====================================================

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

    # =====================================================
    # MANDATORY CHANNELS MIGRATION
    # =====================================================

    cur.execute("PRAGMA table_info(mandatory_channels)")

    mandatory_columns = {
        row["name"]
        for row in cur.fetchall()
    }

    if "username" not in mandatory_columns:
        try:
            cur.execute("""
                ALTER TABLE mandatory_channels
                ADD COLUMN username TEXT DEFAULT ''
            """)
        except sqlite3.OperationalError:
            pass

    if "invite_link" not in mandatory_columns:
        try:
            cur.execute("""
                ALTER TABLE mandatory_channels
                ADD COLUMN invite_link TEXT DEFAULT ''
            """)
        except sqlite3.OperationalError:
            pass

    if "title" not in mandatory_columns:
        try:
            cur.execute("""
                ALTER TABLE mandatory_channels
                ADD COLUMN title TEXT
            """)
        except sqlite3.OperationalError:
            pass

    if "created_at" not in mandatory_columns:
        try:
            cur.execute("""
                ALTER TABLE mandatory_channels
                ADD COLUMN created_at TEXT
            """)
        except sqlite3.OperationalError:
            pass

    # =====================================================
    # OWNER
    # =====================================================

    cur.execute("""
        INSERT OR IGNORE INTO admins
        (user_id, added_at)
        VALUES (?, ?)
    """, (
        OWNER_ID,
        datetime.now().isoformat()
    ))

    # =====================================================
    # DEFAULT TASK CHANNELS
    # =====================================================

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

    logger.info("Database initialized successfully.")


# =========================================================
# USER FUNCTIONS
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
# ADMIN FUNCTIONS
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
# ACTIVITY LOG
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
# MENUS
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


def admin_menu():
    buttons = [
        ["📊 Admin statistics"],
        ["👥 Users", "📝 Activity logs"],
        ["👑 Admins", "🔐 Mandatory channels"],
        ["📢 Task channels", "🎁 Gift requests"],
        ["📣 Advertising requests"],
        ["⬅️ Back"],
    ]

    return ReplyKeyboardMarkup(
        buttons,
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

            status = member.status

            if status in (
                "member",
                "administrator",
                "creator"
            ):
                continue

            if (
                status == "restricted"
                and getattr(member, "is_member", False)
            ):
                continue

            return False

        except Exception as e:
            logger.warning(
                "Mandatory channel check error %s: %s",
                channel["channel_id"],
                e
            )

            continue

    return True


async def mandatory_message(update, context):
    channels = get_mandatory_channels()

    if not channels:
        return

    buttons = []

    for channel in channels:
        link = channel["invite_link"]

        if not link:
            username = channel["username"]

            if username:
                username = username.replace("@", "")
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

    if update.message:
        await update.message.reply_text(
            "🔐 Botdan foydalanish uchun quyidagi "
            "kanallarga obuna bo‘lishingiz kerak:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    add_user(user)

    if context.args:
        try:
            referrer_id = int(context.args[0])

            current_user = get_user(user.id)
            referrer = get_user(referrer_id)

            if (
                referrer_id != user.id
                and current_user
                and current_user["referred_by"] is None
                and referrer
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
                    f"Yangi referral: {user.id}"
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
        await mandatory_message(
            update,
            context
        )
        return

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "⭐ FrostStars botiga xush kelibsiz.\n\n"
        "Quyidagi menyudan foydalaning:",
        reply_markup=user_menu(user.id)
    )


# =========================================================
# STARS MENU
# =========================================================

async def send_stars_menu(message):
    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 Vazifalar",
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

    await message.reply_text(
        "⭐ Stars bo‘limi:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# TASK CHANNELS
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


async def show_task(update, context):
    query = update.callback_query

    await query.answer()

    channels = get_task_channels()

    if not channels:
        await query.edit_message_text(
            "Hozircha vazifalar mavjud emas."
        )
        return

    buttons = []

    for channel in channels:
        username = channel["username"] or ""
        username = username.replace("@", "")

        if not username:
            continue

        buttons.append([
            InlineKeyboardButton(
                f"📢 {channel['title']} +{channel['reward']} ⭐",
                url=f"https://t.me/{username}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                "✅ Tekshirish",
                callback_data=f"task:{channel['id']}"
            )
        ])

    await query.edit_message_text(
        "🎯 Kanallarga obuna bo‘ling va Stars oling:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def check_task(update, context):
    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    try:
        task_id = int(
            query.data.split(":")[1]
        )
    except Exception:
        await query.message.reply_text(
            "❌ Noto‘g‘ri vazifa."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM channels WHERE id = ?",
        (task_id,)
    )

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
        await query.message.reply_text(
            "❌ Vazifa topilmadi."
        )
        return

    if already:
        await query.message.reply_text(
            "⚠️ Siz bu vazifani oldin bajargansiz."
        )
        return

    username = channel["username"]

    try:
        member = await context.bot.get_chat_member(
            username,
            user_id
        )

        if member.status not in (
            "member",
            "administrator",
            "creator"
        ):
            await query.message.reply_text(
                "❌ Avval kanalga obuna bo‘ling."
            )
            return

    except Exception as e:
        logger.warning(
            "Task check error: %s",
            e
        )

        await query.message.reply_text(
            "❌ Kanalni tekshirib bo‘lmadi.\n"
            "Bot kanalga admin ekanini tekshiring."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO completed_tasks
        (user_id, task_id, created_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        task_id,
        datetime.now().isoformat()
    ))

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (
        channel["reward"],
        user_id
    ))

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        "task_completed",
        f"{channel['title']} +{channel['reward']}"
    )

    await query.message.reply_text(
        f"✅ Vazifa bajarildi!\n\n"
        f"💰 +{channel['reward']} ⭐ qo‘shildi."
    )


# =========================================================
# REFERRAL
# =========================================================

async def referral(update, context):
    user = update.effective_user
    row = get_user(user.id)

    if not row:
        add_user(user)
        row = get_user(user.id)

    bot = await context.bot.get_me()

    link = (
        f"https://t.me/{bot.username}?start={user.id}"
    )

    await update.message.reply_text(
        "👥 Referral tizimi\n\n"
        f"Har bir taklif uchun: ⭐ {REFERRAL_REWARD}\n\n"
        f"👤 Sizning referral soningiz: "
        f"{row['referral_count']}\n\n"
        f"🔗 Sizning linkingiz:\n{link}"
    )


# =========================================================
# STATISTICS
# =========================================================

async def statistics(update, context):
    user = update.effective_user
    row = get_user(user.id)

    if not row:
        add_user(user)
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
        "2. Bir vazifani qayta-qayta bajarib bo‘lmaydi.\n"
        "3. Soxta akkauntlardan foydalanish taqiqlanadi.\n"
        "4. Botdagi texnik xatolardan foydalanishga urinish taqiqlanadi.\n"
        "5. Sovg‘a olish uchun yetarli Stars bo‘lishi kerak."
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
    buttons = []

    for name, price in get_available_gifts():
        buttons.append([
            InlineKeyboardButton(
                f"{name} — ⭐ {price}",
                callback_data=f"gift:{price}:{name}"
            )
        ])

    await update.message.reply_text(
        "🎁 Sovg‘ani tanlang:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def show_gift(update, context):
    query = update.callback_query

    await query.answer()

    try:
        parts = query.data.split(":", 2)

        price = float(parts[1])
        name = parts[2]

    except Exception:
        await query.message.reply_text(
            "❌ Sovg‘a xatosi."
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
                "⬅️ Bekor qilish",
                callback_data="giftcancel"
            )
        ]
    ]

    await query.message.reply_text(
        f"🎁 {name}\n\n"
        f"💰 Narxi: ⭐ {price}\n\n"
        "Sotib olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirm_gift(update, context):
    query = update.callback_query

    await query.answer()

    try:
        parts = query.data.split(":", 2)

        price = float(parts[1])
        name = parts[2]

    except Exception:
        await query.message.reply_text(
            "❌ Xatolik."
        )
        return

    user_id = query.from_user.id
    row = get_user(user_id)

    if not row:
        await query.message.reply_text(
            "❌ Foydalanuvchi topilmadi."
        )
        return

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

    conn.commit()

    request_id = cur.lastrowid

    conn.close()

    log_activity(
        user_id,
        "gift_request",
        f"#{request_id} {name} {price}"
    )

    await query.message.reply_text(
        "✅ So‘rov qabul qilindi!\n\n"
        f"🎁 {name}\n"
        f"💰 ⭐ {price}\n"
        f"🆔 So‘rov: #{request_id}\n\n"
        "Admin so‘rovni ko‘rib chiqadi."
    )


# =========================================================
# ADMIN STATISTICS
# =========================================================

async def admin_statistics(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM users"
    )

    total_balance = cur.fetchone()[0]

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
        f"⭐ Umumiy balans: {total_balance:.2f}\n"
        f"🎁 Gift so‘rovlari: {gifts_count}\n"
        f"📣 Reklama so‘rovlari: {ads_count}"
    )


# =========================================================
# USERS
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

    if len(users) > 50:
        text += (
            "\n... faqat birinchi 50 ta ko‘rsatildi."
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
            "📝 Loglar hali yo‘q."
        )
        return

    text = "📝 Oxirgi loglar:\n\n"

    for row in rows:
        text += (
            f"#{row['id']} | "
            f"{row['user_id']} | "
            f"{row['action']}\n"
            f"{row['details']}\n"
            f"{row['created_at']}\n\n"
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

    text += (
        "Admin qo‘shish: /addadmin USER_ID\n"
        "Adminni olib tashlash: /removeadmin USER_ID"
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
        "Kanal qo‘shish: /addtask\n"
        "Kanal o‘chirish: /deltask ID"
    )

    await update.message.reply_text(text)


# =========================================================
# MANDATORY CHANNEL ADMIN
# =========================================================

async def mandatory_channels(update, context):
    channels = get_mandatory_channels()

    text = "🔐 Majburiy kanallar:\n\n"

    if not channels:
        text += "Hozircha kanal yo‘q.\n\n"

    for channel in channels:
        text += (
            f"🆔 DB ID: {channel['id']}\n"
            f"📌 Telegram ID: {channel['channel_id']}\n"
            f"📢 Nomi: {channel['title']}\n"
            f"🔗 Link: "
            f"{channel['invite_link'] or 'yo‘q'}\n\n"
        )

    text += (
        "➕ Qo‘shish: /addmandatory\n"
        "🗑 O‘chirish: /delmandatory ID"
    )

    await update.message.reply_text(text)


# =========================================================
# GIFT REQUESTS
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
                    callback_data=(
                        f"giftstatus:{row['id']}:approved"
                    )
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=(
                        f"giftstatus:{row['id']}:rejected"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "📦 Delivered",
                    callback_data=(
                        f"giftstatus:{row['id']}:delivered"
                    )
                )
            ]
        ]

        await update.message.reply_text(
            f"🎁 Gift request #{row['id']}\n\n"
            f"👤 User: {row['user_id']}\n"
            f"🎁 Gift: {row['gift_name']}\n"
            f"⭐ Price: {row['price']}\n"
            f"📌 Status: {row['status']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def gift_status(update, context):
    query = update.callback_query

    await query.answer()

    try:
        _, request_id, new_status = (
            query.data.split(":")
        )

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

        await query.message.reply_text(
            "❌ So‘rov topilmadi."
        )
        return

    old_status = request["status"]

    if new_status == "approved":

        if old_status != "pending":
            conn.close()

            await query.message.reply_text(
                "❌ Bu so‘rovni approve qilib bo‘lmaydi."
            )
            return

    elif new_status == "rejected":

        if old_status != "pending":
            conn.close()

            await query.message.reply_text(
                "❌ Bu so‘rovni reject qilib bo‘lmaydi."
            )
            return

        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (
            request["price"],
            request["user_id"]
        ))

    elif new_status == "delivered":

        if old_status != "approved":
            conn.close()

            await query.message.reply_text(
                "❌ Avval approve qiling."
            )
            return

    else:
        conn.close()
        return

    cur.execute("""
        UPDATE gift_requests
        SET status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        new_status,
        datetime.now().isoformat(),
        request_id
    ))

    conn.commit()
    conn.close()

    log_activity(
        query.from_user.id,
        "gift_status",
        f"#{request_id} -> {new_status}"
    )

    await query.message.reply_text(
        f"✅ So‘rov #{request_id} statusi: "
        f"{new_status}"
    )


# =========================================================
# ADVERTISING
# =========================================================

async def advertising(update, context):
    context.user_data["state"] = "advertisement"

    await update.message.reply_text(
        "📣 Reklama berish uchun reklamangiz haqida "
        "ma'lumot yuboring.\n\n"
        "Masalan:\n"
        "• Reklama matni\n"
        "• Kanal username\n"
        "• Necha kun reklama qilinishi"
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

    conn.commit()

    request_id = cur.lastrowid

    conn.close()

    context.user_data.pop(
        "state",
        None
    )

    log_activity(
        user.id,
        "advertisement_request",
        f"#{request_id}"
    )

    await update.message.reply_text(
        "✅ Reklama so‘rovingiz qabul qilindi.\n\n"
        f"🆔 So‘rov: #{request_id}\n"
        "Admin siz bilan bog‘lanadi."
    )


async def advertising_requests(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM advertiser_requests
        ORDER BY id DESC
        LIMIT 30
    """)

    rows = cur.fetchall()

    conn.close()

    if not rows:
        await update.message.reply_text(
            "📣 Reklama so‘rovlari yo‘q."
        )
        return

    text = "📣 Reklama so‘rovlari:\n\n"

    for row in rows:
        text += (
            f"#{row['id']}\n"
            f"👤 User: {row['user_id']}\n"
            f"📌 Status: {row['status']}\n"
            f"📝 {row['text']}\n\n"
        )

    await update.message.reply_text(text)


# =========================================================
# ADMIN COMMANDS
# =========================================================

async def add_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Format:\n/addadmin USER_ID"
        )
        return

    try:
        user_id = int(context.args[0])

    except ValueError:
        await update.message.reply_text(
            "❌ USER_ID raqam bo‘lishi kerak."
        )
        return

    if not get_user(user_id):
        await update.message.reply_text(
            "❌ Bu user botdan foydalanmagan."
        )
        return

    add_admin(user_id)

    await update.message.reply_text(
        f"✅ {user_id} admin qilindi."
    )


async def remove_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Format:\n/removeadmin USER_ID"
        )
        return

    try:
        user_id = int(context.args[0])

    except ValueError:
        await update.message.reply_text(
            "❌ USER_ID raqam bo‘lishi kerak."
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

    context.user_data["state"] = (
        "task_add_username"
    )

    await update.message.reply_text(
        "📢 Vazifa kanali username'ini yuboring.\n\n"
        "Masalan:\n"
        "@mychannel"
    )


async def delete_task_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Format:\n/deltask ID"
        )
        return

    try:
        channel_id = int(context.args[0])

    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo‘lishi kerak."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM channels WHERE id = ?",
        (channel_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Vazifa kanali o‘chirildi."
    )


# =========================================================
# ADD MANDATORY CHANNEL
# =========================================================

async def add_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = (
        "mandatory_add_id"
    )

    await update.message.reply_text(
        "🔐 Majburiy kanal qo‘shish.\n\n"
        "1️⃣ Telegram kanal ID sini yuboring.\n\n"
        "Masalan:\n"
        "-1001234567890\n\n"
        "Bot kanalga ADMIN bo‘lishi kerak."
    )


async def delete_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Format:\n/delmandatory ID"
        )
        return

    try:
        channel_id = int(context.args[0])

    except ValueError:
        await update.message.reply_text(
            "❌ ID raqam bo‘lishi kerak."
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
        await mandatory_message(
            update,
            context
        )
        return

    state = context.user_data.get("state")

    # =====================================================
    # ADVERTISEMENT
    # =====================================================

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

        # -------------------------------------------------
        # TASK USERNAME
        # -------------------------------------------------

        if state == "task_add_username":

            username = text.strip()

            if not username.startswith("@"):
                username = "@" + username

            context.user_data[
                "task_username"
            ] = username

            context.user_data[
                "state"
            ] = "task_add_title"

            await update.message.reply_text(
                "📢 Kanal nomini yuboring."
            )

            return

        # -------------------------------------------------
        # TASK TITLE
        # -------------------------------------------------

        if state == "task_add_title":

            title = text.strip()

            context.user_data[
                "task_title"
            ] = title

            context.user_data[
                "state"
            ] = "task_add_reward"

            await update.message.reply_text(
                "⭐ Bitta vazifa uchun rewardni yuboring.\n\n"
                "Masalan: 0.1"
            )

            return

        # -------------------------------------------------
        # TASK REWARD
        # -------------------------------------------------

        if state == "task_add_reward":

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

            try:
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

                await update.message.reply_text(
                    "✅ Vazifa kanali qo‘shildi!\n\n"
                    f"📢 {title}\n"
                    f"🔗 {username}\n"
                    f"⭐ {reward}"
                )

            except sqlite3.IntegrityError:
                await update.message.reply_text(
                    "❌ Bu kanal allaqachon mavjud."
                )

            finally:
                conn.close()

            context.user_data.pop(
                "state",
                None
            )

            context.user_data.pop(
                "task_username",
                None
            )

            context.user_data.pop(
                "task_title",
                None
            )

            return

        # =================================================
        # MANDATORY CHANNEL ID
        # =================================================

        if state == "mandatory_add_id":

            channel_id = text.strip()

            if not channel_id.startswith("-100"):
                await update.message.reply_text(
                    "❌ Kanal ID noto‘g‘ri.\n\n"
                    "Odatda kanal ID -100 bilan boshlanadi."
                )
                return

            try:
                chat = await context.bot.get_chat(
                    channel_id
                )

                if chat.type != "channel":
                    await update.message.reply_text(
                        "❌ Bu ID Telegram CHANNEL emas."
                    )
                    return

            except Exception as e:
                logger.warning(
                    "get_chat error: %s",
                    e
                )

                await update.message.reply_text(
                    "❌ Kanal topilmadi.\n\n"
                    "Tekshiring:\n"
                    "• ID to‘g‘rimi?\n"
                    "• Bot kanalga adminmi?"
                )
                return

            context.user_data[
                "mandatory_channel_id"
            ] = channel_id

            context.user_data[
                "mandatory_username"
            ] = chat.username or ""

            context.user_data[
                "state"
            ] = "mandatory_add_title"

            await update.message.reply_text(
                "✅ Kanal topildi.\n\n"
                "Endi kanal nomini yuboring.\n\n"
                f"Telegram nomi: {chat.title}"
            )

            return

        # =================================================
        # MANDATORY TITLE
        # =================================================

        if state == "mandatory_add_title":

            title = text.strip()

            context.user_data[
                "mandatory_title"
            ] = title

            context.user_data[
                "state"
            ] = "mandatory_add_link"

            await update.message.reply_text(
                "🔗 Endi kanalga kirish linkini yuboring.\n\n"
                "Public kanal:\n"
                "https://t.me/username\n\n"
                "Private kanal:\n"
                "https://t.me/+xxxx"
            )

            return

        # =================================================
        # MANDATORY LINK
        # =================================================

        if state == "mandatory_add_link":

            invite_link = text.strip()

            channel_id = context.user_data.get(
                "mandatory_channel_id"
            )

            username = context.user_data.get(
                "mandatory_username",
                ""
            )

            title = context.user_data.get(
                "mandatory_title"
            )

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

                await update.message.reply_text(
                    "✅ Majburiy kanal qo‘shildi!\n\n"
                    f"🆔 ID: {channel_id}\n"
                    f"📢 Nomi: {title}\n"
                    f"🔗 Link: {invite_link}\n\n"
                    "⚠️ Bot kanalga admin ekanini tekshiring."
                )

            except sqlite3.IntegrityError:
                await update.message.reply_text(
                    "❌ Bu kanal allaqachon qo‘shilgan."
                )

            finally:
                conn.close()

            context.user_data.pop(
                "state",
                None
            )

            context.user_data.pop(
                "mandatory_channel_id",
                None
            )

            context.user_data.pop(
                "mandatory_username",
                None
            )

            context.user_data.pop(
                "mandatory_title",
                None
            )

            return

    # =====================================================
    # USER MENU
    # =====================================================

    if text == "⭐ Stars":
        await send_stars_menu(
            update.message
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
    # ADMIN MENU
    # =====================================================

    if text == "⚙️ Admin panel":

        if not is_admin(user.id):
            await update.message.reply_text(
                "❌ Siz admin emassiz."
            )
            return

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

        if is_admin(user.id):
            await advertising_requests(
                update,
                context
            )

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

    # =====================================================
    # MANDATORY CHECK
    # =====================================================

    if data == "mandatory:check":

        await query.answer()

        if await check_mandatory(
            user_id,
            context
        ):
            await query.message.reply_text(
                "✅ Barcha majburiy kanallarga "
                "obuna bo‘lgansiz!\n\n"
                "Botdan foydalanishingiz mumkin.",
                reply_markup=user_menu(user_id)
            )

        else:
            await query.message.reply_text(
                "❌ Hali barcha kanallarga "
                "obuna bo‘lmagansiz."
            )

        return

    # =====================================================
    # STARS
    # =====================================================

    if data == "stars:tasks":
        await show_task(
            update,
            context
        )
        return

    if data == "stars:balance":

        await query.answer()

        row = get_user(user_id)

        if not row:
            await query.message.reply_text(
                "❌ Foydalanuvchi topilmadi."
            )
            return

        await query.message.reply_text(
            "⭐ Sizning balansingiz:\n\n"
            f"⭐ {row['balance']:.2f}"
        )

        return

    # =====================================================
    # TASKS
    # =====================================================

    if data.startswith("task:"):
        await check_task(
            update,
            context
        )
        return

    # =====================================================
    # GIFTS
    # =====================================================

    if data.startswith("gift:"):
        await show_gift(
            update,
            context
        )
        return

    if data.startswith("giftconfirm:"):
        await confirm_gift(
            update,
            context
        )
        return

    if data == "giftcancel":

        await query.answer()

        await query.message.reply_text(
            "❌ Bekor qilindi."
        )

        return

    # =====================================================
    # GIFT STATUS
    # =====================================================

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
# ERROR HANDLER
# =========================================================

async def error_handler(update, context):
    logger.error(
        "Unhandled error: %s",
        context.error,
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

    # =====================================================
    # COMMANDS
    # =====================================================

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

    # =====================================================
    # CALLBACKS
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # =====================================================
    # TEXT
    # =====================================================

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
        "✅ FROSTSTARS BOT IS RUNNING!"
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
