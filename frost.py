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

SUBSCRIPTION_DAYS = 2
DEFAULT_REWARD = 0.10
REFERRAL_REWARD = 1.50


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

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # TASKS / CHANNELS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            reward REAL DEFAULT 0.1,
            created_at TEXT
        )
    """)

    # -----------------------------------------------------
    # COMPLETED TASKS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            reward REAL NOT NULL,
            completed_at TEXT NOT NULL,
            UNIQUE(user_id, task_id)
        )
    """)

    # -----------------------------------------------------
    # SKIPPED TASKS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS skipped_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            skipped_at TEXT NOT NULL,
            UNIQUE(user_id, task_id)
        )
    """)

    # -----------------------------------------------------
    # 2-DAY SUBSCRIPTIONS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            reward REAL NOT NULL,
            subscribed_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_checked_at TEXT,
            valid INTEGER DEFAULT 1,
            UNIQUE(user_id, task_id)
        )
    """)

    # -----------------------------------------------------
    # GIFTS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # GIFT REQUESTS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gift_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_id INTEGER,
            gift_name TEXT,
            price REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # -----------------------------------------------------
    # ADMINS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT
        )
    """)

    # -----------------------------------------------------
    # ACTIVITY
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT
        )
    """)

    # -----------------------------------------------------
    # MANDATORY CHANNELS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ADVERTISEMENTS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertiser_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    # -----------------------------------------------------
    # OWNER
    # -----------------------------------------------------

    cur.execute("""
        INSERT OR IGNORE INTO admins
        (user_id, added_at)
        VALUES (?, ?)
    """, (
        OWNER_ID,
        datetime.now().isoformat()
    ))

    # -----------------------------------------------------
    # DEFAULT TASKS
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
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
            DEFAULT_REWARD,
            datetime.now().isoformat()
        ))

    cur.execute("""
        SELECT id
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
            DEFAULT_REWARD,
            datetime.now().isoformat()
        ))

    # -----------------------------------------------------
    # DEFAULT GIFTS
    # -----------------------------------------------------

    cur.execute("SELECT COUNT(*) FROM gifts")
    gift_count = cur.fetchone()[0]

    if gift_count == 0:
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
        ]

        for emoji, name, price in default_gifts:
            cur.execute("""
                INSERT INTO gifts
                (emoji, name, price, active, created_at)
                VALUES (?, ?, ?, 1, ?)
            """, (
                emoji,
                name,
                price,
                datetime.now().isoformat()
            ))

    conn.commit()
    conn.close()


# =========================================================
# USER
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
# ADMIN
# =========================================================

def is_owner(user_id):
    return user_id == OWNER_ID


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
# MENUS
# =========================================================

def main_menu(user_id):
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


def admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["📊 Statistika"],
            ["👥 Foydalanuvchilar", "📝 Loglar"],
            ["📢 Vazifa kanallari"],
            ["🎁 Giftlar"],
            ["🎁 Gift so‘rovlari"],
            ["🔐 Majburiy kanallar"],
            ["👑 Adminlar"],
            ["📣 Reklama so‘rovlari"],
            ["⬅️ Orqaga"],
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

        except Exception:
            continue

    return True


async def send_mandatory(update, context):
    channels = get_mandatory_channels()

    keyboard = []

    for channel in channels:
        link = channel["invite_link"]

        if not link and channel["username"]:
            username = channel["username"].replace("@", "")
            link = f"https://t.me/{username}"

        if link:
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 {channel['title']}",
                    url=link
                )
            ])

    keyboard.append([
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
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
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

            if referrer_id != user.id:
                conn = db()
                cur = conn.cursor()

                cur.execute("""
                    SELECT referred_by
                    FROM users
                    WHERE user_id = ?
                """, (user.id,))

                current = cur.fetchone()

                cur.execute("""
                    SELECT user_id
                    FROM users
                    WHERE user_id = ?
                """, (referrer_id,))

                referrer = cur.fetchone()

                if (
                    current
                    and current["referred_by"] is None
                    and referrer
                ):
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

        except Exception as e:
            logger.warning("Referral error: %s", e)

    if not await check_mandatory(
        user.id,
        context
    ):
        await send_mandatory(
            update,
            context
        )
        return

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "⭐ FrostStars botiga xush kelibsiz!",
        reply_markup=main_menu(user.id)
    )


# =========================================================
# TASK FUNCTIONS
# =========================================================

def get_tasks():
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
        FROM completed_tasks
        WHERE user_id = ?
        AND task_id = ?
    """, (user_id, task_id))

    completed = cur.fetchone()

    cur.execute("""
        SELECT 1
        FROM skipped_tasks
        WHERE user_id = ?
        AND task_id = ?
    """, (user_id, task_id))

    skipped = cur.fetchone()

    conn.close()

    return completed is not None or skipped is not None


