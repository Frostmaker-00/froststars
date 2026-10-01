import os
import sqlite3
import logging
from datetime import datetime, timedelta
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

# Vazifa bajarilgandan keyin kanalda qolish muddati
SUBSCRIPTION_DAYS = 2


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
    # COMPLETED TASKS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            reward REAL DEFAULT 0,
            completed_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    # =====================================================
    # TASK SUBSCRIPTIONS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            subscribed_at TEXT,
            expires_at TEXT,
            last_checked_at TEXT,
            valid INTEGER DEFAULT 1,
            UNIQUE(user_id, task_id)
        )
    """)

    # =====================================================
    # GIFTS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 1,
            emoji TEXT DEFAULT '🎁',
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    # =====================================================
    # GIFT REQUESTS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            gift_id INTEGER,
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
    # ADVERTISING REQUESTS
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

    default_channels = [
        (
            "@Cossmoss_00",
            "Cossmoss",
            DEFAULT_TASK_REWARD
        ),
        (
            "@PromptLab_UZ",
            "PromptLab UZ",
            DEFAULT_TASK_REWARD
        ),
    ]

    for username, title, reward in default_channels:

        cur.execute("""
            SELECT id
            FROM channels
            WHERE username = ?
        """, (username,))

        if not cur.fetchone():

            cur.execute("""
                INSERT INTO channels
                (
                    username,
                    title,
                    reward,
                    created_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                username,
                title,
                reward,
                datetime.now().isoformat()
            ))

    # =====================================================
    # DEFAULT GIFTS
    # =====================================================

    default_gifts = [
        ("❤️", "Heart", 5),
        ("🧸", "Teddy Bear", 10),
        ("🌹", "Rose", 15),
        ("🌷", "Tulip", 20),
        ("💐", "Bouquet", 25),
        ("🎂", "Cake", 30),
        ("🎁", "Gift Box", 35),
        ("💎", "Diamond", 50),
        ("👑", "Crown", 75),
        ("🚀", "Rocket", 100),
    ]

    for emoji, name, price in default_gifts:

        cur.execute("""
            SELECT id
            FROM gifts
            WHERE name = ?
        """, (name,))

        if not cur.fetchone():

            cur.execute("""
                INSERT INTO gifts
                (
                    name,
                    price,
                    emoji,
                    active,
                    created_at
                )
                VALUES (?, ?, ?, 1, ?)
            """, (
                name,
                price,
                emoji,
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

    cur.execute("""
        SELECT *
        FROM users
        WHERE user_id = ?
    """, (user_id,))

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

    cur.execute("""
        SELECT 1
        FROM admins
        WHERE user_id = ?
    """, (user_id,))

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

    cur.execute("""
        DELETE FROM admins
        WHERE user_id = ?
    """, (user_id,))

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
        (
            user_id,
            action,
            details,
            created_at
        )
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
        ["⭐ Stars", "🎁 Gift olish"],
        ["👥 Referral", "💰 Balans"],
        ["📜 Qoidalar", "📢 Reklama"],
    ]

    if is_admin(user_id):
        buttons.append(["⚙️ Admin panel"])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True
    )


def admin_menu():

    buttons = [
        ["📊 Admin statistikasi"],
        ["👥 Foydalanuvchilar", "📝 Activity logs"],
        ["👑 Adminlar", "🔐 Majburiy kanallar"],
        ["📢 Vazifa kanallari", "🎁 Giftlar"],
        ["📦 Gift so‘rovlari"],
        ["📣 Reklama so‘rovlari"],
        ["⬅️ Orqaga"],
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
                "Mandatory channel error: %s",
                e
            )

            continue

    return True


async def send_mandatory_message(update, context):

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
            callback_data="mandatory_check"
        )
    ])

    text = (
        "🔐 Botdan foydalanish uchun "
        "quyidagi kanallarga obuna bo‘ling:"
    )

    if update.message:

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif update.callback_query:

        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )


# =========================================================
# START
# =========================================================

