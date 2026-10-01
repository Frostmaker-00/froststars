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

# Vazifani bajargandan keyin kanalda qolish muddati
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
    # TASKS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            title TEXT,
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
    """)

    # =====================================================
    # COMPLETED TASKS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            reward REAL DEFAULT 0,
            completed_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    # =====================================================
    # TASK VIEWS
    # Har bir task userga faqat bir marta ko'rsatiladi
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            shown_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    # =====================================================
    # TASK SUBSCRIPTIONS
    # 2 kun kanalga obuna bo'lib turish nazorati
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
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
            name TEXT,
            emoji TEXT DEFAULT '🎁',
            price REAL DEFAULT 1,
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

        cur.execute(
            "SELECT id FROM channels WHERE username = ?",
            (username,)
        )

        if not cur.fetchone():

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

    # =====================================================
    # DEFAULT GIFTS
    # =====================================================

    cur.execute("SELECT COUNT(*) FROM gifts")
    gift_count = cur.fetchone()[0]

    if gift_count == 0:

        default_gifts = [
            ("❤️ Yurak", "❤️", 5),
            ("🧸 Teddy Bear", "🧸", 10),
            ("🌹 Rose", "🌹", 15),
            ("🌷 Tulip", "🌷", 20),
            ("💐 Bouquet", "💐", 30),
            ("🎂 Cake", "🎂", 40),
            ("💎 Diamond", "💎", 50),
            ("👑 Crown", "👑", 75),
            ("🚀 Rocket", "🚀", 100),
            ("⭐ Star", "⭐", 150),
            ("🏆 Trophy", "🏆", 200),
            ("💰 Money", "💰", 250),
        ]

        for name, emoji, price in default_gifts:

            cur.execute("""
                INSERT INTO gifts
                (name, emoji, price, active, created_at)
                VALUES (?, ?, ?, 1, ?)
            """, (
                name,
                emoji,
                price,
                datetime.now().isoformat()
            ))

    conn.commit()
    conn.close()


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
        ["⭐ Stars ishlash", "🎁 Gift olish"],
        ["👥 Referral", "💰 Balans"],
        ["📜 Qoidalar", "📢 Reklama"],
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

    buttons = [
        ["📊 Admin statistikasi"],
        ["👥 Foydalanuvchilar", "📝 Loglar"],
        ["👑 Adminlar", "🔐 Majburiy kanallar"],
        ["📢 Vazifa kanallari", "🎁 Giftlar"],
        ["🎁 Gift so‘rovlari"],
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
                "Mandatory check: %s",
                e
            )

            # Kanal tekshirilmasa botni bloklamaymiz
            continue

    return True


async def mandatory_message(update, context):

    channels = get_mandatory_channels()

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
            callback_data="mandatory_check"
        )
    ])

    text = (
        "🔐 Botdan foydalanish uchun "
        "quyidagi kanallarga obuna bo‘ling:"
    )

    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )


# =========================================================
# START
# =========================================================

async def start(update, context):

    user = update.effective_user

    add_user(user)

    # Referral
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
                    f"New referral {user.id}"
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
        "⭐ FrostStars botiga xush kelibsiz!\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=user_menu(user.id)
    )


# =========================================================
# STARS MENU
# =========================================================

async def stars_menu(update, context):

    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 Vazifani boshlash",
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
                callback_data="back_main"
            )
        ]
    ]

    await update.message.reply_text(
        "⭐ Stars ishlash\n\n"
        "Kanallarga obuna bo‘ling va Stars ishlang.",
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


def task_was_seen(user_id, task_id):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM task_views
        WHERE user_id = ?
        AND task_id = ?
    """, (
        user_id,
        task_id
    ))

    result = cur.fetchone()

    conn.close()

    return result is not None


