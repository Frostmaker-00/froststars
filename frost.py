import os
import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
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
        "BOT_TOKEN topilmadi. FadeHost Environment Variables bo'limiga "
        "BOT_TOKEN qo'shing."
    )

OWNER_ID = 6383248812
SUBSCRIPTION_DAYS = 2
REFERRAL_REWARD = 1.50
DEFAULT_TASK_REWARD = 0.10

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("FrostStars")


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_columns(cur, table, columns):
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}

    for name, definition in columns.items():
        if name not in existing:
            try:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                )
            except sqlite3.OperationalError:
                pass


def init_db():
    conn = db()
    cur = conn.cursor()

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT DEFAULT '',
            title TEXT DEFAULT '',
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
    """)

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS skipped_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            skipped_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            reward REAL DEFAULT 0,
            subscribed_at TEXT,
            expires_at TEXT,
            last_checked_at TEXT,
            valid INTEGER DEFAULT 1,
            UNIQUE(user_id, task_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            emoji TEXT DEFAULT '🎁',
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_id INTEGER,
            gift_name TEXT,
            price REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
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
            action TEXT,
            details TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            username TEXT DEFAULT '',
            title TEXT DEFAULT '',
            invite_link TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    # Old starbot.db files can have older schemas.
    ensure_columns(cur, "channels", {
        "username": "TEXT DEFAULT ''",
        "title": "TEXT DEFAULT ''",
        "reward": "REAL DEFAULT 0.1",
        "created_at": "TEXT",
    })

    ensure_columns(cur, "completed_tasks", {
        "reward": "REAL DEFAULT 0",
        "completed_at": "TEXT",
    })

    ensure_columns(cur, "task_subscriptions", {
        "reward": "REAL DEFAULT 0",
        "subscribed_at": "TEXT",
        "expires_at": "TEXT",
        "last_checked_at": "TEXT",
        "valid": "INTEGER DEFAULT 1",
    })

    ensure_columns(cur, "gifts", {
        "name": "TEXT DEFAULT ''",
        "price": "REAL DEFAULT 0",
        "emoji": "TEXT DEFAULT '🎁'",
        "active": "INTEGER DEFAULT 1",
        "created_at": "TEXT",
    })

    ensure_columns(cur, "gift_requests", {
        "gift_id": "INTEGER",
        "gift_name": "TEXT",
        "price": "REAL DEFAULT 0",
        "status": "TEXT DEFAULT 'pending'",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    })

    cur.execute(
        "INSERT OR IGNORE INTO admins(user_id, added_at) VALUES(?, ?)",
        (OWNER_ID, datetime.now().isoformat()),
    )

    # Default task channels. Change/delete them from admin panel if needed.
    for username, title in [
        ("@Cossmoss_00", "Cossmoss"),
        ("@PromptLab_UZ", "PromptLab UZ"),
    ]:
        cur.execute(
            "SELECT id FROM channels WHERE username = ? LIMIT 1",
            (username,),
        )
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO channels(username, title, reward, created_at)
                VALUES(?, ?, ?, ?)
            """, (
                username,
                title,
                DEFAULT_TASK_REWARD,
                datetime.now().isoformat(),
            ))

    # Default gift catalogue. Admin can add more and choose prices.
    cur.execute("SELECT COUNT(*) FROM gifts")
    if cur.fetchone()[0] == 0:
        default_gifts = [
            ("❤️", "Heart", 5),
            ("🌹", "Rose", 10),
            ("🌷", "Tulip", 12),
            ("🌻", "Sunflower", 15),
            ("💐", "Bouquet", 20),
            ("🍫", "Chocolate", 25),
            ("🧸", "Teddy Bear", 30),
            ("🎁", "Gift Box", 40),
            ("💎", "Diamond", 50),
            ("🏆", "Trophy", 75),
            ("👑", "Crown", 100),
            ("🚀", "Rocket", 150),
            ("💖", "Love", 200),
            ("🌟", "Star", 250),
            ("🦄", "Unicorn", 300),
        ]
        for emoji, name, price in default_gifts:
            cur.execute("""
                INSERT INTO gifts(emoji, name, price, active, created_at)
                VALUES(?, ?, ?, 1, ?)
            """, (emoji, name, price, datetime.now().isoformat()))

    conn.commit()
    conn.close()


# =========================================================
# BASIC HELPERS
# =========================================================

def add_user(user):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users(
            user_id, username, first_name, balance,
            referral_count, referred_by, created_at
        )
        VALUES(?, ?, ?, 0, 0, NULL, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.now().isoformat(),
    ))

    cur.execute("""
        UPDATE users
        SET username = ?, first_name = ?
        WHERE user_id = ?
    """, (user.username or "", user.first_name or "", user.id))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def change_balance(user_id, amount):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