async def start(update, context):

    user = update.effective_user

    add_user(user)

    # -----------------------------------------------------
    # REFERRAL
    # -----------------------------------------------------

    if context.args:

        try:

            referrer_id = int(context.args[0])

            current_user = get_user(user.id)
            referrer = get_user(referrer_id)

            if (
                referrer
                and current_user
                and referrer_id != user.id
                and current_user["referred_by"] is None
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

    # -----------------------------------------------------
    # MANDATORY
    # -----------------------------------------------------

    if not await check_mandatory(
        user.id,
        context
    ):

        await send_mandatory_message(
            update,
            context
        )

        return

    # -----------------------------------------------------
    # MAIN MENU
    # -----------------------------------------------------

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "⭐ FrostStars botiga xush kelibsiz.\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=user_menu(user.id)
    )


# =========================================================
# STARS MENU
# =========================================================

async def stars_menu(update, context):

    query = update.callback_query

    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 Vazifalar",
                callback_data="task_next"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="balance"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Orqaga",
                callback_data="main_menu"
            )
        ]
    ]

    await query.edit_message_text(
        "⭐ Stars bo‘limi",
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


def get_next_task(user_id):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.*
        FROM channels c
        WHERE NOT EXISTS (
            SELECT 1
            FROM completed_tasks ct
            WHERE ct.user_id = ?
              AND ct.task_id = c.id
        )
        ORDER BY c.id ASC
        LIMIT 1
    """, (user_id,))

    row = cur.fetchone()

    conn.close()

    return row


async def show_next_task(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    task = get_next_task(user_id)

    if not task:

        keyboard = [[
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="balance"
            )
        ]]

        await query.edit_message_text(
            "🎉 Siz barcha mavjud vazifalarni "
            "bajarib bo‘lgansiz!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    username = task["username"].replace("@", "")

    keyboard = [
        [
            InlineKeyboardButton(
                f"📢 {task['title']}",
                url=f"https://t.me/{username}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Obunani tekshirish",
                callback_data=f"task_check:{task['id']}"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="balance"
            )
        ]
    ]

    text = (
        "🎯 Yangi vazifa\n\n"
        f"📢 Kanal: {task['title']}\n"
        f"⭐ Mukofot: +{task['reward']}\n\n"
        "1️⃣ Kanalga obuna bo‘ling\n"
        "2️⃣ Obunani tekshirish tugmasini bosing\n"
        "3️⃣ Mukofotni oling\n\n"
        f"⚠️ Mukofot olingandan keyin kanalni "
        f"{SUBSCRIPTION_DAYS} kun tark etmang."
    )

    try:

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception:

        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# =========================================================
# CHECK TASK
# =========================================================

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

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM channels
        WHERE id = ?
    """, (task_id,))

    task = cur.fetchone()

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

    if not task:

        await query.answer(
            "❌ Vazifa topilmadi.",
            show_alert=True
        )

        return

    if already:

        await query.answer(
            "⚠️ Bu vazifani allaqachon bajargansiz.",
            show_alert=True
        )

        return

    username = task["username"]

    # -----------------------------------------------------
    # TELEGRAM OBUNANI TEKSHIRISH
    # -----------------------------------------------------

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

            await query.answer(
                "❌ Avval kanalga obuna bo‘ling.",
                show_alert=True
            )

            return

    except Exception as e:

        logger.warning(
            "Task check error: %s",
            e
        )

        await query.answer(
            "❌ Kanalni tekshirib bo‘lmadi. "
            "Bot kanalga admin ekanini tekshiring.",
            show_alert=True
        )

        return

    # -----------------------------------------------------
    # REWARD
    # -----------------------------------------------------

    now = datetime.now()

    expires = now + timedelta(
        days=SUBSCRIPTION_DAYS
    )

    conn = db()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO completed_tasks
            (
                user_id,
                task_id,
                reward,
                completed_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            task_id,
            task["reward"],
            now.isoformat()
        ))

        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (
            task["reward"],
            user_id
        ))

        cur.execute("""
            INSERT INTO task_subscriptions
            (
                user_id,
                task_id,
                subscribed_at,
                expires_at,
                last_checked_at,
                valid
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            user_id,
            task_id,
            now.isoformat(),
            expires.isoformat(),
            now.isoformat()
        ))

        conn.commit()

    except sqlite3.IntegrityError:

        conn.rollback()
        conn.close()

        await query.answer(
            "⚠️ Bu vazifa allaqachon bajarilgan.",
            show_alert=True
        )

        return

    except Exception as e:

        conn.rollback()
        conn.close()

        logger.error(
            "Reward database error: %s",
            e
        )

        await query.answer(
            "❌ Mukofot berishda xatolik.",
            show_alert=True
        )

        return

    conn.close()

    log_activity(
        user_id,
        "task_completed",
        f"{task['title']} +{task['reward']}"
    )

    # -----------------------------------------------------
    # ESKI XABARNI O‘CHIRISH
    # -----------------------------------------------------

    try:

        await query.message.delete()

    except Exception as e:

        logger.warning(
            "Message delete error: %s",
            e
        )

    # -----------------------------------------------------
    # KEYINGI VAZIFA
    # -----------------------------------------------------

    next_task = get_next_task(user_id)

    keyboard = []

    if next_task:

        keyboard.append([
            InlineKeyboardButton(
                "➡️ Keyingi vazifa",
                callback_data="task_next"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "💰 Balans",
            callback_data="balance"
        )
    ])

    text = (
        "🎉 Vazifa bajarildi!\n\n"
        f"📢 {task['title']}\n"
        f"⭐ +{task['reward']} Stars\n\n"
        "💰 Mukofot balansingizga qo‘shildi.\n\n"
        f"⚠️ Kanalda {SUBSCRIPTION_DAYS} kun "
        "qolishingiz kerak."
    )

    if not next_task:

        text += (
            "\n\n🎉 Hozircha boshqa vazifalar yo‘q."
        )

    await context.bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# 2-DAY SUBSCRIPTION CHECK
# =========================================================

async def check_two_day_subscriptions(
    user_id,
    context
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            ts.*,
            c.username,
            c.title
        FROM task_subscriptions ts
        JOIN channels c
            ON c.id = ts.task_id
        WHERE ts.user_id = ?
          AND ts.valid = 1
    """, (user_id,))

    subscriptions = cur.fetchall()

    conn.close()

    for sub in subscriptions:

        try:

            expires = datetime.fromisoformat(
                sub["expires_at"]
            )

        except Exception:

            continue

        # -------------------------------------------------
        # 2 KUN TUGADI
        # -------------------------------------------------

        if datetime.now() >= expires:

            conn = db()
            cur = conn.cursor()

            cur.execute("""
                UPDATE task_subscriptions
                SET valid = 0,
                    last_checked_at = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                sub["id"]
            ))

            conn.commit()
            conn.close()

            continue

        # -------------------------------------------------
        # OBUNANI TEKSHIRISH
        # -------------------------------------------------

        try:

            username = sub["username"]

            if not username:
                continue

            member = await context.bot.get_chat_member(
                username,
                user_id
            )

            if member.status in (
                "member",
                "administrator",
                "creator"
            ):

                conn = db()
                cur = conn.cursor()

                cur.execute("""
                    UPDATE task_subscriptions
                    SET last_checked_at = ?
                    WHERE id = ?
                """, (
                    datetime.now().isoformat(),
                    sub["id"]
                ))

                conn.commit()
                conn.close()

                continue

            # ---------------------------------------------
            # KANALDAN CHIQIB KETGAN
            # ---------------------------------------------

            conn = db()
            cur = conn.cursor()

            cur.execute("""
                UPDATE task_subscriptions
                SET valid = 0,
                    last_checked_at = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                sub["id"]
            ))

            conn.commit()
            conn.close()

            try:

                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "⚠️ Siz vazifa kanalidan "
                        "chiqib ketdingiz.\n\n"
                        f"📢 {sub['title']}\n\n"
                        "2 kunlik obuna sharti buzildi."
                    )
                )

            except Exception as e:

                logger.warning(
                    "Notification error: %s",
                    e
                )

        except Exception as e:

            logger.warning(
                "Subscription check error: %s",
                e
            )

            continue