def get_next_task(user_id):
    tasks = get_tasks()

    for task in tasks:
        if not task_was_seen(
            user_id,
            task["id"]
        ):
            return task

    return None


def task_keyboard(task):
    username = task["username"].replace("@", "")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"📢 {task['title']}",
                url=f"https://t.me/{username}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Obuna bo‘ldim",
                callback_data=f"task_check:{task['id']}"
            )
        ],
        [
            InlineKeyboardButton(
                "⏭️ Vazifani o'tkazib yuborish",
                callback_data=f"task_skip:{task['id']}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Orqaga",
                callback_data="stars_menu"
            )
        ]
    ])


async def show_next_task(chat_id, user_id, context):
    task = get_next_task(user_id)

    if not task:
        await context.bot.send_message(
            chat_id,
            "🎉 Barcha vazifalarni ko‘rib chiqdingiz!\n\n"
            "Hozircha yangi vazifa yo‘q."
        )
        return

    await context.bot.send_message(
        chat_id,
        "🎯 Yangi vazifa\n\n"
        f"📢 {task['title']}\n"
        f"⭐ Mukofot: {task['reward']} Stars\n\n"
        "1️⃣ Kanalga obuna bo‘ling\n"
        "2️⃣ «Obuna bo‘ldim» tugmasini bosing\n"
        "3️⃣ Tekshiruvdan o'ting\n\n"
        f"⚠️ Mukofotdan keyin kanalda "
        f"{SUBSCRIPTION_DAYS} kun qolishingiz kerak.",
        reply_markup=task_keyboard(task)
    )


async def stars_menu(update, context):
    query = update.callback_query

    if query:
        await query.answer()
        user_id = query.from_user.id
        chat_id = query.message.chat_id

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎯 Vazifalarni boshlash",
                    callback_data="task_start"
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
        ])

        await query.edit_message_text(
            "⭐ Stars ishlash\n\n"
            "Vazifalarni bajaring va Stars oling.",
            reply_markup=keyboard
        )

        return


# =========================================================
# TASK START
# =========================================================