def mark_task_seen(user_id, task_id):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO task_views
        (user_id, task_id, shown_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        task_id,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def task_completed(user_id, task_id):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM completed_tasks
        WHERE user_id = ?
        AND task_id = ?
    """, (
        user_id,
        task_id
    ))

    result = cur.fetchone()

    conn.close()

    return result is not None


def get_next_task(user_id):

    tasks = get_task_channels()

    for task in tasks:

        if task_was_seen(
            user_id,
            task["id"]
        ):
            continue

        if task_completed(
            user_id,
            task["id"]
        ):
            continue

        return task

    return None


async def show_next_task(query, context):

    user_id = query.from_user.id

    task = get_next_task(user_id)

    if not task:

        keyboard = [[
            InlineKeyboardButton(
                "⬅️ Stars",
                callback_data="stars_menu"
            )
        ]]

        await query.edit_message_text(
            "🎉 Hozircha yangi vazifalar yo‘q.\n\n"
            "Barcha mavjud vazifalarni ko‘rib chiqdingiz.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # Task bir marta ko'rilgan deb belgilanadi
    mark_task_seen(
        user_id,
        task["id"]
    )

    username = task["username"] or ""
    clean_username = username.replace("@", "")

    keyboard = [
        [
            InlineKeyboardButton(
                f"📢 {task['title']}",
                url=f"https://t.me/{clean_username}"
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
                "❌ Vazifani yopish",
                callback_data="task_close"
            )
        ]
    ]

    await query.edit_message_text(
        "🎯 Yangi vazifa\n\n"
        f"📢 Kanal: {task['title']}\n"
        f"⭐ Mukofot: +{task['reward']} Stars\n\n"
        "1️⃣ Kanalga kiring\n"
        "2️⃣ Obuna bo‘ling\n"
        "3️⃣ «Obunani tekshirish» tugmasini bosing\n\n"
        "⚠️ Mukofot olish uchun kanalga "
        "2 kun davomida obuna bo‘lib turish kerak.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# TASK CHECK
# =========================================================

async def check_task(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    try:

        task_id = int(
            query.data.split(":")[1]
        )

    except Exception:

        await query.answer(
            "❌ Vazifa xatosi.",
            show_alert=True
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM channels WHERE id = ?",
        (task_id,)
    )

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

    completed = cur.fetchone()

    conn.close()

    if not task:

        await query.answer(
            "❌ Vazifa topilmadi.",
            show_alert=True
        )

        return

    if completed:

        await query.answer(
            "⚠️ Bu vazifa allaqachon bajarilgan.",
            show_alert=True
        )

        return

    username = task["username"]

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
            "Task membership error: %s",
            e
        )

        await query.answer(
            "❌ Kanalni tekshirib bo‘lmadi. "
            "Bot kanalga admin ekanini tekshiring.",
            show_alert=True
        )

        return

    # =====================================================
    # REWARD
    # =====================================================

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
            INSERT OR REPLACE INTO task_subscriptions
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

    conn.close()

    log_activity(
        user_id,
        "task_completed",
        f"{task['title']} +{task['reward']}"
    )

    # Eski vazifa xabarini o'chirish
    try:
        await query.message.delete()
    except Exception:
        pass

    # Keyingi vazifa alohida yangi xabar emas,
    # menyu xabarini qayta yaratamiz
    keyboard = [[
        InlineKeyboardButton(
            "➡️ Keyingi vazifa",
            callback_data="task_next"
        )
    ], [
        InlineKeyboardButton(
            "💰 Balans",
            callback_data="balance"
        ]
    ]]

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            "🎉 Vazifa bajarildi!\n\n"
            f"📢 {task['title']}\n"
            f"⭐ +{task['reward']} Stars\n\n"
            f"💰 Balansingiz yangilandi.\n\n"
            f"⚠️ Kanalda {SUBSCRIPTION_DAYS} kun "
            "davomida qolishingiz kerak."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# CHECK 2-DAY SUBSCRIPTIONS
# =========================================================

async def check_two_day_subscriptions(user_id, context):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT ts.*, c.username, c.title
        FROM task_subscriptions ts
        JOIN channels c
        ON c.id = ts.task_id
        WHERE ts.user_id = ?
        AND ts.valid = 1
    """, (
        user_id,
    ))

    subscriptions = cur.fetchall()

    conn.close()

    for sub in subscriptions:

        try:

            expires = datetime.fromisoformat(
                sub["expires_at"]
            )

        except Exception:
            continue

        # 2 kun tugagan bo'lsa
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

        # Hali 2 kun tugamagan
        try:

            member = await context.bot.get_chat_member(
                sub["username"],
                user_id
            )

            if member.status not in (
                "member",
                "administrator",
                "creator"
            ):

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

                await context.bot.send_message(
                    user_id,
                    "⚠️ Siz vazifa kanalidan chiqib ketgansiz.\n\n"
                    f"📢 {sub['title']}\n"
                    "Vazifa uchun berilgan 2 kunlik obuna "
                    "sharti buzildi."
                )

                continue

        except Exception as e:

            logger.warning(
                "2 day check error: %s",
                e
            )

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