def log_activity(user_id, action, details=""):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO activity_logs(user_id, action, details, created_at)
            VALUES(?, ?, ?, ?)
        """, (user_id, action, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("log_activity error")


# =========================================================
# ADMIN
# =========================================================

def is_owner(user_id):
    return user_id == OWNER_ID


def is_admin(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    ok = cur.fetchone() is not None
    conn.close()
    return ok


def add_admin(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO admins(user_id, added_at) VALUES(?, ?)",
        (user_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def remove_admin(user_id):
    if user_id == OWNER_ID:
        return False
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


# =========================================================
# MENUS
# =========================================================

def main_menu(user_id):
    rows = [
        ["⭐ Stars ishlash", "🎁 Gift olish"],
        ["👥 Referral", "💰 Balans"],
        ["📜 Qoidalar", "📢 Reklama"],
    ]
    if is_admin(user_id):
        rows.append(["⚙️ Admin panel"])

    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_menu():
    return ReplyKeyboardMarkup([
        ["📊 Statistika"],
        ["👥 Foydalanuvchilar", "📝 Loglar"],
        ["📢 Vazifa kanallari", "🎁 Giftlar"],
        ["🎁 Gift so‘rovlari", "🔐 Majburiy kanallar"],
        ["👑 Adminlar", "📣 Reklama so‘rovlari"],
        ["⬅️ Orqaga"],
    ], resize_keyboard=True)


# =========================================================
# MANDATORY CHANNELS
# =========================================================

def get_mandatory_channels():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mandatory_channels ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


async def check_mandatory(user_id, context):
    channels = get_mandatory_channels()
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(
                channel["channel_id"], user_id
            )
            if member.status in ("member", "administrator", "creator"):
                continue
            if member.status == "restricted" and getattr(member, "is_member", False):
                continue
            return False
        except Exception as e:
            logger.warning(
                "Mandatory channel check failed for %s: %s",
                channel["channel_id"], e
            )
            # If bot cannot inspect a mandatory channel, don't lock everyone out.
            continue
    return True


async def send_mandatory(update, context):
    keyboard = []
    for channel in get_mandatory_channels():
        link = channel["invite_link"] or ""
        if not link and channel["username"]:
            link = "https://t.me/" + channel["username"].replace("@", "")
        if link:
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 {channel['title']}", url=link
                )
            ])

    keyboard.append([
        InlineKeyboardButton("✅ Tekshirish", callback_data="mandatory_check")
    ])

    text = (
        "🔐 Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )


# =========================================================
# START
# =========================================================

async def start(update, context):
    user = update.effective_user
    add_user(user)

    # One-time referral registration.
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                conn = db()
                cur = conn.cursor()

                cur.execute(
                    "SELECT referred_by FROM users WHERE user_id = ?",
                    (user.id,),
                )
                current = cur.fetchone()

                cur.execute(
                    "SELECT user_id FROM users WHERE user_id = ?",
                    (referrer_id,),
                )
                referrer = cur.fetchone()

                if current and current["referred_by"] is None and referrer:
                    cur.execute("""
                        UPDATE users SET referred_by = ?
                        WHERE user_id = ?
                    """, (referrer_id, user.id))

                    cur.execute("""
                        UPDATE users
                        SET referral_count = referral_count + 1,
                            balance = balance + ?
                        WHERE user_id = ?
                    """, (REFERRAL_REWARD, referrer_id))

                    conn.commit()
                    log_activity(
                        referrer_id, "referral",
                        f"new referral {user.id}"
                    )

                conn.close()
        except Exception:
            logger.exception("Referral error")

    if not await check_mandatory(user.id, context):
        await send_mandatory(update, context)
        return

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "⭐ FrostStars botiga xush kelibsiz!",
        reply_markup=main_menu(user.id),
    )


# =========================================================
# TASKS
# =========================================================

def get_tasks():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


def task_was_seen(user_id, task_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1 FROM completed_tasks
        WHERE user_id = ? AND task_id = ?
        LIMIT 1
    """, (user_id, task_id))
    if cur.fetchone():
        conn.close()
        return True

    cur.execute("""
        SELECT 1 FROM skipped_tasks
        WHERE user_id = ? AND task_id = ?
        LIMIT 1
    """, (user_id, task_id))
    result = cur.fetchone() is not None
    conn.close()
    return result


def get_next_task(user_id):
    for task in get_tasks():
        if not task_was_seen(user_id, task["id"]):
            return task
    return None


def task_keyboard(task):
    username = (task["username"] or "").replace("@", "")
    buttons = []

    if username:
        buttons.append([
            InlineKeyboardButton(
                f"📢 {task['title']}",
                url=f"https://t.me/{username}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Obuna bo‘ldim",
            callback_data=f"task_check:{task['id']}"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            "⏭️ Vazifani o'tkazib yuborish",
            callback_data=f"task_skip:{task['id']}"
        )
    ])
    buttons.append([
        InlineKeyboardButton("⬅️ Orqaga", callback_data="stars_menu")
    ])
    return InlineKeyboardMarkup(buttons)


async def show_task_message(query, user_id, context):
    task = get_next_task(user_id)

    if not task:
        await query.edit_message_text(
            "🎉 Barcha vazifalarni ko‘rib chiqdingiz!\n\n"
            "Hozircha yangi vazifa yo‘q."
        )
        return

    await query.edit_message_text(
        "🎯 Vazifa\n\n"
        f"📢 {task['title']}\n"
        f"⭐ Mukofot: {float(task['reward']):g} Stars\n\n"
        "1️⃣ Kanalga obuna bo‘ling\n"
        "2️⃣ «Obuna bo‘ldim» tugmasini bosing\n"
        "3️⃣ Tekshiruvdan o‘ting\n\n"
        f"⚠️ Mukofotdan keyin {SUBSCRIPTION_DAYS} kun "
        "kanalda qolish kerak.",
        reply_markup=task_keyboard(task),
    )