# =========================================================
# BALANCE
# =========================================================

async def show_balance(update, context):

    query = update.callback_query

    await query.answer()

    row = get_user(
        query.from_user.id
    )

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Stars",
            callback_data="stars_menu"
        )
    ]]

    await query.edit_message_text(
        "💰 Sizning balansingiz:\n\n"
        f"⭐ {row['balance']:.2f} Stars",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def balance_message(update, context):

    row = get_user(
        update.effective_user.id
    )

    await update.message.reply_text(
        "💰 Sizning balansingiz:\n\n"
        f"⭐ {row['balance']:.2f} Stars"
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
        "🔗 Sizning referral linkingiz:\n"
        f"{link}"
    )


# =========================================================
# RULES
# =========================================================

async def rules(update, context):

    await update.message.reply_text(
        "📜 FrostStars qoidalari\n\n"
        "1. Vazifalarni halol bajaring.\n"
        "2. Har bir vazifa faqat bir marta bajariladi.\n"
        "3. Vazifa rewardini olgandan keyin kanalni "
        f"{SUBSCRIPTION_DAYS} kun tark etmang.\n"
        "4. Soxta akkauntlardan foydalanish taqiqlanadi.\n"
        "5. Botdagi texnik xatolardan foydalanish taqiqlanadi.\n"
        "6. Gift olish uchun yetarli Stars bo‘lishi kerak."
    )


# =========================================================
# GIFTS
# =========================================================

def get_gifts():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM gifts
        WHERE active = 1
        ORDER BY price ASC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


async def gifts_menu(update, context):

    gifts = get_gifts()

    if not gifts:

        await update.message.reply_text(
            "🎁 Hozircha giftlar mavjud emas."
        )

        return

    buttons = []

    for gift in gifts:

        buttons.append([
            InlineKeyboardButton(
                f"{gift['emoji']} {gift['name']} — "
                f"⭐ {gift['price']}",
                callback_data=f"gift:{gift['id']}"
            )
        ])

    await update.message.reply_text(
        "🎁 Gift olish\n\n"
        "O‘zingizga kerakli giftni tanlang:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================================================
# SHOW GIFT
# =========================================================

async def show_gift(update, context):

    query = update.callback_query

    await query.answer()

    try:

        gift_id = int(
            query.data.split(":")[1]
        )

    except Exception:

        await query.answer(
            "❌ Gift xatosi.",
            show_alert=True
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM gifts
        WHERE id = ?
          AND active = 1
    """, (gift_id,))

    gift = cur.fetchone()

    conn.close()

    if not gift:

        await query.answer(
            "❌ Gift topilmadi.",
            show_alert=True
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Olish",
                callback_data=f"gift_confirm:{gift['id']}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Bekor qilish",
                callback_data="gift_cancel"
            )
        ]
    ]

    await query.edit_message_text(
        f"{gift['emoji']} {gift['name']}\n\n"
        f"💰 Narxi: ⭐ {gift['price']}\n\n"
        "Ushbu giftni olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# CONFIRM GIFT
# =========================================================

async def confirm_gift(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    try:

        gift_id = int(
            query.data.split(":")[1]
        )

    except Exception:

        await query.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM gifts
        WHERE id = ?
          AND active = 1
    """, (gift_id,))

    gift = cur.fetchone()

    conn.close()

    if not gift:

        await query.answer(
            "❌ Gift topilmadi.",
            show_alert=True
        )

        return

    user = get_user(user_id)

    if user["balance"] < gift["price"]:

        await query.answer(
            "❌ Balansingiz yetarli emas.",
            show_alert=True
        )

        return

    # -----------------------------------------------------
    # PUL AYIRISH
    # -----------------------------------------------------

    change_balance(
        user_id,
        -gift["price"]
    )

    now = datetime.now().isoformat()

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO gift_requests
        (
            user_id,
            gift_id,
            gift_name,
            price,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, 'pending', ?, ?)
    """, (
        user_id,
        gift["id"],
        f"{gift['emoji']} {gift['name']}",
        gift["price"],
        now,
        now
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        "gift_request",
        f"#{request_id} {gift['name']}"
    )

    await query.edit_message_text(
        "✅ Gift so‘rovi qabul qilindi!\n\n"
        f"{gift['emoji']} {gift['name']}\n"
        f"⭐ {gift['price']}\n"
        f"🆔 So‘rov: #{request_id}\n\n"
        "Admin so‘rovni ko‘rib chiqadi."
    )


# =========================================================
# CANCEL GIFT
# =========================================================

async def cancel_gift(update, context):

    query = update.callback_query

    await query.answer()

    await query.edit_message_text(
        "❌ Gift olish bekor qilindi."
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
        "Kanal: @channel\n"
        "Reklama matni: ...\n"
        "Muddat: 3 kun"
    )


async def save_advertisement(update, context):

    user = update.effective_user

    text = update.message.text

    conn = db()
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

    log_activity(
        user.id,
        "advertisement_request",
        f"#{request_id}"
    )

    await update.message.reply_text(
        "✅ Reklama so‘rovingiz qabul qilindi.\n\n"
        f"🆔 So‘rov: #{request_id}"
    )


# =========================================================
# ADMIN STATISTICS
# =========================================================

async def admin_statistics(update, context):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM users
    """)

    users = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(balance), 0)
        FROM users
    """)

    total_balance = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM completed_tasks
    """)

    completed = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM gift_requests
    """)

    gifts = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM advertiser_requests
    """)

    ads = cur.fetchone()[0]

    conn.close()

    await update.message.reply_text(
        "📊 Admin statistikasi\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"⭐ Umumiy balans: {total_balance:.2f}\n"
        f"🎯 Bajarilgan vazifalar: {completed}\n"
        f"🎁 Gift so‘rovlari: {gifts}\n"
        f"📢 Reklama so‘rovlari: {ads}"
    )