# =========================================================
# BALANCE
# =========================================================

async def balance_menu(update, context):

    user_id = update.effective_user.id

    await check_two_day_subscriptions(
        user_id,
        context
    )

    row = get_user(user_id)

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="back_main"
        )
    ]]

    await update.message.reply_text(
        "💰 Sizning balansingiz:\n\n"
        f"⭐ {row['balance']:.2f}",
        reply_markup=InlineKeyboardMarkup(keyboard)
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

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="back_main"
        )
    ]]

    await update.message.reply_text(
        "👥 Referral\n\n"
        f"⭐ Har bir referral: {REFERRAL_REWARD}\n"
        f"👤 Referral soni: {row['referral_count']}\n\n"
        f"🔗 Sizning linkingiz:\n{link}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# RULES
# =========================================================

async def rules(update, context):

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="back_main"
        )
    ]]

    await update.message.reply_text(
        "📜 FrostStars qoidalari\n\n"
        "1. Vazifani faqat bir marta bajarish mumkin.\n"
        "2. Har bir vazifa faqat bir marta ko‘rsatiladi.\n"
        "3. Vazifani bajargandan keyin kanalni "
        "2 kun tark etmaslik kerak.\n"
        "4. Soxta akkauntlardan foydalanish taqiqlanadi.\n"
        "5. Gift olish uchun yetarli Stars bo‘lishi kerak.\n"
        "6. Botdagi xatolardan foydalanish taqiqlanadi.",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        ORDER BY id ASC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


async def gifts_menu(update, context):

    gifts_list = get_gifts()

    buttons = []

    for gift in gifts_list:

        buttons.append([
            InlineKeyboardButton(
                f"{gift['emoji']} {gift['name']} — ⭐ {gift['price']}",
                callback_data=f"gift:{gift['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="back_main"
        )
    ])

    await update.message.reply_text(
        "🎁 Gift olish\n\n"
        "Kerakli giftni tanlang:",
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

    cur.execute(
        "SELECT * FROM gifts WHERE id = ? AND active = 1",
        (gift_id,)
    )

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
                callback_data=f"gift_confirm:{gift_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Giftlar",
                callback_data="gifts_list"
            )
        ]
    ]

    await query.edit_message_text(
        f"{gift['emoji']} {gift['name']}\n\n"
        f"💰 Narxi: ⭐ {gift['price']}\n\n"
        "Giftni olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# CONFIRM GIFT
# =========================================================

async def confirm_gift(update, context):

    query = update.callback_query

    await query.answer()

    try:

        gift_id = int(
            query.data.split(":")[1]
        )

    except Exception:

        return

    user_id = query.from_user.id

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM gifts WHERE id = ? AND active = 1",
        (gift_id,)
    )

    gift = cur.fetchone()

    conn.close()

    if not gift:

        await query.answer(
            "❌ Gift mavjud emas.",
            show_alert=True
        )

        return

    user = get_user(user_id)

    if user["balance"] < gift["price"]:

        await query.answer(
            f"❌ Yetarli Stars yo‘q.\n"
            f"Kerak: {gift['price']}\n"
            f"Sizda: {user['balance']:.2f}",
            show_alert=True
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE user_id = ?
    """, (
        gift["price"],
        user_id
    ))

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
        gift_id,
        f"{gift['emoji']} {gift['name']}",
        gift["price"],
        datetime.now().isoformat(),
        datetime.now().isoformat()
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
        "✅ Gift so‘rovi yuborildi!\n\n"
        f"{gift['emoji']} {gift['name']}\n"
        f"⭐ {gift['price']}\n"
        f"🆔 So‘rov: #{request_id}\n\n"
        "Admin so‘rovni ko‘rib chiqadi."
    )


# =========================================================
# ADVERTISING
# =========================================================

async def advertising(update, context):

    context.user_data["state"] = "advertisement"

    await update.message.reply_text(
        "📢 Reklama\n\n"
        "Reklama ma'lumotlarini yuboring.\n\n"
        "Masalan:\n"
        "Kanal: @example\n"
        "Reklama turi: post\n"
        "Muddat: 3 kun"
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

    log_activity(
        user.id,
        "advertisement",
        f"#{request_id}"
    )

    await update.message.reply_text(
        "✅ Reklama so‘rovingiz qabul qilindi.\n\n"
        f"🆔 #{request_id}\n"
        "Admin siz bilan bog‘lanadi.",
        reply_markup=user_menu(user.id)
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
    balance = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM completed_tasks"
    )
    completed = cur.fetchone()[0]

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
        f"🎯 Bajarilgan vazifalar: {completed}\n"
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
            f"👤 {user['first_name']} "
            f"({username})\n"
            f"⭐ {user['balance']:.2f}\n"
            f"👥 Ref: {user['referral_count']}\n\n"
        )

    await update.message.reply_text(text)


# =========================================================
# LOGS
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
            f"#{row['id']} | {row['user_id']}\n"
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
        "/addadmin USER_ID\n"
        "/removeadmin USER_ID"
    )

    await update.message.reply_text(text)


# =========================================================
# TASK CHANNELS ADMIN
# =========================================================

async def task_channels_admin(update, context):

    channels = get_task_channels()

    text = "📢 Vazifa kanallari:\n\n"

    for channel in channels:

        text += (
            f"🆔 {channel['id']}\n"
            f"📢 {channel['title']}\n"
            f"🔗 {channel['username']}\n"
            f"⭐ Reward: {channel['reward']}\n\n"
        )

    text += (
        "/addtask\n"
        "/deltask ID"
    )

    await update.message.reply_text(text)


# =========================================================
# MANDATORY CHANNELS ADMIN
# =========================================================

async def mandatory_channels_admin(update, context):

    channels = get_mandatory_channels()

    text = "🔐 Majburiy kanallar:\n\n"

    if not channels:
        text += "Kanal yo‘q.\n\n"

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


# =========================================================
# GIFTS ADMIN
# =========================================================

async def gifts_admin(update, context):

    gifts_list = get_gifts()

    text = "🎁 Giftlar:\n\n"

    for gift in gifts_list:

        text += (
            f"🆔 {gift['id']}\n"
            f"{gift['emoji']} {gift['name']}\n"
            f"⭐ Narxi: {gift['price']}\n\n"
        )

    text += (
        "➕ Gift qo‘shish: /addgift\n"
        "💰 Narx o‘zgartirish: /setgiftprice ID NARX\n"
        "🗑 Gift o‘chirish: /delgift ID"
    )

    await update.message.reply_text(text)


# =========================================================
# GIFT REQUESTS ADMIN
# =========================================================

async def gift_requests_admin(update, context):

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
                        f"gift_status:{row['id']}:approved"
                    )
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=(
                        f"gift_status:{row['id']}:rejected"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "📦 Delivered",
                    callback_data=(
                        f"gift_status:{row['id']}:delivered"
                    )
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


# =========================================================
# GIFT STATUS
# =========================================================

async def gift_status(update, context):

    query = update.callback_query

    await query.answer()

    if not is_admin(query.from_user.id):

        await query.answer(
            "❌ Admin emassiz.",
            show_alert=True
        )

        return

    try:

        _, request_id, status = (
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

        await query.answer(
            "❌ So‘rov topilmadi.",
            show_alert=True
        )

        return

    old_status = request["status"]

    if status == "approved":

        if old_status != "pending":

            conn.close()

            await query.answer(
                "❌ Bu so‘rov pending emas.",
                show_alert=True
            )

            return

    elif status == "rejected":

        if old_status != "pending":

            conn.close()

            await query.answer(
                "❌ Bu so‘rov pending emas.",
                show_alert=True
            )

            return

        # Pulni qaytarish
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

            await query.answer(
                "❌ Avval approve qiling.",
                show_alert=True
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

    await query.edit_message_text(
        f"🎁 Gift #{request_id}\n\n"
        f"👤 User: {request['user_id']}\n"
        f"🎁 {request['gift_name']}\n"
        f"⭐ {request['price']}\n\n"
        f"✅ Status: {status}"
    )


# =========================================================
# ADD GIFT COMMAND
# =========================================================

async def add_gift_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "gift_name"

    await update.message.reply_text(
        "🎁 Yangi gift qo‘shish.\n\n"
        "1️⃣ Gift nomini yuboring.\n\n"
        "Masalan:\n"
        "Diamond"
    )


async def set_gift_price_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:

        await update.message.reply_text(
            "/setgiftprice ID NARX\n\n"
            "Masalan:\n"
            "/setgiftprice 3 25"
        )

        return

    try:

        gift_id = int(context.args[0])
        price = float(
            context.args[1].replace(",", ".")
        )

        if price <= 0:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "❌ ID va narx noto‘g‘ri."
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

    if not changed:

        await update.message.reply_text(
            "❌ Gift topilmadi."
        )

        return

    await update.message.reply_text(
        f"✅ Gift #{gift_id} narxi "
        f"⭐ {price} qilib belgilandi."
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
            "❌ ID raqam bo‘lishi kerak."
        )

        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE gifts
        SET active = 0
        WHERE id = ?
    """, (
        gift_id
    ))

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

    changed = cur.rowcount

    conn.commit()
    conn.close()

    if changed:

        await update.message.reply_text(
            "✅ Vazifa o‘chirildi."
        )

    else:

        await update.message.reply_text(
            "❌ Vazifa topilmadi."
        )