async def stars_menu(update, context):
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🎯 Vazifalarni boshlash",
            callback_data="task_start"
        )],
        [InlineKeyboardButton(
            "💰 Balans",
            callback_data="balance"
        )],
        [InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="main_menu"
        )],
    ])

    await query.edit_message_text(
        "⭐ Stars ishlash\n\n"
        "Vazifalarni bajaring va Stars oling.",
        reply_markup=keyboard,
    )


async def task_start(update, context):
    query = update.callback_query
    await query.answer()
    await show_task_message(query, query.from_user.id, context)


async def check_task(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    try:
        task_id = int(query.data.split(":")[1])
    except Exception:
        await query.answer("❌ Vazifa ID xato.", show_alert=True)
        return

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels WHERE id = ?", (task_id,))
    task = cur.fetchone()

    cur.execute("""
        SELECT 1 FROM completed_tasks
        WHERE user_id = ? AND task_id = ?
        LIMIT 1
    """, (user_id, task_id))
    completed = cur.fetchone()
    conn.close()

    if not task:
        await query.answer("❌ Vazifa topilmadi.", show_alert=True)
        return

    if completed:
        await query.answer(
            "⚠️ Bu vazifa oldin bajarilgan.",
            show_alert=True
        )
        return

    await query.answer("🔎 Tekshirilmoqda...")

    username = (task["username"] or "").strip()
    if not username:
        await query.answer(
            "❌ Kanal username'i yo‘q.",
            show_alert=True
        )
        return

    try:
        member = await context.bot.get_chat_member(
            username, user_id
        )
        if member.status not in ("member", "administrator", "creator"):
            if not (
                member.status == "restricted"
                and getattr(member, "is_member", False)
            ):
                await query.answer(
                    "❌ Avval kanalga obuna bo‘ling.",
                    show_alert=True
                )
                return
    except Exception as e:
        logger.exception("Task channel check error: %s", e)
        await query.answer(
            "❌ Kanalni tekshirib bo‘lmadi. "
            "Bot kanalga admin ekanini tekshiring.",
            show_alert=True
        )
        return

    reward = float(task["reward"])
    now = datetime.now()
    expires = now + timedelta(days=SUBSCRIPTION_DAYS)

    conn = db()
    cur = conn.cursor()

    try:
        # Atomic transaction: reward, completed row and subscription row
        # are either all written or none are written.
        cur.execute("BEGIN")

        cur.execute("""
            INSERT INTO completed_tasks(
                user_id, task_id, reward, completed_at
            )
            VALUES(?, ?, ?, ?)
        """, (user_id, task_id, reward, now.isoformat()))

        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (reward, user_id))

        if cur.rowcount != 1:
            raise RuntimeError("User topilmadi")

        cur.execute("""
            INSERT INTO task_subscriptions(
                user_id, task_id, reward, subscribed_at,
                expires_at, last_checked_at, valid
            )
            VALUES(?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id, task_id) DO UPDATE SET
                reward = excluded.reward,
                subscribed_at = excluded.subscribed_at,
                expires_at = excluded.expires_at,
                last_checked_at = excluded.last_checked_at,
                valid = 1
        """, (
            user_id,
            task_id,
            reward,
            now.isoformat(),
            expires.isoformat(),
            now.isoformat(),
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
        logger.exception("REWARD ERROR: %s", e)
        await query.answer(
            "❌ Mukofot berishda xatolik. "
            "Server logini tekshiring.",
            show_alert=True
        )
        return

    conn.close()

    log_activity(
        user_id,
        "task_completed",
        f"{task['title']} +{reward}"
    )

    # Delete the old task message so it appears only once.
    try:
        await query.message.delete()
    except Exception:
        pass

    # Immediately show the next task.
    next_task = get_next_task(user_id)

    if next_task:
        await context.bot.send_message(
            user_id,
            "🎉 Vazifa bajarildi!\n\n"
            f"📢 {task['title']}\n"
            f"⭐ +{reward:g} Stars\n\n"
            f"⚠️ {SUBSCRIPTION_DAYS} kun kanalni tark etmang.\n"
            "Aks holda shu vazifa uchun berilgan Stars "
            "balansdan qaytarib olinadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "➡️ Keyingi vazifa",
                    callback_data="task_start"
                )],
                [InlineKeyboardButton(
                    "💰 Balans",
                    callback_data="balance"
                )],
            ]),
        )
    else:
        await context.bot.send_message(
            user_id,
            "🎉 Vazifa bajarildi!\n\n"
            f"📢 {task['title']}\n"
            f"⭐ +{reward:g} Stars\n\n"
            f"⚠️ {SUBSCRIPTION_DAYS} kun kanalni tark etmang.\n"
            "Barcha mavjud vazifalar tugadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "💰 Balans",
                    callback_data="balance"
                )],
                [InlineKeyboardButton(
                    "⬅️ Stars",
                    callback_data="stars_menu"
                )],
            ]),
        )