async def task_start(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    task = get_next_task(user_id)

    if not task:
        await query.edit_message_text(
            "🎉 Siz barcha mavjud vazifalarni ko‘rib chiqdingiz."
        )
        return

    await query.edit_message_text(
        "🎯 Vazifa\n\n"
        f"📢 {task['title']}\n"
        f"⭐ Mukofot: {task['reward']} Stars\n\n"
        "Kanalga obuna bo‘ling va tekshirtiring.",
        reply_markup=task_keyboard(task)
    )


# =========================================================
# TASK CHECK
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
            "⚠️ Bu vazifa oldin bajarilgan.",
            show_alert=True
        )
        return

    await query.answer("🔎 Tekshirilmoqda...")

    try:
        member = await context.bot.get_chat_member(
            task["username"],
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
        logger.error(
            "Task subscription check error: %s",
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
            float(task["reward"]),
            now.isoformat()
        ))

        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (
            float(task["reward"]),
            user_id
        ))

        cur.execute("""
            INSERT INTO task_subscriptions
            (
                user_id,
                task_id,
                reward,
                subscribed_at,
                expires_at,
                last_checked_at,
                valid
            )
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            user_id,
            task_id,
            float(task["reward"]),
            now.isoformat(),
            expires.isoformat(),
            now.isoformat()
        ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        logger.exception(
            "REWARD ERROR: %s",
            e
        )

        conn.close()

        await query.answer(
            "❌ Mukofot berishda xatolik yuz berdi.",
            show_alert=True
        )
        return

    conn.close()

    log_activity(
        user_id,
        "task_completed",
        f"{task['title']} +{task['reward']}"
    )

    # Eski xabarni o'chirish
    try:
        await query.message.delete()
    except Exception:
        pass

    # Keyingi vazifa
    await context.bot.send_message(
        chat_id=user_id,
        text=(
            "🎉 Vazifa bajarildi!\n\n"
            f"📢 {task['title']}\n"
            f"⭐ +{task['reward']} Stars\n\n"
            f"💰 Mukofot balansingizga qo‘shildi.\n\n"
            f"⚠️ Kanalda {SUBSCRIPTION_DAYS} kun "
            "qoling.\n"
            "Agar muddat tugamasdan chiqib ketsangiz, "
            "shu vazifa uchun berilgan Stars qaytarib olinadi."
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "➡️ Keyingi vazifa",
                    callback_data="task_start"
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 Balans",
                    callback_data="balance"
                )
            ]
        ])
    )


# =========================================================
# SKIP TASK
# =========================================================

async def skip_task(update, context):
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

    if not task:
        conn.close()

        await query.answer(
            "❌ Vazifa topilmadi.",
            show_alert=True
        )
        return

    try:
        cur.execute("""
            INSERT INTO skipped_tasks
            (
                user_id,
                task_id,
                skipped_at
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            task_id,
            datetime.now().isoformat()
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()

    conn.close()

    log_activity(
        user_id,
        "task_skipped",
        task["title"]
    )

    await query.answer(
        "⏭️ Vazifa o'tkazib yuborildi."
    )

    try:
        await query.message.delete()
    except Exception:
        pass

    await show_next_task(
        user_id,
        user_id,
        context
    )


# =========================================================
# 2 DAY SUBSCRIPTION CHECK
# =========================================================

async def check_two_day_subscriptions(context):
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
        WHERE ts.valid = 1
    """)

    subscriptions = cur.fetchall()
    conn.close()

    for sub in subscriptions:

        user_id = sub["user_id"]
        reward = float(sub["reward"])

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

            log_activity(
                user_id,
                "subscription_completed",
                f"{sub['title']} 2 kun tugadi"
            )

            continue

        # -------------------------------------------------
        # KANALNI TEKSHIRISH
        # -------------------------------------------------

        try:
            member = await context.bot.get_chat_member(
                sub["username"],
                user_id
            )

            still_subscribed = member.status in (
                "member",
                "administrator",
                "creator"
            )

        except Exception as e:
            logger.warning(
                "2-day check error %s: %s",
                user_id,
                e
            )

            continue

        # -------------------------------------------------
        # CHIQIB KETGAN
        # -------------------------------------------------

        if not still_subscribed:

            conn = db()
            cur = conn.cursor()

            cur.execute("""
                UPDATE task_subscriptions
                SET valid = 0,
                    last_checked_at = ?
                WHERE id = ?
                AND valid = 1
            """, (
                datetime.now().isoformat(),
                sub["id"]
            ))

            changed = cur.rowcount

            if changed:
                cur.execute("""
                    UPDATE users
                    SET balance = balance - ?
                    WHERE user_id = ?
                """, (
                    reward,
                    user_id
                ))

                conn.commit()
            else:
                conn.rollback()

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
                        "⚠️ Kanal obunasi bekor qilindi.\n\n"
                        f"📢 {sub['title']}\n"
                        f"⭐ -{reward} Stars\n\n"
                        f"Sabab: {SUBSCRIPTION_DAYS} kunlik "
                        "obuna sharti bajarilmadi."
                    )
                except Exception:
                    pass


# =========================================================
# BALANCE
# =========================================================

async def show_balance(update, context):
    query = update.callback_query

    if query:
        await query.answer()
        user_id = query.from_user.id

        row = get_user(user_id)

        await query.edit_message_text(
            "💰 Balans\n\n"
            f"⭐ {row['balance']:.2f} Stars",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Orqaga",
                        callback_data="main_menu"
                    )
                ]
            ])
        )
        return

    user = update.effective_user
    row = get_user(user.id)

    await update.message.reply_text(
        "💰 Balansingiz:\n\n"
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
        f"⭐ Bir referral: {REFERRAL_REWARD}\n"
        f"👤 Referral soni: {row['referral_count']}\n\n"
        f"🔗 Sizning linkingiz:\n{link}"
    )


# =========================================================
# RULES
# =========================================================

async def rules(update, context):
    await update.message.reply_text(
        "📜 FrostStars qoidalari\n\n"
        "1. Har bir vazifa faqat bir marta mukofot beradi.\n"
        "2. Vazifani o'tkazib yuborish mumkin.\n"
        "3. Mukofot olish uchun kanalga obuna bo‘lish kerak.\n"
        f"4. Mukofotdan keyin {SUBSCRIPTION_DAYS} kun "
        "kanalda qolish kerak.\n"
        "5. Muddat tugamasdan kanalni tark etsangiz, "
        "mukofot qaytarib olinadi.\n"
        "6. Soxta akkauntlardan foydalanish taqiqlanadi."
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

    keyboard = []

    for gift in gifts:
        keyboard.append([
            InlineKeyboardButton(
                f"{gift['emoji']} {gift['name']} — "
                f"⭐ {gift['price']}",
                callback_data=f"gift:{gift['id']}"
            )
        ])

    await update.message.reply_text(
        "🎁 Gift olish\n\n"
        "Giftni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def gift_info(update, context):
    query = update.callback_query

    await query.answer()

    try:
        gift_id = int(
            query.data.split(":")[1]
        )
    except Exception:
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
        await query.message.reply_text(
            "❌ Gift topilmadi."
        )
        return

    await query.message.reply_text(
        f"{gift['emoji']} {gift['name']}\n\n"
        f"⭐ Narxi: {gift['price']}\n\n"
        "Sotib olishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"gift_buy:{gift_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Bekor qilish",
                    callback_data="gift_cancel"
                )
            ]
        ])
    )


async def buy_gift(update, context):
    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    try:
        gift_id = int(
            query.data.split(":")[1]
        )
    except Exception:
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

    if not gift:
        conn.close()

        await query.message.reply_text(
            "❌ Gift topilmadi."
        )
        return

    cur.execute("""
        SELECT balance
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    user = cur.fetchone()

    if not user or user["balance"] < gift["price"]:
        conn.close()

        await query.message.reply_text(
            "❌ Balansingiz yetarli emas.\n\n"
            f"Kerak: ⭐ {gift['price']}\n"
            f"Sizda: ⭐ {user['balance'] if user else 0:.2f}"
        )
        return

    cur.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE user_id = ?
    """, (
        gift["price"],
        user_id
    ))

    now = datetime.now().isoformat()

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

    await query.message.reply_text(
        "✅ Gift so‘rovi yuborildi!\n\n"
        f"{gift['emoji']} {gift['name']}\n"
        f"⭐ {gift['price']}\n"
        f"🆔 #{request_id}\n\n"
        "Admin so‘rovni ko‘rib chiqadi."
    )


# =========================================================
# ADMIN: TASKS
# =========================================================

async def admin_tasks(update, context):
    tasks = get_tasks()

    text = "📢 Vazifa kanallari\n\n"

    for task in tasks:
        text += (
            f"🆔 {task['id']}\n"
            f"📢 {task['title']}\n"
            f"🔗 {task['username']}\n"
            f"⭐ {task['reward']}\n\n"
        )

    text += (
        "/addtask — kanal qo‘shish\n"
        "/deltask ID — kanal o‘chirish"
    )

    await update.message.reply_text(text)


async def add_task(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "task_username"

    await update.message.reply_text(
        "📢 Kanal username yuboring.\n\n"
        "Masalan:\n"
        "@mychannel"
    )


async def delete_task(update, context):
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
# ADMIN: GIFTS
# =========================================================

async def admin_gifts(update, context):
    gifts = get_gifts()

    text = "🎁 Giftlar\n\n"

    for gift in gifts:
        text += (
            f"🆔 {gift['id']}\n"
            f"{gift['emoji']} {gift['name']}\n"
            f"⭐ {gift['price']}\n\n"
        )

    text += (
        "/addgift — yangi gift\n"
        "/delgift ID — giftni o‘chirish"
    )

    await update.message.reply_text(text)


async def add_gift(update, context):
    if not is_admin(update.effective_user.id):
        return

    context.user_data["state"] = "gift_name"

    await update.message.reply_text(
        "🎁 Gift nomini yuboring.\n\n"
        "Masalan:\n"
        "Teddy Bear"
    )


async def delete_gift(update, context):
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

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Gift o‘chirildi."
    )


# =========================================================
# ADMIN: GIFT REQUESTS
# =========================================================

async def admin_gift_requests(update, context):
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
            "🎁 So‘rovlar yo‘q."
        )
        return

    for row in rows:

        keyboard = []

        if row["status"] == "pending":
            keyboard.append([
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"gift_approve:{row['id']}"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"gift_reject:{row['id']}"
                )
            ])

        await update.message.reply_text(
            f"🎁 Gift request #{row['id']}\n\n"
            f"👤 User: {row['user_id']}\n"
            f"🎁 {row['gift_name']}\n"
            f"⭐ {row['price']}\n"
            f"📌 {row['status']}",
            reply_markup=(
                InlineKeyboardMarkup(keyboard)
                if keyboard else None
            )
        )


async def gift_status(update, context):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer(
            "❌ Admin emassiz.",
            show_alert=True
        )
        return

    try:
        action, request_id = query.data.split(":")
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

        await query.answer(
            "❌ So‘rov topilmadi.",
            show_alert=True
        )
        return

    if request["status"] != "pending":
        conn.close()

        await query.answer(
            "⚠️ Bu so‘rov allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    if action == "gift_reject":

        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
        """, (
            request["price"],
            request["user_id"]
        ))

        status = "rejected"

    else:
        status = "approved"

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

    await query.answer(
        f"✅ {status}"
    )

    try:
        await context.bot.send_message(
            request["user_id"],
            f"🎁 Gift so‘rovingiz #{request_id}\n\n"
            f"Status: {status}"
        )
    except Exception:
        pass


# =========================================================
# ADMIN STATISTICS
# =========================================================

async def admin_statistics(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(balance), 0)
        FROM users
    """)
    balance = cur.fetchone()[0]

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

    conn.close()

    await update.message.reply_text(
        "📊 Admin statistikasi\n\n"
        f"👥 Users: {users}\n"
        f"⭐ Umumiy balans: {balance:.2f}\n"
        f"🎯 Bajarilgan vazifalar: {completed}\n"
        f"🎁 Gift so‘rovlari: {gifts}"
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(update, context):
    user = update.effective_user
    text = update.message.text

    add_user(user)

    # Majburiy kanallar
    if not await check_mandatory(
        user.id,
        context
    ):
        await send_mandatory(
            update,
            context
        )
        return

    state = context.user_data.get("state")

    # -----------------------------------------------------
    # ADD TASK
    # -----------------------------------------------------

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
                "⭐ Reward yuboring.\n\n"
                "Masalan: 0.1"
            )
            return

        if state == "task_reward":

            try:
                reward = float(
                    text.replace(",", ".")
                )

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
                "✅ Vazifa qo‘shildi!"
            )
            return

        # -------------------------------------------------
        # ADD GIFT
        # -------------------------------------------------

        if state == "gift_name":

            context.user_data["gift_name"] = text.strip()
            context.user_data["state"] = "gift_emoji"

            await update.message.reply_text(
                "😀 Gift emoji yuboring.\n\n"
                "Masalan: 🧸"
            )
            return

        if state == "gift_emoji":

            context.user_data["gift_emoji"] = text.strip()
            context.user_data["state"] = "gift_price"

            await update.message.reply_text(
                "⭐ Gift narxini yuboring.\n\n"
                "Masalan: 25"
            )
            return

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

            name = context.user_data["gift_name"]
            emoji = context.user_data["gift_emoji"]

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
                "✅ Gift qo‘shildi!"
            )
            return

    # -----------------------------------------------------
    # USER MENU
    # -----------------------------------------------------

    if text == "⭐ Stars ishlash":

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎯 Vazifalarni boshlash",
                    callback_data="task_start"
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 Balans",
                    callback_data="balance"
                )
            ]
        ])

        await update.message.reply_text(
            "⭐ Stars ishlash",
            reply_markup=keyboard
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
        await show_balance(
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

        context.user_data["state"] = "advertisement"

        await update.message.reply_text(
            "📢 Reklama ma'lumotlarini yuboring."
        )
        return

    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    if text == "⚙️ Admin panel":

        if is_admin(user.id):
            await update.message.reply_text(
                "⚙️ Admin panel",
                reply_markup=admin_menu()
            )

        return

    if not is_admin(user.id):
        await update.message.reply_text(
            "👇 Menyudan foydalaning."
        )
        return

    if text == "📊 Statistika":
        await admin_statistics(
            update,
            context
        )
        return

    if text == "📢 Vazifa kanallari":
        await admin_tasks(
            update,
            context
        )
        return

    if text == "🎁 Giftlar":
        await admin_gifts(
            update,
            context
        )
        return

    if text == "🎁 Gift so‘rovlari":
        await admin_gift_requests(
            update,
            context
        )
        return

    if text == "👥 Foydalanuvchilar":

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM users
            ORDER BY created_at DESC
            LIMIT 50
        """)

        users = cur.fetchall()
        conn.close()

        result = "👥 Foydalanuvchilar\n\n"

        for u in users:
            result += (
                f"🆔 {u['user_id']}\n"
                f"👤 {u['first_name']}\n"
                f"⭐ {u['balance']:.2f}\n\n"
            )

        await update.message.reply_text(result)
        return

    if text == "📝 Loglar":

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM activity_logs
            ORDER BY id DESC
            LIMIT 30
        """)

        logs = cur.fetchall()
        conn.close()

        result = "📝 Loglar\n\n"

        for log in logs:
            result += (
                f"#{log['id']} "
                f"{log['user_id']} "
                f"{log['action']}\n"
                f"{log['details']}\n\n"
            )

        await update.message.reply_text(result)
        return

    if text == "👑 Adminlar":

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM admins
            ORDER BY added_at ASC
        """)

        admins = cur.fetchall()
        conn.close()

        result = "👑 Adminlar\n\n"

        for admin in admins:
            role = (
                "OWNER"
                if admin["user_id"] == OWNER_ID
                else "ADMIN"
            )

            result += (
                f"{role}: {admin['user_id']}\n"
            )

        result += (
            "\n/addadmin USER_ID\n"
            "/removeadmin USER_ID"
        )

        await update.message.reply_text(result)
        return

    if text == "⬅️ Orqaga":

        context.user_data.clear()

        await update.message.reply_text(
            "🏠 Asosiy menyu",
            reply_markup=main_menu(user.id)
        )
        return


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def callback_handler(update, context):
    query = update.callback_query
    data = query.data

    # -----------------------------------------------------
    # MANDATORY
    # -----------------------------------------------------

    if data == "mandatory_check":

        await query.answer()

        if await check_mandatory(
            query.from_user.id,
            context
        ):
            await query.message.reply_text(
                "✅ Obuna tasdiqlandi!",
                reply_markup=main_menu(
                    query.from_user.id
                )
            )
        else:
            await query.answer(
                "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
                show_alert=True
            )

        return

    # -----------------------------------------------------
    # STARS
    # -----------------------------------------------------

    if data == "stars_menu":
        await stars_menu(
            update,
            context
        )
        return

    if data == "task_start":
        await task_start(
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

    if data.startswith("task_skip:"):
        await skip_task(
            update,
            context
        )
        return

    # -----------------------------------------------------
    # BALANCE
    # -----------------------------------------------------

    if data == "balance":
        await show_balance(
            update,
            context
        )
        return

    # -----------------------------------------------------
    # MAIN
    # -----------------------------------------------------

    if data == "main_menu":

        await query.answer()

        await query.message.edit_text(
            "🏠 Asosiy menyu",
        )

        return

    # -----------------------------------------------------
    # GIFTS
    # -----------------------------------------------------

    if data.startswith("gift:"):
        await gift_info(
            update,
            context
        )
        return

    if data.startswith("gift_buy:"):
        await buy_gift(
            update,
            context
        )
        return

    if data == "gift_cancel":

        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        return

    # -----------------------------------------------------
    # GIFT ADMIN
    # -----------------------------------------------------

    if data.startswith("gift_approve:") or \
       data.startswith("gift_reject:"):

        await gift_status(
            update,
            context
        )
        return

    await query.answer()


# =========================================================
# COMMANDS
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
            "❌ ID noto‘g‘ri."
        )
        return

    if not get_user(user_id):
        await update.message.reply_text(
            "❌ User avval botdan foydalanishi kerak."
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
            "❌ ID noto‘g‘ri."
        )
        return

    if remove_admin(user_id):
        await update.message.reply_text(
            "✅ Admin olib tashlandi."
        )


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
# ADVERTISEMENT
# =========================================================