# =========================================================
# ADMIN USERS
# =========================================================

async def admin_users(update, context):

    users = get_all_users()

    if not users:

        await update.message.reply_text(
            "👥 Foydalanuvchilar yo‘q."
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
            f"👤 {user['first_name']}\n"
            f"🔗 {username}\n"
            f"⭐ {user['balance']:.2f}\n"
            f"👥 Ref: {user['referral_count']}\n\n"
        )

    await update.message.reply_text(text)


# =========================================================
# ACTIVITY
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
            "📝 Activity logs yo‘q."
        )

        return

    text = "📝 Oxirgi activity:\n\n"

    for row in rows:

        text += (
            f"#{row['id']}\n"
            f"👤 {row['user_id']}\n"
            f"⚙️ {row['action']}\n"
            f"📝 {row['details']}\n"
            f"🕐 {row['created_at']}\n\n"
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
        "/addadmin USER_ID\n"
        "/removeadmin USER_ID"
    )

    await update.message.reply_text(text)


# =========================================================
# TASK CHANNELS ADMIN
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
        "/addtask\n"
        "/deltask ID"
    )

    await update.message.reply_text(text)


# =========================================================
# ADD TASK
# =========================================================

async def add_task_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "task_username"

    await update.message.reply_text(
        "📢 Kanal username yuboring.\n\n"
        "Masalan:\n"
        "@mychannel"
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

        channel_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ ID raqam bo‘lishi kerak."
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM channels
        WHERE id = ?
    """, (channel_id,))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Vazifa kanali o‘chirildi."
    )


# =========================================================
# GIFTS ADMIN
# =========================================================

async def admin_gifts(update, context):

    gifts = get_gifts()

    text = "🎁 Giftlar:\n\n"

    for gift in gifts:

        text += (
            f"🆔 {gift['id']}\n"
            f"{gift['emoji']} {gift['name']}\n"
            f"⭐ {gift['price']}\n\n"
        )

    text += (
        "➕ Gift qo‘shish: /addgift\n"
        "✏️ Narx o‘zgartirish: /editgift ID PRICE\n"
        "🗑 O‘chirish: /delgift ID"
    )

    await update.message.reply_text(text)


async def add_gift_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "gift_name"

    await update.message.reply_text(
        "🎁 Gift emoji va nomini yuboring.\n\n"
        "Masalan:\n"
        "💎 Diamond"
    )


async def edit_gift_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:

        await update.message.reply_text(
            "/editgift ID PRICE\n\n"
            "Masalan:\n"
            "/editgift 1 25"
        )

        return

    try:

        gift_id = int(context.args[0])
        price = float(
            context.args[1].replace(",", ".")
        )

    except ValueError:

        await update.message.reply_text(
            "❌ ID yoki narx noto‘g‘ri."
        )

        return

    if price <= 0:

        await update.message.reply_text(
            "❌ Narx 0 dan katta bo‘lishi kerak."
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE gifts
        SET price = ?
        WHERE id = ?
    """, (
        price,
        gift_id
    ))

    changed = cur.rowcount

    conn.commit()
    conn.close()

    if changed:

        await update.message.reply_text(
            f"✅ Gift narxi ⭐ {price} qilib o‘zgartirildi."
        )

    else:

        await update.message.reply_text(
            "❌ Gift topilmadi."
        )