async def skip_task(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    try:
        task_id = int(query.data.split(":")[1])
    except Exception:
        await query.answer("❌ Vazifa ID xato.", show_alert=True)
        return

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels WHERE id = ?", (task_id,))
    task = cur.fetchone()

    if not task:
        conn.close()
        await query.answer("❌ Vazifa topilmadi.", show_alert=True)
        return

    try:
        cur.execute("""
            INSERT INTO skipped_tasks(user_id, task_id, skipped_at)
            VALUES(?, ?, ?)
        """, (user_id, task_id, datetime.now().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
    finally:
        conn.close()

    log_activity(user_id, "task_skipped", task["title"])
    await query.answer("⏭️ Vazifa o'tkazib yuborildi.")

    try:
        await query.message.delete()
    except Exception:
        pass

    next_task = get_next_task(user_id)
    if next_task:
        await context.bot.send_message(
            user_id,
            "🎯 Keyingi vazifa\n\n"
            f"📢 {next_task['title']}\n"
            f"⭐ Mukofot: {float(next_task['reward']):g} Stars\n\n"
            "Kanalga obuna bo‘ling va tekshirtiring.",
            reply_markup=task_keyboard(next_task),
        )
    else:
        await context.bot.send_message(
            user_id,
            "🎉 Hozircha boshqa vazifa qolmadi."
        )


# =========================================================
# 2-DAY SUBSCRIPTION / CLAWBACK
# =========================================================

async def check_two_day_subscriptions(context):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT ts.*, c.username, c.title
        FROM task_subscriptions ts
        JOIN channels c ON c.id = ts.task_id
        WHERE ts.valid = 1
    """)
    subscriptions = cur.fetchall()
    conn.close()

    for sub in subscriptions:
        user_id = sub["user_id"]
        reward = float(sub["reward"] or 0)

        try:
            expires = datetime.fromisoformat(sub["expires_at"])
        except Exception:
            continue

        # The two-day period finished successfully.
        if datetime.now() >= expires:
            conn = db()
            cur = conn.cursor()
            cur.execute("""
                UPDATE task_subscriptions
                SET valid = 0, last_checked_at = ?
                WHERE id = ? AND valid = 1
            """, (datetime.now().isoformat(), sub["id"]))
            changed = cur.rowcount
            conn.commit()
            conn.close()

            if changed:
                log_activity(
                    user_id,
                    "subscription_completed",
                    f"{sub['title']} 2 kun tugadi"
                )
            continue

        try:
            member = await context.bot.get_chat_member(
                sub["username"], user_id
            )
            still_subscribed = member.status in (
                "member", "administrator", "creator"
            )
            if (
                member.status == "restricted"
                and getattr(member, "is_member", False)
            ):
                still_subscribed = True
        except Exception as e:
            logger.warning(
                "2-day check error user=%s task=%s: %s",
                user_id, sub["task_id"], e
            )
            continue

        if still_subscribed:
            conn = db()
            cur = conn.cursor()
            cur.execute("""
                UPDATE task_subscriptions
                SET last_checked_at = ?
                WHERE id = ? AND valid = 1
            """, (datetime.now().isoformat(), sub["id"]))
            conn.commit()
            conn.close()
            continue

        # User left before 2 days: invalidate and remove the exact reward.
        conn = db()
        cur = conn.cursor()
        cur.execute("BEGIN")

        cur.execute("""
            UPDATE task_subscriptions
            SET valid = 0, last_checked_at = ?
            WHERE id = ? AND valid = 1
        """, (datetime.now().isoformat(), sub["id"]))
        changed = cur.rowcount

        if changed:
            cur.execute("""
                UPDATE users
                SET balance = MAX(0, balance - ?)
                WHERE user_id = ?
            """, (reward, user_id))

        conn.commit()
        conn.close()

        if changed:
            log_activity(
                user_id,
                "reward_removed",
                f"{sub['title']} -{reward}"
            )
            try:
                await context.bot.send_message(
                    user_id,
                    "⚠️ Siz vazifa kanalidan 2 kun tugamasdan chiqdingiz.\n\n"
                    f"📢 {sub['title']}\n"
                    f"⭐ -{reward:g} Stars\n\n"
                    "Berilgan mukofot balansdan qaytarib olindi."
                )
            except Exception:
                pass


async def subscription_loop(application):
    while True:
        try:
            await check_two_day_subscriptions(application)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Subscription checker error")
        await asyncio.sleep(1800)  # every 30 minutes


async def post_init(application):
    application.bot_data["subscription_task"] = asyncio.create_task(
        subscription_loop(application)
    )


async def post_shutdown(application):
    task = application.bot_data.get("subscription_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# =========================================================
# BALANCE / REFERRAL / RULES
# =========================================================

async def show_balance(update, context):
    query = update.callback_query
    if query:
        await query.answer()
        row = get_user(query.from_user.id)
        await query.edit_message_text(
            "💰 Balans\n\n"
            f"⭐ {float(row['balance']):.2f} Stars",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "⬅️ Orqaga", callback_data="main_menu"
                )]
            ]),
        )
        return

    user = update.effective_user
    row = get_user(user.id)
    await update.message.reply_text(
        "💰 Balansingiz:\n\n"
        f"⭐ {float(row['balance']):.2f} Stars"
    )


async def referral(update, context):
    user = update.effective_user
    row = get_user(user.id)
    bot = await context.bot.get_me()

    await update.message.reply_text(
        "👥 Referral\n\n"
        f"⭐ Bir referral: {REFERRAL_REWARD:g}\n"
        f"👤 Referral soni: {row['referral_count']}\n\n"
        f"🔗 Sizning linkingiz:\n"
        f"https://t.me/{bot.username}?start={user.id}"
    )


async def rules(update, context):
    await update.message.reply_text(
        "📜 FrostStars qoidalari\n\n"
        "1. Har bir vazifa faqat bir marta mukofot beradi.\n"
        "2. Vazifani o'tkazib yuborish mumkin.\n"
        "3. Mukofot olish uchun kanalga obuna bo‘lish kerak.\n"
        f"4. Mukofotdan keyin {SUBSCRIPTION_DAYS} kun kanalda qolish kerak.\n"
        "5. 2 kun tugamasdan chiqib ketsangiz, shu vazifa mukofoti "
        "balansdan qaytarib olinadi.\n"
        "6. Soxta akkauntlardan foydalanish taqiqlanadi."
    )


# =========================================================
# GIFTS
# =========================================================

def get_gifts(active_only=True):
    conn = db()
    cur = conn.cursor()

    if active_only:
        cur.execute(
            "SELECT * FROM gifts WHERE active = 1 ORDER BY price ASC"
        )
    else:
        cur.execute("SELECT * FROM gifts ORDER BY id DESC")

    rows = cur.fetchall()
    conn.close()
    return rows


async def gifts_menu(update, context):
    gifts = get_gifts()

    if not gifts:
        await update.message.reply_text("🎁 Hozircha giftlar mavjud emas.")
        return

    keyboard = []
    for gift in gifts:
        keyboard.append([
            InlineKeyboardButton(
                f"{gift['emoji']} {gift['name']} — ⭐ {gift['price']:g}",
                callback_data=f"gift:{gift['id']}"
            )
        ])

    await update.message.reply_text(
        "🎁 Gift olish\n\nGiftni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def gift_info(update, context):
    query = update.callback_query
    await query.answer()

    try:
        gift_id = int(query.data.split(":")[1])
    except Exception:
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
        await query.answer("❌ Gift topilmadi.", show_alert=True)
        return

    await query.edit_message_text(
        f"{gift['emoji']} {gift['name']}\n\n"
        f"⭐ Narxi: {float(gift['price']):g}\n\n"
        "Sotib olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "✅ Tasdiqlash", callback_data=f"gift_buy:{gift_id}"
            )],
            [InlineKeyboardButton(
                "❌ Bekor qilish", callback_data="gift_cancel"
            )],
        ]),
    )


async def buy_gift(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    try:
        gift_id = int(query.data.split(":")[1])
    except Exception:
        return

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM gifts WHERE id = ? AND active = 1",
        (gift_id,)
    )
    gift = cur.fetchone()

    if not gift:
        conn.close()
        await query.answer("❌ Gift topilmadi.", show_alert=True)
        return

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )
    user = cur.fetchone()

    balance = float(user["balance"]) if user else 0.0
    price = float(gift["price"])

    if not user or balance < price:
        conn.close()
        await query.answer(
            f"❌ Balans yetarli emas. Sizda ⭐ {balance:.2f}",
            show_alert=True
        )
        return

    now = datetime.now().isoformat()

    try:
        cur.execute("BEGIN")
        cur.execute("""
            UPDATE users
            SET balance = balance - ?
            WHERE user_id = ? AND balance >= ?
        """, (price, user_id, price))

        if cur.rowcount != 1:
            raise RuntimeError("Balans o'zgargan yoki yetarli emas")

        cur.execute("""
            INSERT INTO gift_requests(
                user_id, gift_id, gift_name, price,
                status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, 'pending', ?, ?)
        """, (
            user_id,
            gift_id,
            f"{gift['emoji']} {gift['name']}",
            price,
            now,
            now,
        ))

        request_id = cur.lastrowid
        conn.commit()

    except Exception as e:
        conn.rollback()
        conn.close()
        logger.exception("Gift purchase error: %s", e)
        await query.answer(
            "❌ Gift olishda xatolik.",
            show_alert=True
        )
        return

    conn.close()

    log_activity(
        user_id,
        "gift_request",
        f"#{request_id} {gift['name']} {price}"
    )

    await query.edit_message_text(
        "✅ Gift so‘rovi yuborildi!\n\n"
        f"{gift['emoji']} {gift['name']}\n"
        f"⭐ {price:g}\n"
        f"🆔 #{request_id}\n\n"
        "Admin so‘rovni ko‘rib chiqadi."
    )


# =========================================================
# ADVERTISING
# =========================================================

async def save_advertisement(update, context):
    user = update.effective_user
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO advertiser_requests(
            user_id, text, status, created_at
        )
        VALUES(?, ?, 'pending', ?)
    """, (
        user.id,
        update.message.text,
        datetime.now().isoformat(),
    ))

    request_id = cur.lastrowid
    conn.commit()
    conn.close()

    context.user_data.clear()

    await update.message.reply_text(
        f"✅ Reklama so‘rovi yuborildi.\n🆔 #{request_id}"
    )


# =========================================================
# ADMIN VIEWS
# =========================================================

async def admin_statistics(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
    balance = float(cur.fetchone()[0] or 0)

    cur.execute("SELECT COUNT(*) FROM completed_tasks")
    completed = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM gift_requests")
    gifts = cur.fetchone()[0]

    conn.close()

    await update.message.reply_text(
        "📊 Admin statistikasi\n\n"
        f"👥 Users: {users}\n"
        f"⭐ Umumiy balans: {balance:.2f}\n"
        f"🎯 Bajarilgan vazifalar: {completed}\n"
        f"🎁 Gift so‘rovlari: {gifts}"
    )


async def admin_users(update, context):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM users
        ORDER BY created_at DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("👥 Foydalanuvchilar yo‘q.")
        return

    text = "👥 Foydalanuvchilar\n\n"
    for u in rows:
        text += (
            f"🆔 {u['user_id']}\n"
            f"👤 {u['first_name']} "
            f"(@{u['username'] if u['username'] else 'yo‘q'})\n"
            f"⭐ {float(u['balance']):.2f}\n"
            f"👥 Ref: {u['referral_count']}\n\n"
        )

    await update.message.reply_text(text[:3900])


async def admin_logs(update, context):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM activity_logs
        ORDER BY id DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📝 Loglar yo‘q.")
        return

    text = "📝 Loglar\n\n"
    for row in rows:
        text += (
            f"#{row['id']} | {row['user_id']} | {row['action']}\n"
            f"{row['details']}\n\n"
        )
    await update.message.reply_text(text[:3900])


async def admin_list(update, context):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins ORDER BY added_at ASC")
    rows = cur.fetchall()
    conn.close()

    text = "👑 Adminlar\n\n"
    for row in rows:
        role = "OWNER" if row["user_id"] == OWNER_ID else "ADMIN"
        text += f"{role}: {row['user_id']}\n"

    text += "\n/addadmin USER_ID\n/removeadmin USER_ID"
    await update.message.reply_text(text)


async def admin_tasks(update, context):
    tasks = get_tasks()
    text = "📢 Vazifa kanallari\n\n"

    if not tasks:
        text += "Vazifa yo‘q.\n\n"

    for task in tasks:
        text += (
            f"🆔 {task['id']}\n"
            f"📢 {task['title']}\n"
            f"🔗 {task['username']}\n"
            f"⭐ {float(task['reward']):g}\n\n"
        )

    text += "/addtask — kanal qo‘shish\n/deltask ID — kanal o‘chirish"
    await update.message.reply_text(text)


async def admin_gifts(update, context):
    gifts = get_gifts(active_only=False)
    text = "🎁 Giftlar\n\n"

    if not gifts:
        text += "Gift yo‘q.\n"
    else:
        for gift in gifts:
            status = "✅" if gift["active"] else "❌"
            text += (
                f"{status} 🆔 {gift['id']}\n"
                f"{gift['emoji']} {gift['name']}\n"
                f"⭐ {float(gift['price']):g}\n\n"
            )

    text += (
        "/addgift — yangi gift qo‘shish\n"
        "/delgift ID — giftni o‘chirish"
    )
    await update.message.reply_text(text)


async def admin_gift_requests(update, context):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM gift_requests
        ORDER BY id DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("🎁 Gift so‘rovlari yo‘q.")
        return

    for row in rows:
        keyboard = []
        if row["status"] == "pending":
            keyboard = [[
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"gift_approve:{row['id']}"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"gift_reject:{row['id']}"
                ),
            ]]

        await update.message.reply_text(
            f"🎁 Gift request #{row['id']}\n\n"
            f"👤 User: {row['user_id']}\n"
            f"🎁 {row['gift_name']}\n"
            f"⭐ {float(row['price']):g}\n"
            f"📌 {row['status']}",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )


async def admin_mandatory(update, context):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mandatory_channels ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    text = "🔐 Majburiy kanallar\n\n"
    if not rows:
        text += "Hozircha yo‘q.\n\n"

    for row in rows:
        text += (
            f"🆔 DB ID: {row['id']}\n"
            f"📌 Telegram ID: {row['channel_id']}\n"
            f"📢 {row['title']}\n"
            f"🔗 {row['invite_link'] or 'yo‘q'}\n\n"
        )

    text += "/addmandatory\n/delmandatory ID"
    await update.message.reply_text(text)


async def admin_ad_requests(update, context):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM advertiser_requests
        ORDER BY id DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📣 Reklama so‘rovlari yo‘q.")
        return

    text = "📣 Reklama so‘rovlari\n\n"
    for row in rows:
        text += (
            f"#{row['id']} | User: {row['user_id']}\n"
            f"Status: {row['status']}\n"
            f"{row['text']}\n\n"
        )
    await update.message.reply_text(text[:3900])


# =========================================================
# ADMIN COMMANDS
# =========================================================

async def add_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/addadmin USER_ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID raqam bo‘lishi kerak.")
        return

    if not get_user(user_id):
        await update.message.reply_text(
            "❌ User avval botdan foydalanishi kerak."
        )
        return

    add_admin(user_id)
    await update.message.reply_text(f"✅ {user_id} admin qilindi.")


async def remove_admin_command(update, context):
    if not is_owner(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/removeadmin USER_ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID raqam bo‘lishi kerak.")
        return

    if remove_admin(user_id):
        await update.message.reply_text(f"✅ {user_id} adminlikdan olindi.")
    else:
        await update.message.reply_text("❌ Ownerni olib tashlab bo‘lmaydi.")


async def add_task(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data.clear()
    context.user_data["state"] = "task_username"
    await update.message.reply_text(
        "📢 Kanal username yuboring.\n\nMasalan: @mychannel"
    )


async def delete_task(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/deltask ID")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto‘g‘ri.")
        return

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id = ?", (task_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Vazifa o‘chirildi." if deleted else "❌ Vazifa topilmadi."
    )


async def add_gift(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data.clear()
    context.user_data["state"] = "gift_name"
    await update.message.reply_text("🎁 Gift nomini yuboring.")


async def delete_gift(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/delgift ID")
        return

    try:
        gift_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto‘g‘ri.")
        return

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE gifts SET active = 0 WHERE id = ?",
        (gift_id,)
    )
    changed = cur.rowcount
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Gift o‘chirildi." if changed else "❌ Gift topilmadi."
    )


async def add_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data.clear()
    context.user_data["state"] = "mandatory_id"
    await update.message.reply_text(
        "🔐 Kanal ID yuboring.\n\n"
        "Masalan:\n-1004425654134"
    )


async def delete_mandatory_command(update, context):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("/delmandatory ID")
        return

    try:
        row_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID noto‘g‘ri.")
        return

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM mandatory_channels WHERE id = ?",
        (row_id,)
    )
    changed = cur.rowcount
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Majburiy kanal o‘chirildi."
        if changed else "❌ Kanal topilmadi."
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(update, context):
    user = update.effective_user
    text = update.message.text or ""
    add_user(user)

    # During an active admin state, process that state first.
    state = context.user_data.get("state")

    if is_admin(user.id):
        if state == "task_username":
            username = text.strip()
            if not username.startswith("@"):
                username = "@" + username

            context.user_data["task_username"] = username
            context.user_data["state"] = "task_title"
            await update.message.reply_text("📢 Kanal nomini yuboring.")
            return

        if state == "task_title":
            context.user_data["task_title"] = text.strip()
            context.user_data["state"] = "task_reward"
            await update.message.reply_text(
                "⭐ Reward yuboring.\nMasalan: 0.1"
            )
            return

        if state == "task_reward":
            try:
                reward = float(text.replace(",", "."))
                if reward <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text(
                    "❌ Reward musbat raqam bo‘lishi kerak."
                )
                return

            username = context.user_data["task_username"]
            title = context.user_data["task_title"]

            conn = db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO channels(
                    username, title, reward, created_at
                )
                VALUES(?, ?, ?, ?)
            """, (
                username, title, reward, datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()

            context.user_data.clear()
            await update.message.reply_text(
                f"✅ Vazifa qo‘shildi!\n\n"
                f"📢 {title}\n"
                f"🔗 {username}\n"
                f"⭐ {reward:g}"
            )
            return

        if state == "gift_name":
            context.user_data["gift_name"] = text.strip()
            context.user_data["state"] = "gift_emoji"
            await update.message.reply_text(
                "😀 Gift emoji yuboring.\nMasalan: 🧸"
            )
            return

        if state == "gift_emoji":
            context.user_data["gift_emoji"] = text.strip()
            context.user_data["state"] = "gift_price"
            await update.message.reply_text(
                "⭐ Gift narxini yuboring.\nMasalan: 30"
            )
            return

        if state == "gift_price":
            try:
                price = float(text.replace(",", "."))
                if price <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ Narx noto‘g‘ri.")
                return

            conn = db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO gifts(
                    name, price, emoji, active, created_at
                )
                VALUES(?, ?, ?, 1, ?)
            """, (
                context.user_data["gift_name"],
                price,
                context.user_data["gift_emoji"],
                datetime.now().isoformat(),
            ))
            conn.commit()
            conn.close()

            context.user_data.clear()
            await update.message.reply_text(
                f"✅ Gift qo‘shildi!\n⭐ Narx: {price:g}"
            )
            return

        if state == "mandatory_id":
            channel_id = text.strip()

            if not channel_id.startswith("-100"):
                await update.message.reply_text(
                    "❌ Kanal ID odatda -100 bilan boshlanadi."
                )
                return

            try:
                chat = await context.bot.get_chat(channel_id)
                if chat.type != "channel":
                    raise ValueError("not a channel")
            except Exception:
                await update.message.reply_text(
                    "❌ Kanal topilmadi. ID to‘g‘riligini va bot "
                    "kanalda admin ekanini tekshiring."
                )
                return

            context.user_data["mandatory_id"] = channel_id
            context.user_data["mandatory_username"] = chat.username or ""
            context.user_data["mandatory_title"] = chat.title or ""
            context.user_data["state"] = "mandatory_link"

            await update.message.reply_text(
                "🔗 Kanal linkini yuboring.\n\n"
                "Public: https://t.me/username\n"
                "Private: https://t.me/+xxxx"
            )
            return

        if state == "mandatory_link":
            link = text.strip()
            channel_id = context.user_data["mandatory_id"]
            username = context.user_data["mandatory_username"]
            title = context.user_data["mandatory_title"]

            conn = db()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO mandatory_channels(
                        channel_id, username, title,
                        invite_link, created_at
                    )
                    VALUES(?, ?, ?, ?, ?)
                """, (
                    channel_id,
                    username,
                    title,
                    link,
                    datetime.now().isoformat(),
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                conn.rollback()
                conn.close()
                context.user_data.clear()
                await update.message.reply_text(
                    "❌ Bu kanal allaqachon qo‘shilgan."
                )
                return

            conn.close()
            context.user_data.clear()

            await update.message.reply_text(
                f"✅ Majburiy kanal qo‘shildi!\n\n"
                f"📢 {title}\n"
                f"🆔 {channel_id}"
            )
            return

    # User advertising state.
    if state == "advertisement":
        await save_advertisement(update, context)
        return

    # Mandatory channel gate applies to normal menu actions.
    if not await check_mandatory(user.id, context):
        await send_mandatory(update, context)
        return

    # =====================================================
    # USER MENU
    # =====================================================

    if text == "⭐ Stars ishlash":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🎯 Vazifalarni boshlash", callback_data="task_start"
            )],
            [InlineKeyboardButton(
                "💰 Balans", callback_data="balance"
            )],
        ])
        await update.message.reply_text(
            "⭐ Stars ishlash",
            reply_markup=keyboard
        )
        return

    if text == "🎁 Gift olish":
        await gifts_menu(update, context)
        return

    if text == "👥 Referral":
        await referral(update, context)
        return

    if text == "💰 Balans":
        await show_balance(update, context)
        return

    if text == "📜 Qoidalar":
        await rules(update, context)
        return

    if text == "📢 Reklama":
        context.user_data["state"] = "advertisement"
        await update.message.reply_text(
            "📢 Reklama ma'lumotlarini yuboring."
        )
        return

    # =====================================================
    # ADMIN MENU
    # =====================================================

    if text == "⚙️ Admin panel":
        if is_admin(user.id):
            await update.message.reply_text(
                "⚙️ Admin panel",
                reply_markup=admin_menu()
            )
        return

    if not is_admin(user.id):
        await update.message.reply_text(
            "👇 Menyudan foydalaning.",
            reply_markup=main_menu(user.id)
        )
        return

    if text == "📊 Statistika":
        await admin_statistics(update, context)
        return

    if text == "👥 Foydalanuvchilar":
        await admin_users(update, context)
        return

    if text == "📝 Loglar":
        await admin_logs(update, context)
        return

    if text == "📢 Vazifa kanallari":
        await admin_tasks(update, context)
        return

    if text == "🎁 Giftlar":
        await admin_gifts(update, context)
        return

    if text == "🎁 Gift so‘rovlari":
        await admin_gift_requests(update, context)
        return

    if text == "🔐 Majburiy kanallar":
        await admin_mandatory(update, context)
        return

    if text == "👑 Adminlar":
        await admin_list(update, context)
        return

    if text == "📣 Reklama so‘rovlari":
        await admin_ad_requests(update, context)
        return

    if text == "⬅️ Orqaga":
        context.user_data.clear()
        await update.message.reply_text(
            "🏠 Asosiy menyu",
            reply_markup=main_menu(user.id)
        )
        return


# =========================================================
# CALLBACKS
# =========================================================

async def gift_status(update, context):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Admin emassiz.", show_alert=True)
        return

    try:
        action, request_id_text = query.data.split(":")
        request_id = int(request_id_text)
    except Exception:
        await query.answer("❌ So‘rov ID xato.", show_alert=True)
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
        await query.answer("❌ So‘rov topilmadi.", show_alert=True)
        return

    if request["status"] != "pending":
        conn.close()
        await query.answer(
            "⚠️ So‘rov allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    now = datetime.now().isoformat()

    if action == "gift_reject":
        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (float(request["price"]), request["user_id"]))
        status = "rejected"
    else:
        status = "approved"

    cur.execute("""
        UPDATE gift_requests
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (status, now, request_id))

    conn.commit()
    conn.close()

    await query.answer(f"✅ {status}")

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    try:
        await context.bot.send_message(
            request["user_id"],
            f"🎁 Gift so‘rovingiz #{request_id}\n\n"
            f"Status: {status}"
        )
    except Exception:
        pass


