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
# SOZLAMALAR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "starbot.db"
TOKEN_FILE = BASE_DIR / "bot_token.txt"

# Botning asosiy egasi
OWNER_ID = 6383248812

DEFAULT_TASK_REWARD = 0.1
REFERRAL_REWARD = 1.5

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# TOKEN
# ============================================================

def get_bot_token():
    """
    Token birinchi ishga tushganda so'raladi.
    Keyingi ishga tushirishlarda bot_token.txt dan olinadi.
    """

    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()

        if token:
            return token

    print()
    print("=" * 50)
    print("FROSTSTARS BOT")
    print("=" * 50)
    print("Bot tokeni birinchi marta kiritiladi.")
    print("Tokenni menga yubormang.")
    print()

    token = input("BotFather tokenini kiriting: ").strip()

    if not token:
        raise RuntimeError("BOT_TOKEN kiritilmadi!")

    TOKEN_FILE.write_text(token, encoding="utf-8")

    print()
    print("Token saqlandi.")
    print("Keyingi safar qayta kiritish shart emas.")
    print()

    return token


BOT_TOKEN = get_bot_token()


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = db()
    cur = conn.cursor()

    # Users
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

    # Completed tasks
    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            completed_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    # Gift requests
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            price INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            gift_id TEXT,
            gift_name TEXT
        )
    """)

    # Task channels
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            title TEXT,
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
    """)

    # Admins
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT
        )
    """)

    # Activity logs
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

    # Advertiser requests
    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT
        )
    """)

    # Mandatory channels
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            title TEXT,
            created_at TEXT
        )
    """)

    # Owner avtomatik admin
    cur.execute("""
        INSERT OR IGNORE INTO admins(user_id, added_at)
        VALUES (?, ?)
    """, (
        OWNER_ID,
        datetime.now().isoformat()
    ))

    # Default task channels
    count = cur.execute(
        "SELECT COUNT(*) FROM channels"
    ).fetchone()[0]

    if count == 0:
        cur.execute("""
            INSERT OR IGNORE INTO channels
            (channel_id, title, reward, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            "@Cossmoss_00",
            "Cossmoss",
            DEFAULT_TASK_REWARD,
            datetime.now().isoformat()
        ))

        cur.execute("""
            INSERT OR IGNORE INTO channels
            (channel_id, title, reward, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            "@PromptLab_UZ",
            "PromptLab UZ",
            DEFAULT_TASK_REWARD,
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()


# ============================================================
# ADMIN
# ============================================================

def is_admin(user_id: int) -> bool:

    conn = db()

    row = conn.execute(
        "SELECT user_id FROM admins WHERE user_id=?",
        (user_id,)
    ).fetchone()

    conn.close()

    return row is not None


def get_admins():

    conn = db()

    rows = conn.execute(
        "SELECT * FROM admins ORDER BY added_at"
    ).fetchall()

    conn.close()

    return rows


def add_admin(user_id):

    conn = db()

    conn.execute("""
        INSERT OR IGNORE INTO admins(user_id, added_at)
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

    conn.execute(
        "DELETE FROM admins WHERE user_id=?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return True


# ============================================================
# LOG
# ============================================================

def log_activity(user, action, details=""):

    try:

        conn = db()

        conn.execute("""
            INSERT INTO activity_logs
            (user_id, username, action, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username or "",
            action,
            details,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error("Log error: %s", e)


# ============================================================
# USERS
# ============================================================

def add_user(user, referred_by=None):

    conn = db()

    old = conn.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (user.id,)
    ).fetchone()

    if old:
        conn.execute("""
            UPDATE users
            SET username=?, first_name=?
            WHERE user_id=?
        """, (
            user.username or "",
            user.first_name or "",
            user.id
        ))

    else:

        valid_ref = None

        if referred_by and referred_by != user.id:

            ref_exists = conn.execute(
                "SELECT user_id FROM users WHERE user_id=?",
                (referred_by,)
            ).fetchone()

            if ref_exists:
                valid_ref = referred_by

        conn.execute("""
            INSERT INTO users
            (user_id, username, first_name, balance,
             referred_by, referrals, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            0,
            valid_ref,
            0,
            datetime.now().isoformat()
        ))

        if valid_ref:

            conn.execute("""
                UPDATE users
                SET balance=balance+?,
                    referrals=referrals+1
                WHERE user_id=?
            """, (
                REFERRAL_REWARD,
                valid_ref
            ))

    conn.commit()
    conn.close()


def get_balance(user_id):

    conn = db()

    row = conn.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    conn.close()

    return float(row["balance"]) if row else 0


# ============================================================
# MENUS
# ============================================================

def user_menu(user_id):

    keyboard = [
        ["⭐ Stars ishlash", "👥 Referal"],
        ["📊 Statistika", "💳 Gift olish"],
        ["ℹ️ Qoidalar", "📢 Reklama"],
    ]

    if is_admin(user_id):
        keyboard.append(["👑 Admin panel"])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


def admin_menu():

    return ReplyKeyboardMarkup(
        [
            ["📊 Bot statistikasi", "👥 Foydalanuvchilar"],
            ["📜 Faoliyat loglari", "👑 Adminlar"],
            ["📌 Majburiy kanallar", "📢 Topshiriq kanallari"],
            ["🎁 Gift so‘rovlari", "📣 Reklama so‘rovlari"],
            ["🔙 Orqaga"],
        ],
        resize_keyboard=True
    )


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    referred_by = None

    if context.args:

        try:
            referred_by = int(context.args[0])
        except:
            referred_by = None

    add_user(user, referred_by)

    log_activity(
        user,
        "START",
        f"referral={referred_by}"
    )

    if referred_by and referred_by != user.id:

        try:
            await update.message.reply_text(
                f"🎉 Referal orqali qo‘shildingiz!\n\n"
                f"Referal egasiga {REFERRAL_REWARD} Stars balans berildi."
            )
        except:
            pass

    await update.message.reply_text(
        f"👋 Salom, {user.first_name}!\n\n"
        f"⭐ FrostStars botiga xush kelibsiz!",
        reply_markup=user_menu(user.id)
    )


# ============================================================
# STARS TASKS
# ============================================================

async def stars_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    conn = db()

    channels = conn.execute(
        "SELECT * FROM channels ORDER BY id"
    ).fetchall()

    completed = conn.execute("""
        SELECT task_id
        FROM completed_tasks
        WHERE user_id=?
    """, (
        user.id,
    )).fetchall()

    completed_ids = {
        row["task_id"]
        for row in completed
    }

    conn.close()

    keyboard = []

    for ch in channels:

        if ch["id"] in completed_ids:

            text = f"✅ {ch['title']}"

        else:

            text = f"⭐ {ch['title']} +{ch['reward']}"

        keyboard.append([
            InlineKeyboardButton(
                text,
                callback_data=f"task:{ch['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:main"
        )
    ])

    await update.message.reply_text(
        "⭐ Stars ishlash\n\n"
        "Kanalga obuna bo‘ling va tekshiring:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    log_activity(user, "BUTTON", "Stars ishlash")


async def task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    task_id = int(query.data.split(":")[1])

    conn = db()

    channel = conn.execute(
        "SELECT * FROM channels WHERE id=?",
        (task_id,)
    ).fetchone()

    completed = conn.execute("""
        SELECT id
        FROM completed_tasks
        WHERE user_id=? AND task_id=?
    """, (
        user.id,
        task_id
    )).fetchone()

    conn.close()

    if not channel:

        await query.edit_message_text(
            "❌ Topshiriq topilmadi."
        )

        return

    if completed:

        await query.edit_message_text(
            "✅ Bu topshiriqni oldin bajargansiz."
        )

        return

    channel_id = channel["channel_id"]

    link = (
        f"https://t.me/{channel_id.lstrip('@')}"
        if channel_id.startswith("@")
        else None
    )

    buttons = []

    if link:

        buttons.append([
            InlineKeyboardButton(
                "📢 Kanalga kirish",
                url=link
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔎 Tekshirish",
            callback_data=f"check:{task_id}"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:stars"
        )
    ])

    await query.edit_message_text(
        f"📢 {channel['title']}\n\n"
        f"⭐ Mukofot: {channel['reward']} Stars\n\n"
        f"Kanalga obuna bo‘ling, keyin Tekshirish tugmasini bosing.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    log_activity(
        user,
        "TASK_OPEN",
        f"task={task_id}"
    )


async def check_task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    task_id = int(query.data.split(":")[1])

    conn = db()

    channel = conn.execute(
        "SELECT * FROM channels WHERE id=?",
        (task_id,)
    ).fetchone()

    completed = conn.execute("""
        SELECT id
        FROM completed_tasks
        WHERE user_id=? AND task_id=?
    """, (
        user.id,
        task_id
    )).fetchone()

    conn.close()

    if not channel:

        await query.edit_message_text(
            "❌ Topshiriq topilmadi."
        )

        return

    if completed:

        await query.edit_message_text(
            "✅ Bu topshiriq allaqachon bajarilgan."
        )

        return

    try:

        member = await context.bot.get_chat_member(
            channel["channel_id"],
            user.id
        )

        status = member.status

        subscribed = status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception as e:

        logger.error("Subscription check error: %s", e)

        await query.edit_message_text(
            "⚠️ Obunani tekshirib bo‘lmadi.\n\n"
            "Bot kanalga admin qilinganini tekshiring."
        )

        return

    if not subscribed:

        await query.answer(
            "❌ Avval kanalga obuna bo‘ling!",
            show_alert=True
        )

        return

    conn = db()

    try:

        conn.execute("""
            INSERT INTO completed_tasks
            (user_id, task_id, completed_at)
            VALUES (?, ?, ?)
        """, (
            user.id,
            task_id,
            datetime.now().isoformat()
        ))

        conn.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE user_id=?
        """, (
            channel["reward"],
            user.id
        ))

        conn.commit()

    except sqlite3.IntegrityError:

        conn.rollback()

        await query.edit_message_text(
            "✅ Bu topshiriq allaqachon bajarilgan."
        )

        conn.close()
        return

    conn.close()

    log_activity(
        user,
        "TASK_COMPLETED",
        f"task={task_id}, reward={channel['reward']}"
    )

    await query.edit_message_text(
        f"🎉 Topshiriq bajarildi!\n\n"
        f"⭐ +{channel['reward']} Stars qo‘shildi."
    )


# ============================================================
# REFERAL
# ============================================================

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    me = await context.bot.get_me()

    link = f"https://t.me/{me.username}?start={user.id}"

    conn = db()

    row = conn.execute("""
        SELECT referrals, balance
        FROM users
        WHERE user_id=?
    """, (
        user.id,
    )).fetchone()

    conn.close()

    referrals = row["referrals"] if row else 0
    balance = row["balance"] if row else 0

    await update.message.reply_text(
        "👥 Referal tizimi\n\n"
        f"👤 Referallar: {referrals}\n"
        f"⭐ Balans: {balance:g}\n\n"
        f"🔗 Sizning havolangiz:\n{link}",
        reply_markup=user_menu(user.id)
    )

    log_activity(user, "BUTTON", "Referal")


# ============================================================
# STATISTIKA
# ============================================================

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    conn = db()

    row = conn.execute("""
        SELECT balance, referrals
        FROM users
        WHERE user_id=?
    """, (
        user.id,
    )).fetchone()

    tasks = conn.execute("""
        SELECT COUNT(*)
        FROM completed_tasks
        WHERE user_id=?
    """, (
        user.id,
    )).fetchone()[0]

    conn.close()

    balance = row["balance"] if row else 0
    referrals = row["referrals"] if row else 0

    await update.message.reply_text(
        "📊 Sizning statistikangiz\n\n"
        f"⭐ Balans: {balance:g}\n"
        f"✅ Bajarilgan topshiriqlar: {tasks}\n"
        f"👥 Referallar: {referrals}",
        reply_markup=user_menu(user.id)
    )

    log_activity(user, "BUTTON", "Statistika")


# ============================================================
# QOIDALAR
# ============================================================

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    await update.message.reply_text(
        "ℹ️ Qoidalar\n\n"
        "1. Kanal topshiriqlarini halol bajaring.\n"
        "2. Bir topshiriq uchun mukofot faqat bir marta beriladi.\n"
        "3. Soxta akkauntlar va aldov taqiqlanadi.\n"
        "4. Gift olish uchun balans yetarli bo‘lishi kerak.\n"
        "5. Bot qoidalarini buzgan akkaunt cheklanishi mumkin.",
        reply_markup=user_menu(user.id)
    )

    log_activity(user, "BUTTON", "Qoidalar")


# ============================================================
# GIFT
# ============================================================

async def get_real_gifts(context):

    try:

        gifts = await context.bot.get_available_gifts()

        result = []

        for gift in gifts.gifts:

            star_count = getattr(
                gift,
                "star_count",
                None
            )

            gift_id = getattr(
                gift,
                "id",
                None
            )

            sticker = getattr(
                gift,
                "sticker",
                None
            )

            emoji = "🎁"

            if sticker:

                emoji = getattr(
                    sticker,
                    "emoji",
                    "🎁"
                )

            if star_count and gift_id:

                result.append({
                    "id": gift_id,
                    "price": star_count,
                    "emoji": emoji
                })

        return result

    except Exception as e:

        logger.error("Gift error: %s", e)

        return []


async def gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    balance = get_balance(user.id)

    gifts = await get_real_gifts(context)

    if not gifts:

        await update.message.reply_text(
            "🎁 Hozircha mavjud gift topilmadi.",
            reply_markup=user_menu(user.id)
        )

        return

    keyboard = []

    for gift in gifts:

        keyboard.append([
            InlineKeyboardButton(
                f"{gift['emoji']} {gift['price']} ⭐",
                callback_data=(
                    f"gift:{gift['id']}:{gift['price']}"
                )
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Orqaga",
            callback_data="back:main"
        )
    ])

    await update.message.reply_text(
        f"💳 Gift olish\n\n"
        f"⭐ Sizning balansingiz: {balance:g}\n\n"
        f"Gift tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    log_activity(user, "BUTTON", "Gift olish")


async def gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    parts = query.data.split(":")

    gift_id = parts[1]
    price = int(parts[2])

    balance = get_balance(user.id)

    if balance < price:

        await query.answer(
            f"❌ Balansingiz yetarli emas. Kerak: {price} ⭐",
            show_alert=True
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Tasdiqlash",
                callback_data=f"confirmgift:{gift_id}:{price}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Bekor qilish",
                callback_data="back:main"
            )
        ]
    ]

    await query.edit_message_text(
        f"🎁 Gift buyurtmasi\n\n"
        f"💰 Narxi: {price} ⭐\n"
        f"⭐ Balansingiz: {balance:g}\n\n"
        f"Buyurtmani tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirm_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    parts = query.data.split(":")

    gift_id = parts[1]
    price = int(parts[2])

    conn = db()

    row = conn.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user.id,)
    ).fetchone()

    if not row or row["balance"] < price:

        conn.close()

        await query.edit_message_text(
            "❌ Balans yetarli emas."
        )

        return

    conn.execute("""
        UPDATE users
        SET balance=balance-?
        WHERE user_id=?
    """, (
        price,
        user.id
    ))

    cur = conn.execute("""
        INSERT INTO gift_requests
        (user_id, price, status, created_at, gift_id, gift_name)
        VALUES (?, ?, 'pending', ?, ?, ?)
    """, (
        user.id,
        price,
        datetime.now().isoformat(),
        gift_id,
        "Telegram Gift"
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    log_activity(
        user,
        "GIFT_ORDER",
        f"id={request_id}, price={price}"
    )

    await query.edit_message_text(
        f"✅ Buyurtma qabul qilindi!\n\n"
        f"🆔 Buyurtma: #{request_id}\n"
        f"⭐ Narxi: {price}\n\n"
        f"Admin tekshirganidan keyin gift yuboriladi."
    )

    await notify_admins(
        context,
        f"🎁 Yangi Gift so‘rovi\n\n"
        f"🆔 #{request_id}\n"
        f"👤 {user.first_name}\n"
        f"🆔 User ID: {user.id}\n"
        f"⭐ Narx: {price}"
    )


# ============================================================
# ADMIN NOTIFICATION
# ============================================================

async def notify_admins(context, text):

    for row in get_admins():

        try:

            await context.bot.send_message(
                row["user_id"],
                text
            )

        except Exception as e:

            logger.error(
                "Admin notification error: %s",
                e
            )


# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):

        await update.message.reply_text(
            "❌ Sizda admin huquqi yo‘q."
        )

        return

    await update.message.reply_text(
        "👑 Admin panel\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=admin_menu()
    )

    log_activity(user, "ADMIN_PANEL", "open")


# ============================================================
# BOT STATISTIKASI
# ============================================================

async def bot_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
        return

    conn = db()

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    tasks = conn.execute(
        "SELECT COUNT(*) FROM completed_tasks"
    ).fetchone()[0]

    orders = conn.execute(
        "SELECT COUNT(*) FROM gift_requests"
    ).fetchone()[0]

    pending = conn.execute("""
        SELECT COUNT(*)
        FROM gift_requests
        WHERE status='pending'
    """).fetchone()[0]

    conn.close()

    await update.message.reply_text(
        "📊 Bot statistikasi\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"✅ Bajarilgan topshiriqlar: {tasks}\n"
        f"🎁 Jami buyurtmalar: {orders}\n"
        f"⏳ Kutilayotgan buyurtmalar: {pending}",
        reply_markup=admin_menu()
    )


# ============================================================
# USERS
# ============================================================

async def users_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
        return

    conn = db()

    rows = conn.execute("""
        SELECT user_id, username, first_name,
               balance, referrals, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT 20
    """).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    conn.close()

    text = f"👥 Foydalanuvchilar: {total}\n\n"

    for row in rows:

        name = row["first_name"] or "Noma'lum"

        text += (
            f"👤 {name}\n"
            f"🆔 {row['user_id']}\n"
            f"⭐ {row['balance']:g}\n"
            f"👥 Ref: {row['referrals']}\n\n"
        )

    await update.message.reply_text(
        text,
        reply_markup=admin_menu()
    )


# ============================================================
# LOGS
# ============================================================

async def activity_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
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
            "📜 Loglar hozircha yo‘q.",
            reply_markup=admin_menu()
        )

        return

    text = "📜 So‘nggi faoliyatlar\n\n"

    for row in rows:

        text += (
            f"#{row['id']} | "
            f"{row['created_at']}\n"
            f"👤 {row['user_id']} "
            f"@{row['username'] or '-'}\n"
            f"🔹 {row['action']}\n"
            f"📝 {row['details']}\n\n"
        )

    await update.message.reply_text(
        text[:4000],
        reply_markup=admin_menu()
    )


# ============================================================
# ADMINLAR
# ============================================================

async def admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
        return

    rows = get_admins()

    keyboard = []

    text = "👑 Adminlar\n\n"

    for row in rows:

        uid = row["user_id"]

        text += f"🆔 {uid}"

        if uid == OWNER_ID:
            text += " — 👑 OWNER"

        text += "\n"

        if uid != OWNER_ID:

            keyboard.append([
                InlineKeyboardButton(
                    f"❌ O‘chirish {uid}",
                    callback_data=f"adminremove:{uid}"
                )
            ])

    keyboard.append([
        InlineKeyboardButton(
            "➕ Admin qo‘shish",
            callback_data="adminadd"
        )
    ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# ADMIN ADD
# ============================================================

async def admin_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    context.user_data["state"] = "add_admin"

    await query.edit_message_text(
        "➕ Yangi adminning Telegram ID'sini yuboring.\n\n"
        "Masalan:\n"
        "123456789"
    )


async def admin_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    target_id = int(query.data.split(":")[1])

    if target_id == OWNER_ID:

        await query.answer(
            "❌ Ownerni o‘chirib bo‘lmaydi.",
            show_alert=True
        )

        return

    remove_admin(target_id)

    await query.edit_message_text(
        f"✅ {target_id} adminlardan olib tashlandi."
    )


# ============================================================
# TASK CHANNELS
# ============================================================

async def task_channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
        return

    conn = db()

    rows = conn.execute(
        "SELECT * FROM channels ORDER BY id"
    ).fetchall()

    conn.close()

    text = "📢 Topshiriq kanallari\n\n"

    keyboard = []

    for row in rows:

        text += (
            f"#{row['id']} "
            f"{row['title']} — "
            f"{row['reward']} ⭐\n"
            f"{row['channel_id']}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"🗑 O‘chirish #{row['id']}",
                callback_data=f"taskchanneldelete:{row['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "➕ Kanal qo‘shish",
            callback_data="taskchanneladd"
        )
    ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def task_channel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    context.user_data["state"] = "add_task_channel_username"

    await query.edit_message_text(
        "➕ Kanal username'ini yuboring.\n\n"
        "Masalan:\n"
        "@mychannel"
    )


async def task_channel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    channel_id = int(
        query.data.split(":")[1]
    )

    conn = db()

    conn.execute(
        "DELETE FROM channels WHERE id=?",
        (channel_id,)
    )

    conn.commit()
    conn.close()

    await query.edit_message_text(
        "✅ Topshiriq kanali o‘chirildi."
    )


# ============================================================
# MAJBURIY KANALLAR
# ============================================================

async def mandatory_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
        return

    conn = db()

    rows = conn.execute(
        "SELECT * FROM mandatory_channels ORDER BY id"
    ).fetchall()

    conn.close()

    text = "📌 Majburiy kanallar\n\n"

    if not rows:
        text += "Hozircha majburiy kanal yo‘q.\n"

    keyboard = []

    for row in rows:

        text += (
            f"#{row['id']} "
            f"{row['title']}\n"
            f"{row['channel_id']}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"✏️ Almashtirish #{row['id']}",
                callback_data=f"mandatoryedit:{row['id']}"
            ),
            InlineKeyboardButton(
                f"🗑 O‘chirish #{row['id']}",
                callback_data=f"mandatorydelete:{row['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "➕ Majburiy kanal qo‘shish",
            callback_data="mandatoryadd"
        )
    ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def mandatory_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    context.user_data["state"] = "mandatory_add_channel"

    await query.edit_message_text(
        "📌 Majburiy kanal qo‘shish\n\n"
        "Kanal username'ini yuboring.\n\n"
        "Masalan:\n"
        "@mychannel"
    )


async def mandatory_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    channel_id = int(query.data.split(":")[1])

    context.user_data["state"] = "mandatory_edit_channel"
    context.user_data["mandatory_id"] = channel_id

    await query.edit_message_text(
        "✏️ Yangi kanal username'ini yuboring."
    )


async def mandatory_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    channel_id = int(query.data.split(":")[1])

    conn = db()

    conn.execute(
        "DELETE FROM mandatory_channels WHERE id=?",
        (channel_id,)
    )

    conn.commit()
    conn.close()

    await query.edit_message_text(
        "✅ Majburiy kanal o‘chirildi."
    )


# ============================================================
# ADVERTISING
# ============================================================

async def advertiser(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    context.user_data["state"] = "advertiser"

    await update.message.reply_text(
        "📢 Reklama / Admin bilan aloqa\n\n"
        "Reklamangiz yoki taklifingizni bitta xabarda yozing.\n\n"
        "Masalan:\n"
        "• Reklama narxi\n"
        "• Kanal username\n"
        "• Reklama turi",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 Orqaga"]],
            resize_keyboard=True
        )
    )

    log_activity(user, "ADVERTISER_OPEN")


async def advertiser_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

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

    if not rows:

        await update.message.reply_text(
            "📣 Reklama so‘rovlari yo‘q.",
            reply_markup=admin_menu()
        )

        return

    text = "📣 Reklama so‘rovlari\n\n"

    for row in rows:

        text += (
            f"#{row['id']} | {row['created_at']}\n"
            f"👤 {row['user_id']} "
            f"@{row['username'] or '-'}\n"
            f"📩 {row['message']}\n"
            f"📌 {row['status']}\n\n"
        )

    await update.message.reply_text(
        text[:4000],
        reply_markup=admin_menu()
    )


# ============================================================
# GIFT REQUESTS ADMIN
# ============================================================

async def gift_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_admin(user.id):
        return

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM gift_requests
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "🎁 Buyurtmalar yo‘q.",
            reply_markup=admin_menu()
        )

        return

    text = "🎁 Gift so‘rovlari\n\n"

    for row in rows:

        text += (
            f"#{row['id']}\n"
            f"👤 {row['user_id']}\n"
            f"⭐ {row['price']}\n"
            f"📌 {row['status']}\n\n"
        )

    await update.message.reply_text(
        text,
        reply_markup=admin_menu()
    )


# ============================================================
# MANDATORY CHECK
# ============================================================

async def check_mandatory(user_id, context):

    conn = db()

    rows = conn.execute(
        "SELECT * FROM mandatory_channels"
    ).fetchall()

    conn.close()

    missing = []

    for row in rows:

        try:

            member = await context.bot.get_chat_member(
                row["channel_id"],
                user_id
            )

            if member.status not in (
                "member",
                "administrator",
                "creator"
            ):
                missing.append(row)

        except:

            missing.append(row)

    return missing


# ============================================================
# TEXT ROUTER
# ============================================================

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    text = update.message.text

    state = context.user_data.get("state")

    # --------------------------------------------------------
    # ORQAGA
    # --------------------------------------------------------

    if text == "🔙 Orqaga":

        context.user_data.clear()

        await update.message.reply_text(
            "🏠 Bosh menyu",
            reply_markup=user_menu(user.id)
        )

        return

    # --------------------------------------------------------
    # ADMIN STATE
    # --------------------------------------------------------

    if is_admin(user.id):

        if state == "add_admin":

            try:

                target_id = int(text)

                add_admin(target_id)

                context.user_data.clear()

                await update.message.reply_text(
                    f"✅ {target_id} admin qilindi.",
                    reply_markup=admin_menu()
                )

                await notify_admins(
                    context,
                    f"👑 Yangi admin qo‘shildi:\n{target_id}"
                )

            except:

                await update.message.reply_text(
                    "❌ Telegram ID noto‘g‘ri."
                )

            return

        # ----------------------------------------------------
        # TASK CHANNEL ADD
        # ----------------------------------------------------

        if state == "add_task_channel_username":

            context.user_data["new_channel"] = text
            context.user_data["state"] = "add_task_channel_title"

            await update.message.reply_text(
                "Kanal nomini yuboring."
            )

            return

        if state == "add_task_channel_title":

            context.user_data["new_title"] = text
            context.user_data["state"] = "add_task_channel_reward"

            await update.message.reply_text(
                f"Mukofot miqdorini yuboring.\n"
                f"Masalan: {DEFAULT_TASK_REWARD}"
            )

            return

        if state == "add_task_channel_reward":

            try:

                reward = float(text.replace(",", "."))

                channel = context.user_data["new_channel"]
                title = context.user_data["new_title"]

                conn = db()

                conn.execute("""
                    INSERT OR REPLACE INTO channels
                    (channel_id, title, reward, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    channel,
                    title,
                    reward,
                    datetime.now().isoformat()
                ))

                conn.commit()
                conn.close()

                context.user_data.clear()

                await update.message.reply_text(
                    "✅ Topshiriq kanali qo‘shildi.",
                    reply_markup=admin_menu()
                )

            except Exception as e:

                await update.message.reply_text(
                    f"❌ Xato: {e}"
                )

            return

        # ----------------------------------------------------
        # MANDATORY CHANNEL ADD
        # ----------------------------------------------------

        if state == "mandatory_add_channel":

            channel = text.strip()

            context.user_data["mandatory_channel"] = channel
            context.user_data["state"] = "mandatory_add_title"

            await update.message.reply_text(
                "Kanal nomini yuboring."
            )

            return

        if state == "mandatory_add_title":

            channel = context.user_data["mandatory_channel"]
            title = text.strip()

            conn = db()

            try:

                conn.execute("""
                    INSERT INTO mandatory_channels
                    (channel_id, title, created_at)
                    VALUES (?, ?, ?)
                """, (
                    channel,
                    title,
                    datetime.now().isoformat()
                ))

                conn.commit()

                context.user_data.clear()

                await update.message.reply_text(
                    "✅ Majburiy kanal qo‘shildi.",
                    reply_markup=admin_menu()
                )

            except sqlite3.IntegrityError:

                await update.message.reply_text(
                    "❌ Bu kanal allaqachon mavjud."
                )

            finally:

                conn.close()

            return

        # ----------------------------------------------------
        # MANDATORY CHANNEL EDIT
        # ----------------------------------------------------

        if state == "mandatory_edit_channel":

            channel_id = context.user_data["mandatory_id"]

            conn = db()

            conn.execute("""
                UPDATE mandatory_channels
                SET channel_id=?
                WHERE id=?
            """, (
                text.strip(),
                channel_id
            ))

            conn.commit()
            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Majburiy kanal almashtirildi.",
                reply_markup=admin_menu()
            )

            return

    # --------------------------------------------------------
    # ADVERTISER
    # --------------------------------------------------------

    if state == "advertiser":

        conn = db()

        cur = conn.execute("""
            INSERT INTO advertiser_requests
            (user_id, username, message, status, created_at)
            VALUES (?, ?, ?, 'new', ?)
        """, (
            user.id,
            user.username or "",
            text,
            datetime.now().isoformat()
        ))

        request_id = cur.lastrowid

        conn.commit()
        conn.close()

        context.user_data.clear()

        log_activity(
            user,
            "ADVERTISER_MESSAGE",
            f"request={request_id}"
        )

        await update.message.reply_text(
            "✅ Xabaringiz adminlarga yuborildi.\n\n"
            "Admin siz bilan bog‘lanadi.",
            reply_markup=user_menu(user.id)
        )

        await notify_admins(
            context,
            f"📢 Yangi reklama so‘rovi!\n\n"
            f"🆔 #{request_id}\n"
            f"👤 {user.first_name}\n"
            f"Telegram ID: {user.id}\n"
            f"Username: @{user.username or '-'}\n\n"
            f"📩 Xabar:\n{text}"
        )

        return

    # --------------------------------------------------------
    # USER MENU
    # --------------------------------------------------------

    if text == "⭐ Stars ishlash":

        await stars_menu(update, context)

    elif text == "👥 Referal":

        await referral(update, context)

    elif text == "📊 Statistika":

        await statistics(update, context)

    elif text == "💳 Gift olish":

        await gift_menu(update, context)

    elif text == "ℹ️ Qoidalar":

        await rules(update, context)

    elif text == "📢 Reklama":

        await advertiser(update, context)

    elif text == "👑 Admin panel":

        await admin_panel(update, context)

    # --------------------------------------------------------
    # ADMIN MENU
    # --------------------------------------------------------

    elif text == "📊 Bot statistikasi":

        await bot_statistics(update, context)

    elif text == "👥 Foydalanuvchilar":

        await users_statistics(update, context)

    elif text == "📜 Faoliyat loglari":

        await activity_logs(update, context)

    elif text == "👑 Adminlar":

        await admins_menu(update, context)

    elif text == "📌 Majburiy kanallar":

        await mandatory_menu(update, context)

    elif text == "📢 Topshiriq kanallari":

        await task_channels_menu(update, context)

    elif text == "🎁 Gift so‘rovlari":

        await gift_requests(update, context)

    elif text == "📣 Reklama so‘rovlari":

        await advertiser_requests(update, context)

    else:

        await update.message.reply_text(
            "Menyudan foydalaning:",
            reply_markup=user_menu(user.id)
        )


# ============================================================
# CALLBACK ROUTER
# ============================================================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    data = query.data

    # --------------------------------------------------------
    # BACK MAIN
    # --------------------------------------------------------

    if data == "back:main":

        await query.answer()

        await query.message.delete()

        await context.bot.send_message(
            query.from_user.id,
            "🏠 Bosh menyu",
            reply_markup=user_menu(query.from_user.id)
        )

        return

    # --------------------------------------------------------
    # BACK STARS
    # --------------------------------------------------------

    if data == "back:stars":

        await query.answer()

        user = query.from_user

        conn = db()

        channels = conn.execute(
            "SELECT * FROM channels ORDER BY id"
        ).fetchall()

        completed = conn.execute("""
            SELECT task_id
            FROM completed_tasks
            WHERE user_id=?
        """, (
            user.id,
        )).fetchall()

        conn.close()

        completed_ids = {
            r["task_id"]
            for r in completed
        }

        keyboard = []

        for ch in channels:

            status = (
                "✅"
                if ch["id"] in completed_ids
                else f"⭐ +{ch['reward']}"
            )

            keyboard.append([
                InlineKeyboardButton(
                    f"{status} {ch['title']}",
                    callback_data=f"task:{ch['id']}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back:main"
            )
        ])

        await query.edit_message_text(
            "⭐ Stars ishlash",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # --------------------------------------------------------
    # TASK
    # --------------------------------------------------------

    if data.startswith("task:"):

        await task_callback(update, context)

        return

    if data.startswith("check:"):

        await check_task(update, context)

        return

    # --------------------------------------------------------
    # GIFT
    # --------------------------------------------------------

    if data.startswith("gift:"):

        await gift_callback(update, context)

        return

    if data.startswith("confirmgift:"):

        await confirm_gift(update, context)

        return

    # --------------------------------------------------------
    # ADMIN ADD
    # --------------------------------------------------------

    if data == "adminadd":

        await admin_add_callback(update, context)

        return

    if data.startswith("adminremove:"):

        await admin_remove_callback(update, context)

        return

    # --------------------------------------------------------
    # TASK CHANNEL
    # --------------------------------------------------------

    if data == "taskchanneladd":

        await task_channel_add(update, context)

        return

    if data.startswith("taskchanneldelete:"):

        await task_channel_delete(update, context)

        return

    # --------------------------------------------------------
    # MANDATORY
    # --------------------------------------------------------

    if data == "mandatoryadd":

        await mandatory_add_callback(update, context)

        return

    if data.startswith("mandatoryedit:"):

        await mandatory_edit_callback(update, context)

        return

    if data.startswith("mandatorydelete:"):

        await mandatory_delete_callback(update, context)

        return

    await query.answer()


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update, context):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    init_db()

    print("=" * 50)
    print("FROSTSTARS BOT IS STARTING...")
    print("=" * 50)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    # Callback
    application.add_handler(
        CallbackQueryHandler(callback_router)
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_router
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("BOT IS RUNNING...")
    print("Token: loaded")
    print()

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()