async def delete_gift_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    if not context.args:

        await update.message.reply_text(
            "/delgift ID"
        )

        return

    try:

        gift_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ ID noto‘g‘ri."
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE gifts
        SET active = 0
        WHERE id = ?
    """, (gift_id,))

    changed = cur.rowcount

    conn.commit()
    conn.close()

    if changed:

        await update.message.reply_text(
            "✅ Gift o‘chirildi."
        )

    else:

        await update.message.reply_text(
            "❌ Gift topilmadi."
        )


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
                    callback_data=f"gift_status:{row['id']}:approved"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"gift_status:{row['id']}:rejected"
                )
            ],
            [
                InlineKeyboardButton(
                    "📦 Delivered",
                    callback_data=f"gift_status:{row['id']}:delivered"
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

        _, request_id, status = query.data.split(":")

        request_id = int(request_id)

    except Exception:

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM gift_requests
        WHERE id = ?
    """, (request_id,))

    request = cur.fetchone()

    if not request:

        conn.close()

        await query.message.reply_text(
            "❌ So‘rov topilmadi."
        )

        return

    old_status = request["status"]

    if status == "approved":

        if old_status != "pending":

            conn.close()

            await query.message.reply_text(
                "❌ Bu so‘rov approve qilinmaydi."
            )

            return

    elif status == "rejected":

        if old_status != "pending":

            conn.close()

            await query.message.reply_text(
                "❌ Bu so‘rov reject qilinmaydi."
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

    elif status == "delivered":

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
        status,
        datetime.now().isoformat(),
        request_id
    ))

    conn.commit()
    conn.close()

    await query.message.reply_text(
        f"✅ #{request_id} → {status}"
    )