async def callback_handler(update, context):
    query = update.callback_query
    data = query.data or ""

    if data == "mandatory_check":
        if await check_mandatory(query.from_user.id, context):
            await query.answer("✅ Obuna tasdiqlandi!")
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(
                query.from_user.id,
                "🏠 Asosiy menyu",
                reply_markup=main_menu(query.from_user.id)
            )
        else:
            await query.answer(
                "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
                show_alert=True
            )
        return

    # Task and menu callbacks are already protected by the normal flow.
    if data == "stars_menu":
        await stars_menu(update, context)
        return

    if data == "task_start":
        await task_start(update, context)
        return

    if data.startswith("task_check:"):
        await check_task(update, context)
        return

    if data.startswith("task_skip:"):
        await skip_task(update, context)
        return

    if data == "balance":
        await show_balance(update, context)
        return

    if data == "main_menu":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            query.from_user.id,
            "🏠 Asosiy menyu",
            reply_markup=main_menu(query.from_user.id)
        )
        return

    if data.startswith("gift_buy:"):
        await buy_gift(update, context)
        return

    if data.startswith("gift:"):
        await gift_info(update, context)
        return

    if data == "gift_cancel":
        await query.answer("❌ Bekor qilindi.")
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data.startswith("gift_approve:") or data.startswith("gift_reject:"):
        await gift_status(update, context)
        return

    await query.answer()


# =========================================================
# ERROR
# =========================================================

async def error_handler(update, context):
    logger.exception("Unhandled error", exc_info=context.error)


# =========================================================
# MAIN
# =========================================================

def main():
    init_db()

    logger.info("Starting FrostStars...")

    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(CommandHandler("addtask", add_task))
    application.add_handler(CommandHandler("deltask", delete_task))
    application.add_handler(CommandHandler("addgift", add_gift))
    application.add_handler(CommandHandler("delgift", delete_gift))
    application.add_handler(CommandHandler("addmandatory", add_mandatory_command))
    application.add_handler(CommandHandler("delmandatory", delete_mandatory_command))

    application.add_handler(CallbackQueryHandler(callback_handler))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
    )

    application.add_error_handler(error_handler)

    logger.info("FROSTSTARS BOT IS RUNNING!")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