async def save_advertisement(update, context):
    user = update.effective_user

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
        update.message.text,
        datetime.now().isoformat()
    ))

    conn.commit()
    request_id = cur.lastrowid
    conn.close()

    context.user_data.clear()

    await update.message.reply_text(
        f"✅ Reklama so‘rovi yuborildi.\n"
        f"🆔 #{request_id}"
    )


# =========================================================
# JOB
# =========================================================

async def subscription_checker(context):
    try:
        await check_two_day_subscriptions(context)
    except Exception as e:
        logger.exception(
            "Subscription checker error: %s",
            e
        )


# =========================================================
# ERROR
# =========================================================

async def error_handler(update, context):
    logger.exception(
        "Unhandled exception:",
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

    # Commands
    application.add_handler(
        CommandHandler("start", start)
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
            add_task
        )
    )

    application.add_handler(
        CommandHandler(
            "deltask",
            delete_task
        )
    )

    application.add_handler(
        CommandHandler(
            "addgift",
            add_gift
        )
    )

    application.add_handler(
        CommandHandler(
            "delgift",
            delete_gift
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

    # Callback
    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    application.add_error_handler(
        error_handler
    )

    # Har 30 daqiqada 2 kunlik obunalarni tekshiradi
    application.job_queue.run_repeating(
        subscription_checker,
        interval=1800,
        first=60
    )

    logger.info(
        "FROSTSTARS BOT IS RUNNING!"
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