# =========================================================
# ADD MANDATORY
# =========================================================

async def add_mandatory_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "mandatory_id"

    await update.message.reply_text(
        "🔐 Majburiy kanal qo‘shish.\n\n"
        "Kanal ID yuboring.\n\n"
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

    changed = cur.rowcount

    conn.commit()
    conn.close()

    if changed:

        await update.message.reply_text(
            "✅ Majburiy kanal o‘chirildi."
        )

    else:

        await update.message.reply_text(
            "❌ Kanal topilmadi."
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
            "❌ USER_ID noto‘g‘ri."
        )

        return

    if not get_user(user_id):

        await update.message.reply_text(
            "❌ Bu foydalanuvchi botdan foydalanmagan."
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

    # 2 kunlik task subscription nazorati
    await check_two_day_subscriptions(
        user.id,
        context
    )

    # Majburiy kanal
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

        # =================================================
        # ADD TASK USERNAME
        # =================================================

        if state == "task_username":

            username = text.strip()

            if not username.startswith("@"):
                username = "@" + username

            context.user_data[
                "task_username"
            ] = username

            context.user_data[
                "state"
            ] = "task_title"

            await update.message.reply_text(
                "📢 Kanal nomini yuboring."
            )

            return

        # =================================================
        # ADD TASK TITLE
        # =================================================

        if state == "task_title":

            context.user_data[
                "task_title"
            ] = text.strip()

            context.user_data[
                "state"
            ] = "task_reward"

            await update.message.reply_text(
                "⭐ Reward miqdorini yuboring.\n\n"
                "Masalan:\n"
                "0.1"
            )

            return

        # =================================================
        # ADD TASK REWARD
        # =================================================

        if state == "task_reward":

            try:

                reward = float(
                    text.replace(",", ".")
                )

                if reward <= 0:
                    raise ValueError

            except ValueError:

                await update.message.reply_text(
                    "❌ Reward noto‘g‘ri."
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

            except sqlite3.IntegrityError:

                conn.close()

                await update.message.reply_text(
                    "❌ Bu kanal allaqachon mavjud."
                )

                return

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

            await update.message.reply_text(
                "✅ Vazifa qo‘shildi!\n\n"
                f"📢 {title}\n"
                f"🔗 {username}\n"
                f"⭐ {reward}"
            )

            return

        # =================================================
        # MANDATORY ID
        # =================================================

        if state == "mandatory_id":

            channel_id = text.strip()

            if not channel_id.startswith("-100"):

                await update.message.reply_text(
                    "❌ Kanal ID odatda -100 bilan boshlanadi."
                )

                return

            try:

                chat = await context.bot.get_chat(
                    channel_id
                )

                if chat.type != "channel":

                    await update.message.reply_text(
                        "❌ Bu Telegram channel emas."
                    )

                    return

            except Exception:

                await update.message.reply_text(
                    "❌ Kanal topilmadi.\n\n"
                    "Bot kanalga admin ekanini tekshiring."
                )

                return

            context.user_data[
                "mandatory_id"
            ] = channel_id

            context.user_data[
                "mandatory_username"
            ] = chat.username or ""

            context.user_data[
                "state"
            ] = "mandatory_title"

            await update.message.reply_text(
                "📢 Kanal nomini yuboring."
            )

            return

        # =================================================
        # MANDATORY TITLE
        # =================================================

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

        # =================================================
        # MANDATORY LINK
        # =================================================

        if state == "mandatory_link":

            invite_link = text.strip()

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
                "✅ Majburiy kanal qo‘shildi!\n\n"
                f"📢 {title}\n"
                f"🆔 {channel_id}\n"
                f"🔗 {invite_link}"
            )

            return

        # =================================================
        # ADD GIFT NAME
        # =================================================

        if state == "gift_name":

            context.user_data[
                "gift_name"
            ] = text.strip()

            context.user_data[
                "state"
            ] = "gift_emoji"

            await update.message.reply_text(
                "2️⃣ Gift emoji yuboring.\n\n"
                "Masalan:\n"
                "💎"
            )

            return

        # =================================================
        # ADD GIFT EMOJI
        # =================================================

        if state == "gift_emoji":

            context.user_data[
                "gift_emoji"
            ] = text.strip()

            context.user_data[
                "state"
            ] = "gift_price"

            await update.message.reply_text(
                "3️⃣ Gift narxini yuboring.\n\n"
                "Masalan:\n"
                "50"
            )

            return

        # =================================================
        # ADD GIFT PRICE
        # =================================================

        if state == "gift_price":

            try:

                price = float(
                    text.replace(",", ".")
                )

                if price <= 0:
                    raise ValueError

            except ValueError:

                await update.message.reply_text(
                    "❌ Narx noto‘g‘ri."
                )

                return

            name = context.user_data.get(
                "gift_name"
            )

            emoji = context.user_data.get(
                "gift_emoji"
            )

            conn = db()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO gifts
                (name, emoji, price, active, created_at)
                VALUES (?, ?, ?, 1, ?)
            """, (
                name,
                emoji,
                price,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Yangi gift qo‘shildi!\n\n"
                f"{emoji} {name}\n"
                f"⭐ Narx: {price}"
            )

            return

    # =====================================================
    # USER BUTTONS
    # =====================================================

    if text == "⭐ Stars ishlash":

        await stars_menu(
            update,
            context
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

        await balance_menu(
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
    # ADMIN MENU
    # =====================================================

    if text == "⚙️ Admin panel":

        if not is_admin(user.id):
            return

        await update.message.reply_text(
            "⚙️ Admin panel:",
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

    if text == "📝 Loglar":

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
            await mandatory_channels_admin(
                update,
                context
            )

        return

    if text == "📢 Vazifa kanallari":

        if is_admin(user.id):
            await task_channels_admin(
                update,
                context
            )

        return

    if text == "🎁 Giftlar":

        if is_admin(user.id):
            await gifts_admin(
                update,
                context
            )

        return

    if text == "🎁 Gift so‘rovlari":

        if is_admin(user.id):
            await gift_requests_admin(
                update,
                context
            )

        return

    if text == "📣 Reklama so‘rovlari":

        if is_admin(user.id):

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

            text_result = "📣 Reklama so‘rovlari:\n\n"

            for row in rows:

                text_result += (
                    f"#{row['id']}\n"
                    f"👤 {row['user_id']}\n"
                    f"📌 {row['status']}\n"
                    f"📝 {row['text']}\n\n"
                )

            await update.message.reply_text(
                text_result
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

            await query.edit_message_text(
                "✅ Barcha majburiy kanallarga "
                "obuna bo‘lgansiz!\n\n"
                "Endi botdan foydalanishingiz mumkin."
            )

        else:

            await query.answer(
                "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
                show_alert=True
            )

        return

    # =====================================================
    # BACK MAIN
    # =====================================================

    if data == "back_main":

        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            user_id,
            "🏠 Asosiy menyu:",
            reply_markup=user_menu(user_id)
        )

        return

    # =====================================================
    # STARS MENU
    # =====================================================

    if data == "stars_menu":

        await query.answer()

        keyboard = [[
            InlineKeyboardButton(
                "🎯 Vazifani boshlash",
                callback_data="task_next"
            )
        ], [
            InlineKeyboardButton(
                "💰 Balans",
                callback_data="balance"
            )
        ], [
            InlineKeyboardButton(
                "⬅️ Orqaga",
                callback_data="back_main"
            )
        ]]

        await query.edit_message_text(
            "⭐ Stars ishlash",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # =====================================================
    # NEXT TASK
    # =====================================================

    if data == "task_next":

        await query.answer()

        await show_next_task(
            query,
            context
        )

        return

    # =====================================================
    # TASK CHECK
    # =====================================================

    if data.startswith("task_check:"):

        await check_task(
            update,
            context
        )

        return

    # =====================================================
    # TASK CLOSE
    # =====================================================

    if data == "task_close":

        await query.answer()

        await query.edit_message_text(
            "❌ Vazifa yopildi.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "➡️ Stars",
                        callback_data="stars_menu"
                    )
                ]
            ])
        )

        return

    # =====================================================
    # BALANCE
    # =====================================================

    if data == "balance":

        await query.answer()

        await check_two_day_subscriptions(
            user_id,
            context
        )

        row = get_user(user_id)

        await query.edit_message_text(
            "💰 Balansingiz:\n\n"
            f"⭐ {row['balance']:.2f}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Stars",
                        callback_data="stars_menu"
                    )
                ]
            ])
        )

        return

    # =====================================================
    # GIFTS LIST
    # =====================================================

    if data == "gifts_list":

        await query.answer()

        gifts_list = get_gifts()

        buttons = []

        for gift in gifts_list:

            buttons.append([
                InlineKeyboardButton(
                    f"{gift['emoji']} {gift['name']} — ⭐ {gift['price']}",
                    callback_data=f"gift:{gift['id']}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "⬅️ Orqaga",
                callback_data="back_main"
            )
        ])

        await query.edit_message_text(
            "🎁 Giftlar:",
            reply_markup=InlineKeyboardMarkup(buttons)
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

    # =====================================================
    # GIFT CONFIRM
    # =====================================================

    if data.startswith("gift_confirm:"):

        await confirm_gift(
            update,
            context
        )

        return

    # =====================================================
    # GIFT STATUS
    # =====================================================

    if data.startswith("gift_status:"):

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
            "setgiftprice",
            set_gift_price_command
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

    logger.info(
        "FROSTSTARS BOT IS RUNNING!"
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