# =========================================================
# MANDATORY ADMIN
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
            f"📢 {channel['title']}\n"
            f"🔗 {channel['invite_link']}\n\n"
        )

    text += (
        "/addmandatory\n"
        "/delmandatory ID"
    )

    await update.message.reply_text(text)


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

        channel_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ ID noto‘g‘ri."
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM mandatory_channels
        WHERE id = ?
    """, (channel_id,))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Majburiy kanal o‘chirildi."
    )


# =========================================================
# ADVERTISING REQUESTS ADMIN
# =========================================================

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
            f"📌 {row['status']}\n"
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
            "/addadmin USER_ID"
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
            "/removeadmin USER_ID"
        )

        return

    try:

        user_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ USER_ID noto‘g‘ri."
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
# TEXT HANDLER
# =========================================================

async def text_handler(update, context):

    user = update.effective_user

    text = update.message.text

    add_user(user)

    # -----------------------------------------------------
    # MANDATORY
    # -----------------------------------------------------

    if not await check_mandatory(
        user.id,
        context
    ):

        await send_mandatory_message(
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
        # ADD TASK USERNAME
        # -------------------------------------------------

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

        # -------------------------------------------------
        # ADD TASK TITLE
        # -------------------------------------------------

        if state == "task_title":

            context.user_data["task_title"] = text.strip()
            context.user_data["state"] = "task_reward"

            await update.message.reply_text(
                "⭐ Rewardni yuboring.\n\n"
                "Masalan: 0.1"
            )

            return

        # -------------------------------------------------
        # ADD TASK REWARD
        # -------------------------------------------------

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
                (
                    username,
                    title,
                    reward,
                    created_at
                )
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
                "✅ Vazifa kanali qo‘shildi!\n\n"
                f"📢 {title}\n"
                f"🔗 {username}\n"
                f"⭐ {reward}"
            )

            return

        # -------------------------------------------------
        # ADD GIFT
        # -------------------------------------------------

        if state == "gift_name":

            parts = text.split(maxsplit=1)

            if len(parts) < 2:

                await update.message.reply_text(
                    "Masalan:\n"
                    "💎 Diamond"
                )

                return

            emoji = parts[0]
            name = parts[1]

            context.user_data["gift_emoji"] = emoji
            context.user_data["gift_name"] = name
            context.user_data["state"] = "gift_price"

            await update.message.reply_text(
                "⭐ Gift narxini yuboring.\n\n"
                "Masalan: 50"
            )

            return

        # -------------------------------------------------
        # GIFT PRICE
        # -------------------------------------------------

        if state == "gift_price":

            try:

                price = float(
                    text.replace(",", ".")
                )

            except ValueError:

                await update.message.reply_text(
                    "❌ Narx noto‘g‘ri."
                )

                return

            if price <= 0:

                await update.message.reply_text(
                    "❌ Narx 0 dan katta bo‘lishi kerak."
                )

                return

            emoji = context.user_data.get(
                "gift_emoji"
            )

            name = context.user_data.get(
                "gift_name"
            )

            conn = db()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO gifts
                (
                    name,
                    price,
                    emoji,
                    active,
                    created_at
                )
                VALUES (?, ?, ?, 1, ?)
            """, (
                name,
                price,
                emoji,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Gift qo‘shildi!\n\n"
                f"{emoji} {name}\n"
                f"⭐ {price}"
            )

            return

        # -------------------------------------------------
        # MANDATORY ID
        # -------------------------------------------------

        if state == "mandatory_id":

            channel_id = text.strip()

            try:

                chat = await context.bot.get_chat(
                    channel_id
                )

                if chat.type != "channel":

                    await update.message.reply_text(
                        "❌ Bu Telegram channel emas."
                    )

                    return

            except Exception as e:

                logger.warning(
                    "Mandatory get_chat error: %s",
                    e
                )

                await update.message.reply_text(
                    "❌ Kanal topilmadi.\n\n"
                    "Bot kanalga admin ekanini tekshiring."
                )

                return

            context.user_data[
                "mandatory_channel_id"
            ] = channel_id

            context.user_data[
                "mandatory_username"
            ] = chat.username or ""

            context.user_data[
                "mandatory_chat_title"
            ] = chat.title or ""

            context.user_data[
                "state"
            ] = "mandatory_title"

            await update.message.reply_text(
                "📢 Kanal nomini yuboring.\n\n"
                f"Telegram nomi: {chat.title}"
            )

            return

        # -------------------------------------------------
        # MANDATORY TITLE
        # -------------------------------------------------

        if state == "mandatory_title":

            context.user_data[
                "mandatory_title"
            ] = text.strip()

            context.user_data[
                "state"
            ] = "mandatory_link"

            await update.message.reply_text(
                "🔗 Kanal linkini yuboring.\n\n"
                "Masalan:\n"
                "https://t.me/Cossmoss_00"
            )

            return

        # -------------------------------------------------
        # MANDATORY LINK
        # -------------------------------------------------

        if state == "mandatory_link":

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

            except sqlite3.IntegrityError:

                conn.close()

                context.user_data.clear()

                await update.message.reply_text(
                    "❌ Bu kanal allaqachon mavjud."
                )

                return

            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Majburiy kanal qo‘shildi!\n\n"
                f"🆔 {channel_id}\n"
                f"📢 {title}\n"
                f"🔗 {invite_link}"
            )

            return

    # =====================================================
    # USER MENU
    # =====================================================

    if text == "⭐ Stars":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🎯 Stars ishlash",
                    callback_data="task_next"
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 Balans",
                    callback_data="balance"
                )
            ]
        ]

        await update.message.reply_text(
            "⭐ Stars\n\n"
            "Stars ishlash uchun quyidagi tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    if text == "🎁 Gift olish":

        await gifts_menu(
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

    if text == "💰 Balans":

        await balance_message(
            update,
            context
        )

        return

    if text == "📜 Qoidalar":

        await rules(
            update,
            context
        )

        return

    if text == "📢 Reklama":

        await advertising(
            update,
            context
        )

        return

    # =====================================================
    # ADMIN PANEL
    # =====================================================

    if text == "⚙️ Admin panel":

        if not is_admin(user.id):
            return

        await update.message.reply_text(
            "⚙️ Admin panel",
            reply_markup=admin_menu()
        )

        return

    if text == "📊 Admin statistikasi":

        if is_admin(user.id):
            await admin_statistics(
                update,
                context
            )

        return

    if text == "👥 Foydalanuvchilar":

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

    if text == "👑 Adminlar":

        if is_admin(user.id):
            await admin_list(
                update,
                context
            )

        return

    if text == "🔐 Majburiy kanallar":

        if is_admin(user.id):
            await mandatory_channels(
                update,
                context
            )

        return

    if text == "📢 Vazifa kanallari":

        if is_admin(user.id):
            await task_channels(
                update,
                context
            )

        return

    if text == "🎁 Giftlar":

        if is_admin(user.id):
            await admin_gifts(
                update,
                context
            )

        return

    if text == "📦 Gift so‘rovlari":

        if is_admin(user.id):
            await gift_requests(
                update,
                context
            )

        return

    if text == "📣 Reklama so‘rovlari":

        if is_admin(user.id):
            await advertising_requests(
                update,
                context
            )

        return

    if text == "⬅️ Orqaga":

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
    # MANDATORY
    # =====================================================

    if data == "mandatory_check":

        await query.answer()

        if await check_mandatory(
            user_id,
            context
        ):

            try:
                await query.message.delete()
            except Exception:
                pass

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ Barcha majburiy kanallarga "
                    "obuna bo‘lgansiz!\n\n"
                    "🏠 Botdan foydalanishingiz mumkin."
                ),
                reply_markup=user_menu(user_id)
            )

        else:

            await query.answer(
                "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
                show_alert=True
            )

        return

    # =====================================================
    # TASK
    # =====================================================

    if data == "task_next":

        await show_next_task(
            update,
            context
        )

        return

    if data.startswith("task_check:"):

        await check_task(
            update,
            context
        )

        return

    # =====================================================
    # BALANCE
    # =====================================================

    if data == "balance":

        await show_balance(
            update,
            context
        )

        return

    # =====================================================
    # STARS MENU
    # =====================================================

    if data == "stars_menu":

        await stars_menu(
            update,
            context
        )

        return

    # =====================================================
    # GIFT
    # =====================================================

    if data.startswith("gift:"):

        await show_gift(
            update,
            context
        )

        return

    if data.startswith("gift_confirm:"):

        await confirm_gift(
            update,
            context
        )

        return

    if data == "gift_cancel":

        await cancel_gift(
            update,
            context
        )

        return

    # =====================================================
    # GIFT STATUS
    # =====================================================

    if data.startswith("gift_status:"):

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

    # =====================================================
    # MAIN MENU
    # =====================================================

    if data == "main_menu":

        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            chat_id=user_id,
            text="🏠 Asosiy menyu:",
            reply_markup=user_menu(user_id)
        )

        return

    await query.answer()


# =========================================================
# PERIODIC SUBSCRIPTION CHECK
# =========================================================

async def subscription_job(context):

    users = get_all_users()

    for user in users:

        try:

            await check_two_day_subscriptions(
                user["user_id"],
                context
            )

        except Exception as e:

            logger.warning(
                "Subscription job error: %s",
                e
            )


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

    application.add_handler(
        CommandHandler(
            "addgift",
            add_gift_command
        )
    )

    application.add_handler(
        CommandHandler(
            "editgift",
            edit_gift_command
        )
    )

    application.add_handler(
        CommandHandler(
            "delgift",
            delete_gift_command
        )
    )

    # =====================================================
    # CALLBACK
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

    # =====================================================
    # ERROR
    # =====================================================

    application.add_error_handler(
        error_handler
    )

    # =====================================================
    # SUBSCRIPTION CHECK
    # =====================================================

    if application.job_queue:

        application.job_queue.run_repeating(
            subscription_job,
            interval=300,
            first=30
        )

    logger.info(
        "===================================="
    )

    logger.info(
        "FROSTSTARS BOT IS RUNNING"
    )

    logger.info(
        "===================================="
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
