
import os
import sqlite3
import logging
from datetime import datetime

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
# SOZLAMALAR
# =========================================================

BOT_TOKEN = os.getenv("8725108807:AAGZWDsUXrFhUlH9i6OTtyHQEcmMU4E-Dg4")

ADMIN_ID = 6383248812

# Kanal topshirig'i mukofoti
DEFAULT_TASK_REWARD = 0.5

# Referal mukofoti
REFERRAL_REWARD = 2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "starbot.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            referred_by INTEGER,
            referrals INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    # COMPLETED TASKS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id TEXT,
            completed_at TEXT,
            UNIQUE(user_id, task_id)
        )
    """)

    # GIFT REQUESTS
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

    # CHANNELS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            title TEXT,
            reward INTEGER DEFAULT 15,
            created_at TEXT
        )
    """)

    # Eski bazalarda yetishmayotgan ustunlarni qo'shish
    tables_columns = {
        "users": {
            "username": "TEXT",
            "first_name": "TEXT",
            "balance": "INTEGER DEFAULT 0",
            "referred_by": "INTEGER",
            "referrals": "INTEGER DEFAULT 0",
            "created_at": "TEXT",
        },
        "completed_tasks": {
            "id": "INTEGER",
            "user_id": "INTEGER",
            "task_id": "TEXT",
            "completed_at": "TEXT",
        },
        "gift_requests": {
            "id": "INTEGER",
            "user_id": "INTEGER",
            "price": "INTEGER",
            "status": "TEXT DEFAULT 'pending'",
            "created_at": "TEXT",
            "gift_id": "TEXT",
            "gift_name": "TEXT",
        },
        "channels": {
            "id": "INTEGER",
            "channel_id": "TEXT",
            "title": "TEXT",
            "reward": "INTEGER DEFAULT 15",
            "created_at": "TEXT",
        },
    }

    for table, columns in tables_columns.items():
        cur.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cur.fetchall()}

        for column, definition in columns.items():
            if column not in existing:
                try:
                    cur.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )
                except Exception:
                    pass

    # Agar yangi baza bo'lsa, boshlang'ich kanallarni qo'shish
    cur.execute("SELECT COUNT(*) AS count FROM channels")
    channel_count = cur.fetchone()["count"]

    if channel_count == 0:
        now = datetime.now().isoformat()

        default_channels = [
            (
                "@Cossmoss_00",
                "📢 Cossmoss kanaliga obuna",
                DEFAULT_TASK_REWARD,
            ),
            (
                "@PromptLab_UZ",
                "📢 PromptLab kanaliga obuna",
                DEFAULT_TASK_REWARD,
            ),
        ]

        for channel_id, title, reward in default_channels:
            try:
                cur.execute(
                    """
                    INSERT INTO channels
                    (channel_id, title, reward, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (channel_id, title, reward, now),
                )
            except Exception:
                pass

    conn.commit()
    conn.close()

    print("✅ Database tekshirildi va yangilandi.")


# =========================================================
# USER
# =========================================================

def add_user(user):
    conn = get_db()
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
            (user_id, username, first_name, balance, referrals, created_at)
            VALUES (?, ?, ?, 0, 0, ?)
            """,
            (
                user.id,
                user.username or "",
                user.first_name or "",
                datetime.now().isoformat(),
            ),
        )
    else:
        cur.execute(
            """
            UPDATE users
            SET username = ?, first_name = ?
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


def get_balance(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,),
    )

    row = cur.fetchone()
    conn.close()

    return row["balance"] if row else 0


# =========================================================
# MAIN MENU
# =========================================================

def main_menu(user_id):

    buttons = [
        ["⭐ Stars ishlash"],
        ["👥 Referal", "📊 Statistika"],
        ["💳 Gift olish", "ℹ️ Qoidalar"],
    ]

    if user_id == ADMIN_ID:
        buttons.append(["🎁 So‘rovlar", "⭐ Bot Stars"])
        buttons.append(["📢 Kanallar"])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
    )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(user)

    # REFERAL
    if context.args:
        try:
            ref_id = int(context.args[0])

            if ref_id != user.id:

                conn = get_db()
                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT referred_by
                    FROM users
                    WHERE user_id = ?
                    """,
                    (user.id,),
                )

                row = cur.fetchone()

                if row and row["referred_by"] is None:

                    cur.execute(
                        """
                        UPDATE users
                        SET referred_by = ?
                        WHERE user_id = ?
                        """,
                        (ref_id, user.id),
                    )

                    cur.execute(
                        """
                        UPDATE users
                        SET balance = balance + ?,
                            referrals = referrals + 1
                        WHERE user_id = ?
                        """,
                        (REFERRAL_REWARD, ref_id),
                    )

                    conn.commit()

                    try:
                        await context.bot.send_message(
                            ref_id,
                            f"🎉 Sizga yangi referal qo‘shildi!\n"
                            f"⭐ +{REFERRAL_REWARD} Stars",
                        )
                    except Exception:
                        pass

                conn.close()

        except Exception:
            pass

    balance = get_balance(user.id)

    await update.message.reply_text(
        f"⭐ FrostStars botiga xush kelibsiz!\n\n"
        f"💰 Balansingiz: {balance} ⭐\n\n"
        f"Stars yig‘ing va Gift olish uchun so‘rov yuboring.",
        reply_markup=main_menu(user.id),
    )


# =========================================================
# STARS ISHLASH
# =========================================================

async def stars_work(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, channel_id, title, reward
        FROM channels
        ORDER BY id ASC
        """
    )

    channels = cur.fetchall()
    conn.close()

    if not channels:
        await update.message.reply_text(
            "📭 Hozircha topshiriqlar mavjud emas."
        )
        return

    keyboard = []

    for channel in channels:

        task_id = f"channel_{channel['id']}"

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id
            FROM completed_tasks
            WHERE user_id = ? AND task_id = ?
            """,
            (user_id, task_id),
        )

        completed = cur.fetchone()
        conn.close()

        if completed:
            button_text = (
                f"✅ {channel['title']} "
                f"(+{channel['reward']} ⭐)"
            )
        else:
            button_text = (
                f"{channel['title']} "
                f"(+{channel['reward']} ⭐)"
            )

        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"task:{channel['id']}",
            )
        ])

    await update.message.reply_text(
        "⭐ Stars ishlash\n\n"
        "Kanalga obuna bo‘ling va tekshirish tugmasini bosing.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# TASK CALLBACK
# =========================================================

async def task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    try:
        channel_db_id = int(query.data.split(":")[1])
    except Exception:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, channel_id, title, reward
        FROM channels
        WHERE id = ?
        """,
        (channel_db_id,),
    )

    channel = cur.fetchone()

    if not channel:
        conn.close()

        await query.edit_message_text(
            "❌ Bu kanal topshirig‘i topilmadi."
        )
        return

    task_id = f"channel_{channel['id']}"

    cur.execute(
        """
        SELECT id
        FROM completed_tasks
        WHERE user_id = ? AND task_id = ?
        """,
        (user_id, task_id),
    )

    completed = cur.fetchone()

    if completed:
        conn.close()

        await query.edit_message_text(
            "✅ Bu topshiriqni avval bajargansiz."
        )
        return

    conn.close()

    # Kanalga o'tish
    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Kanalga kirish",
                url=f"https://t.me/{channel['channel_id'].replace('@', '')}",
            )
        ],
        [
            InlineKeyboardButton(
                "🔎 Tekshirish",
                callback_data=f"checktask:{channel['id']}",
            )
        ],
    ]

    await query.edit_message_text(
        f"{channel['title']}\n\n"
        f"⭐ Mukofot: +{channel['reward']} Stars\n\n"
        f"1️⃣ Kanalga obuna bo‘ling\n"
        f"2️⃣ Keyin «🔎 Tekshirish» tugmasini bosing.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# TASK CHECK
# =========================================================

async def check_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    try:
        channel_db_id = int(query.data.split(":")[1])
    except Exception:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, channel_id, title, reward
        FROM channels
        WHERE id = ?
        """,
        (channel_db_id,),
    )

    channel = cur.fetchone()

    if not channel:
        conn.close()

        await query.edit_message_text(
            "❌ Kanal topilmadi."
        )
        return

    task_id = f"channel_{channel['id']}"

    cur.execute(
        """
        SELECT id
        FROM completed_tasks
        WHERE user_id = ? AND task_id = ?
        """,
        (user_id, task_id),
    )

    if cur.fetchone():
        conn.close()

        await query.edit_message_text(
            "✅ Bu topshiriq allaqachon bajarilgan."
        )
        return

    try:
        member = await context.bot.get_chat_member(
            chat_id=channel["channel_id"],
            user_id=user_id,
        )

        status = member.status

        is_member = status in [
            "member",
            "administrator",
            "creator",
        ]

    except Exception as e:

        conn.close()

        await query.edit_message_text(
            "⚠️ Kanalni tekshirib bo‘lmadi.\n\n"
            "Bot kanalga admin qilib qo‘yilganini tekshiring."
        )

        print("Channel check error:", e)
        return

    if not is_member:

        conn.close()

        keyboard = [
            [
                InlineKeyboardButton(
                    "📢 Kanalga kirish",
                    url=f"https://t.me/{channel['channel_id'].replace('@', '')}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔎 Qayta tekshirish",
                    callback_data=f"checktask:{channel['id']}",
                )
            ],
        ]

        await query.edit_message_text(
            "❌ Siz hali kanalga obuna bo‘lmagansiz.\n\n"
            "Avval kanalga kiring, keyin qayta tekshiring.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    # Mukofot berish
    try:

        cur.execute(
            """
            INSERT INTO completed_tasks
            (user_id, task_id, completed_at)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                task_id,
                datetime.now().isoformat(),
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

    except sqlite3.IntegrityError:

        conn.rollback()
        conn.close()

        await query.edit_message_text(
            "✅ Bu topshiriqni avval bajargansiz."
        )
        return

    conn.close()

    new_balance = get_balance(user_id)

    await query.edit_message_text(
        f"🎉 Topshiriq bajarildi!\n\n"
        f"⭐ +{channel['reward']} Stars\n"
        f"💰 Balansingiz: {new_balance} ⭐"
    )


# =========================================================
# REFERAL
# =========================================================

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    bot = await context.bot.get_me()

    link = f"https://t.me/{bot.username}?start={user.id}"

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT referrals, balance
        FROM users
        WHERE user_id = ?
        """,
        (user.id,),
    )

    row = cur.fetchone()
    conn.close()

    referrals = row["referrals"] if row else 0
    balance = row["balance"] if row else 0

    await update.message.reply_text(
        f"👥 Referal tizimi\n\n"
        f"🔗 Sizning referal linkingiz:\n"
        f"{link}\n\n"
        f"👥 Referallar: {referrals}\n"
        f"⭐ Referaldan olgan Stars: {referrals * REFERRAL_REWARD}\n"
        f"💰 Balans: {balance} ⭐\n\n"
        f"Har bir yangi referal uchun "
        f"+{REFERRAL_REWARD} ⭐ beriladi."
    )


# =========================================================
# STATISTIKA
# =========================================================

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT balance, referrals
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    )

    user = cur.fetchone()

    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM completed_tasks
        WHERE user_id = ?
        """,
        (user_id,),
    )

    tasks = cur.fetchone()["count"]

    conn.close()

    balance = user["balance"] if user else 0
    referrals = user["referrals"] if user else 0

    await update.message.reply_text(
        f"📊 Sizning statistikangiz\n\n"
        f"⭐ Balans: {balance}\n"
        f"📋 Bajarilgan topshiriqlar: {tasks}\n"
        f"👥 Referallar: {referrals}"
    )


# =========================================================
# QOIDALAR
# =========================================================

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "ℹ️ FrostStars qoidalari\n\n"
        "1. Kanal topshiriqlarini bajaring.\n"
        "2. Har bir topshiriq uchun Stars olasiz.\n"
        "3. Referal orqali qo‘shimcha Stars olasiz.\n"
        "4. Yig‘ilgan Stars bilan Gift olish uchun so‘rov yuborishingiz mumkin.\n"
        "5. Gift admin tomonidan qo‘lda yuboriladi.\n"
        "6. So‘rov tasdiqlangandan keyin admin Giftni yuboradi."
    )


# =========================================================
# GIFT LIST
# =========================================================

async def get_real_gifts(bot):

    try:
        gifts = await bot.get_available_gifts()

        result = []

        for gift in gifts.gifts:

            try:
                price = gift.star_count
            except Exception:
                continue

            gift_id = str(gift.id)

            emoji = "🎁"

            try:
                if gift.sticker and gift.sticker.emoji:
                    emoji = gift.sticker.emoji
            except Exception:
                pass

            result.append({
                "id": gift_id,
                "price": price,
                "emoji": emoji,
            })

        result.sort(key=lambda x: x["price"])

        return result

    except Exception as e:

        print("Gift list error:", e)
        return []


# =========================================================
# GIFT OLISH
# =========================================================

async def gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    gifts = await get_real_gifts(context.bot)

    if not gifts:

        await update.message.reply_text(
            "❌ Hozircha Giftlar ro‘yxatini olish imkoni bo‘lmadi."
        )
        return

    balance = get_balance(update.effective_user.id)

    keyboard = []

    for gift in gifts:

        text = (
            f"{gift['emoji']} Gift — "
            f"{gift['price']} ⭐"
        )

        keyboard.append([
            InlineKeyboardButton(
                text,
                callback_data=f"realgift:{gift['id']}",
            )
        ])

    await update.message.reply_text(
        f"💳 Gift olish\n\n"
        f"💰 Sizning balansingiz: {balance} ⭐\n\n"
        f"Kerakli Giftni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# GIFT TANLASH
# =========================================================

async def real_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    gift_id = query.data.split(":", 1)[1]

    gifts = await get_real_gifts(context.bot)

    selected = None

    for gift in gifts:
        if gift["id"] == gift_id:
            selected = gift
            break

    if not selected:

        await query.edit_message_text(
            "❌ Bu Gift hozir mavjud emas."
        )
        return

    balance = get_balance(query.from_user.id)

    if balance < selected["price"]:

        await query.edit_message_text(
            f"❌ Balansingiz yetarli emas.\n\n"
            f"💰 Balans: {balance} ⭐\n"
            f"🎁 Gift: {selected['price']} ⭐\n"
            f"➖ Yetishmaydi: {selected['price'] - balance} ⭐"
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ So‘rov yuborish",
                callback_data=(
                    f"confirmgift:{selected['id']}:"
                    f"{selected['price']}:"
                    f"{selected['emoji']}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Bekor qilish",
                callback_data="cancelgift",
            )
        ],
    ]

    await query.edit_message_text(
        f"🎁 Gift tanlandi\n\n"
        f"{selected['emoji']} Gift\n"
        f"⭐ Narxi: {selected['price']} Stars\n\n"
        f"💰 Sizning balansingiz: {balance} Stars\n\n"
        f"So‘rov yuborilsinmi?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# GIFT CONFIRM
# =========================================================

async def confirm_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 3)

    if len(parts) < 4:
        return

    gift_id = parts[1]

    try:
        price = int(parts[2])
    except Exception:
        return

    gift_name = parts[3]

    user_id = query.from_user.id

    conn = get_db()
    cur = conn.cursor()

    # Starsni atomik tarzda ushlab qolish
    cur.execute(
        """
        UPDATE users
        SET balance = balance - ?
        WHERE user_id = ?
        AND balance >= ?
        """,
        (
            price,
            user_id,
            price,
        ),
    )

    if cur.rowcount == 0:

        conn.rollback()
        conn.close()

        await query.edit_message_text(
            "❌ Balansingiz yetarli emas."
        )
        return

    cur.execute(
        """
        INSERT INTO gift_requests
        (user_id, price, status, created_at, gift_id, gift_name)
        VALUES (?, ?, 'pending', ?, ?, ?)
        """,
        (
            user_id,
            price,
            datetime.now().isoformat(),
            gift_id,
            gift_name,
        ),
    )

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    await query.edit_message_text(
        f"✅ Gift so‘rovi yuborildi!\n\n"
        f"🆔 So‘rov: #{request_id}\n"
        f"🎁 Gift: {gift_name}\n"
        f"⭐ Narxi: {price} Stars\n\n"
        f"⏳ Admin so‘rovni ko‘rib chiqadi."
    )

    # Adminga yuborish
    try:

        username = (
            f"@{query.from_user.username}"
            if query.from_user.username
            else "Username yo‘q"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"approve:{request_id}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish",
                    callback_data=f"reject:{request_id}",
                ),
            ]
        ]

        await context.bot.send_message(
            ADMIN_ID,
            f"🎁 Yangi Gift so‘rovi!\n\n"
            f"🆔 So‘rov: #{request_id}\n"
            f"👤 Foydalanuvchi: {query.from_user.first_name}\n"
            f"🔗 Username: {username}\n"
            f"🆔 User ID: {user_id}\n"
            f"🎁 Gift: {gift_name}\n"
            f"⭐ Narxi: {price}\n\n"
            f"Foydalanuvchi Starsni oldindan ushlab turdi.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        print("Admin notification error:", e)


# =========================================================
# GIFT CANCEL
# =========================================================

async def cancel_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ Gift so‘rovi bekor qilindi."
    )


# =========================================================
# ADMIN REQUESTS
# =========================================================

async def requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM gift_requests
        WHERE status IN ('pending', 'approved')
        ORDER BY id DESC
        """
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:

        await update.message.reply_text(
            "📭 Hozircha ochiq Gift so‘rovlari yo‘q."
        )
        return

    for row in rows:

        status_text = (
            "⏳ Kutilmoqda"
            if row["status"] == "pending"
            else "✅ Tasdiqlangan — Giftni yuboring"
        )

        keyboard = []

        if row["status"] == "pending":

            keyboard.append([
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"approve:{row['id']}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish",
                    callback_data=f"reject:{row['id']}",
                ),
            ])

        elif row["status"] == "approved":

            keyboard.append([
                InlineKeyboardButton(
                    "🎁 Berildi",
                    callback_data=f"delivered:{row['id']}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish",
                    callback_data=f"rejectapproved:{row['id']}",
                ),
            ])

        await update.message.reply_text(
            f"🎁 Gift so‘rovi #{row['id']}\n\n"
            f"👤 User ID: {row['user_id']}\n"
            f"🎁 Gift: {row['gift_name']}\n"
            f"⭐ Narxi: {row['price']}\n"
            f"📌 Holat: {status_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# =========================================================
# ADMIN REQUEST CALLBACK
# =========================================================

async def request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Siz admin emassiz.", show_alert=True)
        return

    await query.answer()

    action, request_id_text = query.data.split(":", 1)

    try:
        request_id = int(request_id_text)
    except Exception:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM gift_requests
        WHERE id = ?
        """,
        (request_id,),
    )

    request = cur.fetchone()

    if not request:

        conn.close()

        await query.edit_message_text(
            "❌ So‘rov topilmadi."
        )
        return

    user_id = request["user_id"]
    price = request["price"]

    # -----------------------------------------------------
    # TASDIQLASH
    # -----------------------------------------------------

    if action == "approve":

        cur.execute(
            """
            UPDATE gift_requests
            SET status = 'approved'
            WHERE id = ?
            AND status = 'pending'
            """,
            (request_id,),
        )

        if cur.rowcount == 0:

            conn.close()

            await query.answer(
                "Bu so‘rov allaqachon ko‘rib chiqilgan.",
                show_alert=True,
            )
            return

        conn.commit()
        conn.close()

        try:
            await context.bot.send_message(
                user_id,
                f"✅ Gift so‘rovingiz tasdiqlandi!\n\n"
                f"🎁 Gift: {request['gift_name']}\n"
                f"⭐ Narxi: {price} Stars\n\n"
                f"⏳ Admin Giftni qo‘lda yuboradi."
            )
        except Exception:
            pass

        keyboard = [
            [
                InlineKeyboardButton(
                    "🎁 Berildi",
                    callback_data=f"delivered:{request_id}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish",
                    callback_data=f"rejectapproved:{request_id}",
                ),
            ]
        ]

        await query.edit_message_text(
            f"✅ So‘rov #{request_id} tasdiqlandi.\n\n"
            f"🎁 Gift: {request['gift_name']}\n"
            f"👤 User ID: {user_id}\n"
            f"⭐ {price} Stars\n\n"
            f"⚠️ Endi Giftni Telegram orqali foydalanuvchiga "
            f"qo‘lda yuboring.\n\n"
            f"Yuborganingizdan keyin «🎁 Berildi» tugmasini bosing.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # -----------------------------------------------------
    # PENDING RAD ETISH
    # -----------------------------------------------------

    elif action == "reject":

        cur.execute(
            """
            UPDATE gift_requests
            SET status = 'rejected'
            WHERE id = ?
            AND status = 'pending'
            """,
            (request_id,),
        )

        if cur.rowcount == 0:

            conn.close()

            await query.answer(
                "Bu so‘rov allaqachon ko‘rib chiqilgan.",
                show_alert=True,
            )
            return

        cur.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
            """,
            (price, user_id),
        )

        conn.commit()
        conn.close()

        try:
            await context.bot.send_message(
                user_id,
                f"❌ Gift so‘rovingiz rad etildi.\n\n"
                f"⭐ {price} Stars balansingizga qaytarildi."
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"❌ So‘rov #{request_id} rad etildi.\n\n"
            f"⭐ {price} Stars foydalanuvchiga qaytarildi."
        )

    # -----------------------------------------------------
    # GIFT BERILDI
    # -----------------------------------------------------

    elif action == "delivered":

        cur.execute(
            """
            UPDATE gift_requests
            SET status = 'delivered'
            WHERE id = ?
            AND status = 'approved'
            """,
            (request_id,),
        )

        if cur.rowcount == 0:

            conn.close()

            await query.answer(
                "Bu so‘rov allaqachon yakunlangan.",
                show_alert=True,
            )
            return

        conn.commit()
        conn.close()

        try:
            await context.bot.send_message(
                user_id,
                f"🎉 Giftingiz berildi!\n\n"
                f"🎁 {request['gift_name']}\n\n"
                f"Rahmat! ⭐ FrostStars"
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"🎁 So‘rov #{request_id} yakunlandi.\n\n"
            f"Gift foydalanuvchiga berildi."
        )

    # -----------------------------------------------------
    # TASDIQLANGAN SO‘ROVNI RAD ETISH
    # -----------------------------------------------------

    elif action == "rejectapproved":

        cur.execute(
            """
            UPDATE gift_requests
            SET status = 'rejected'
            WHERE id = ?
            AND status = 'approved'
            """,
            (request_id,),
        )

        if cur.rowcount == 0:

            conn.close()

            await query.answer(
                "Bu so‘rov allaqachon yakunlangan.",
                show_alert=True,
            )
            return

        cur.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
            """,
            (price, user_id),
        )

        conn.commit()
        conn.close()

        try:
            await context.bot.send_message(
                user_id,
                f"❌ Tasdiqlangan Gift so‘rovi bekor qilindi.\n\n"
                f"⭐ {price} Stars balansingizga qaytarildi."
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"❌ So‘rov #{request_id} bekor qilindi.\n\n"
            f"⭐ {price} Stars qaytarildi."
        )


# =========================================================
# BOT STARS
# =========================================================

async def bot_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "⭐ FrostStars Stars tizimi\n\n"
        "Foydalanuvchilarning Starslari bot ichidagi "
        "ichki balans hisoblanadi.\n\n"
        "🎁 Giftlar admin tomonidan qo‘lda yuboriladi.\n\n"
        "Bu bo‘lim real Telegram Stars balansini "
        "ko‘rsatmaydi."
    )


# =========================================================
# ADMIN CHANNEL MENU
# =========================================================

async def channel_admin_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Kanal qo‘shish",
                callback_data="adminchannel:add",
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Kanallar",
                callback_data="adminchannel:list",
            )
        ],
    ]

    await update.message.reply_text(
        "📢 Kanal boshqaruvi\n\n"
        "Bu yerda kanallarni Telegramning o‘zidan "
        "qo‘shishingiz va boshqarishingiz mumkin.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# CHANNEL LIST
# =========================================================

async def channel_admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Adminlar uchun.", show_alert=True)
        return

    await query.answer()

    action = query.data.split(":", 1)[1]

    if action == "add":

        context.user_data["channel_add_step"] = "channel_id"

        await query.edit_message_text(
            "➕ Yangi kanal qo‘shish\n\n"
            "1️⃣ Kanal username'ini yuboring.\n\n"
            "Masalan:\n"
            "@YangiKanal"
        )

        return

    if action == "list":

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, channel_id, title, reward
            FROM channels
            ORDER BY id ASC
            """
        )

        channels = cur.fetchall()
        conn.close()

        if not channels:

            await query.edit_message_text(
                "📭 Hozircha kanallar yo‘q."
            )
            return

        keyboard = []

        for channel in channels:

            keyboard.append([
                InlineKeyboardButton(
                    f"✏️ {channel['title']} — {channel['reward']} ⭐",
                    callback_data=f"editchannel:{channel['id']}",
                )
            ])

            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 O‘chirish: {channel['channel_id']}",
                    callback_data=f"deletechannel:{channel['id']}",
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "➕ Kanal qo‘shish",
                callback_data="adminchannel:add",
            )
        ])

        text = "📋 Kanallar:\n\n"

        for channel in channels:
            text += (
                f"#{channel['id']} "
                f"{channel['title']}\n"
                f"🔗 {channel['channel_id']}\n"
                f"⭐ Mukofot: {channel['reward']}\n\n"
            )

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# =========================================================
# CHANNEL TEXT INPUT
# =========================================================

async def channel_admin_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    step = context.user_data.get("channel_add_step")

    if not step:
        return

    text = update.message.text.strip()

    # -----------------------------------------------------
    # 1. CHANNEL USERNAME
    # -----------------------------------------------------

    if step == "channel_id":

        if not text.startswith("@"):

            await update.message.reply_text(
                "❌ Kanal username @ bilan boshlanishi kerak.\n\n"
                "Masalan: @YangiKanal"
            )
            return

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id
            FROM channels
            WHERE channel_id = ?
            """,
            (text,),
        )

        exists = cur.fetchone()

        conn.close()

        if exists:

            await update.message.reply_text(
                "❌ Bu kanal allaqachon qo‘shilgan."
            )
            return

        # Kanalni tekshirish
        try:

            chat = await context.bot.get_chat(text)

            if chat.type not in ["channel", "supergroup"]:

                await update.message.reply_text(
                    "❌ Bu username kanalga tegishli emas."
                )
                return

        except Exception as e:

            await update.message.reply_text(
                "❌ Kanalni topib bo‘lmadi.\n\n"
                "Username to‘g‘ri ekanini tekshiring.\n"
                "Masalan: @YangiKanal"
            )

            print("New channel check error:", e)
            return

        context.user_data["new_channel_id"] = text

        context.user_data["channel_add_step"] = "title"

        await update.message.reply_text(
            "✅ Kanal topildi.\n\n"
            "2️⃣ Kanal nomini yuboring.\n\n"
            "Masalan:\n"
            "📢 Yangi kanal"
        )

        return

    # -----------------------------------------------------
    # 2. TITLE
    # -----------------------------------------------------

    if step == "title":

        context.user_data["new_channel_title"] = text

        context.user_data["channel_add_step"] = "reward"

        await update.message.reply_text(
            "3️⃣ Mukofot miqdorini yuboring.\n\n"
            "Masalan:\n"
            "15"
        )

        return

    # -----------------------------------------------------
    # 3. REWARD
    # -----------------------------------------------------

    if step == "reward":

        try:
            reward = int(text)
        except ValueError:

            await update.message.reply_text(
                "❌ Faqat raqam kiriting.\n\n"
                "Masalan: 15"
            )
            return

        if reward <= 0:

            await update.message.reply_text(
                "❌ Mukofot 0 dan katta bo‘lishi kerak."
            )
            return

        channel_id = context.user_data.get("new_channel_id")
        title = context.user_data.get("new_channel_title")

        conn = get_db()
        cur = conn.cursor()

        try:

            cur.execute(
                """
                INSERT INTO channels
                (channel_id, title, reward, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    channel_id,
                    title,
                    reward,
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:

            conn.rollback()
            conn.close()

            await update.message.reply_text(
                "❌ Bu kanal allaqachon mavjud."
            )

            context.user_data.clear()
            return

        conn.close()

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ Kanal muvaffaqiyatli qo‘shildi!\n\n"
            f"📢 {title}\n"
            f"🔗 {channel_id}\n"
            f"⭐ Mukofot: {reward}\n\n"
            f"⚠️ Endi botni shu kanalga ADMIN qilib qo‘ying."
        )

        return


# =========================================================
# EDIT CHANNEL
# =========================================================

async def edit_channel_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Adminlar uchun.", show_alert=True)
        return

    await query.answer()

    channel_id = int(query.data.split(":")[1])

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM channels
        WHERE id = ?
        """,
        (channel_id,),
    )

    channel = cur.fetchone()
    conn.close()

    if not channel:

        await query.edit_message_text(
            "❌ Kanal topilmadi."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "⭐ Mukofotni o‘zgartirish",
                callback_data=f"editreward:{channel_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Kanalni o‘chirish",
                callback_data=f"deletechannel:{channel_id}",
            )
        ],
    ]

    await query.edit_message_text(
        f"📢 {channel['title']}\n\n"
        f"🔗 {channel['channel_id']}\n"
        f"⭐ Hozirgi mukofot: {channel['reward']}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# EDIT REWARD
# =========================================================

async def edit_reward_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Adminlar uchun.", show_alert=True)
        return

    await query.answer()

    channel_id = int(query.data.split(":")[1])

    context.user_data["edit_reward_channel"] = channel_id

    await query.edit_message_text(
        "⭐ Yangi mukofot miqdorini yuboring.\n\n"
        "Masalan: 20"
    )


# =========================================================
# DELETE CHANNEL
# =========================================================

async def delete_channel_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Adminlar uchun.", show_alert=True)
        return

    await query.answer()

    channel_id = int(query.data.split(":")[1])

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM channels
        WHERE id = ?
        """,
        (channel_id,),
    )

    channel = cur.fetchone()

    if not channel:

        conn.close()

        await query.edit_message_text(
            "❌ Kanal topilmadi."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Ha, o‘chirish",
                callback_data=f"confirmdelete:{channel_id}",
            ),
            InlineKeyboardButton(
                "❌ Yo‘q",
                callback_data=f"editchannel:{channel_id}",
            ),
        ]
    ]

    conn.close()

    await query.edit_message_text(
        f"⚠️ Shu kanalni o‘chirmoqchimisiz?\n\n"
        f"📢 {channel['title']}\n"
        f"🔗 {channel['channel_id']}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# CONFIRM DELETE
# =========================================================

async def confirm_delete_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Adminlar uchun.", show_alert=True)
        return

    await query.answer()

    channel_id = int(query.data.split(":")[1])

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM channels
        WHERE id = ?
        """,
        (channel_id,),
    )

    conn.commit()
    conn.close()

    await query.edit_message_text(
        "🗑 Kanal o‘chirildi."
    )


# =========================================================
# EDIT REWARD TEXT
# =========================================================

async def edit_reward_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    channel_id = context.user_data.get("edit_reward_channel")

    if not channel_id:
        return

    try:
        reward = int(update.message.text.strip())
    except ValueError:

        await update.message.reply_text(
            "❌ Faqat raqam kiriting.\n\n"
            "Masalan: 20"
        )
        return

    if reward <= 0:

        await update.message.reply_text(
            "❌ Mukofot 0 dan katta bo‘lishi kerak."
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE channels
        SET reward = ?
        WHERE id = ?
        """,
        (
            reward,
            channel_id,
        ),
    )

    conn.commit()
    conn.close()

    context.user_data.pop("edit_reward_channel", None)

    await update.message.reply_text(
        f"✅ Mukofot o‘zgartirildi.\n\n"
        f"⭐ Yangi mukofot: {reward}"
    )


# =========================================================
# UNKNOWN / TEXT ROUTER
# =========================================================

async def text_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id == ADMIN_ID:

        # Mukofotni o'zgartirish
        if context.user_data.get("edit_reward_channel"):
            await edit_reward_text(update, context)
            return

        # Yangi kanal qo'shish
        if context.user_data.get("channel_add_step"):
            await channel_admin_text(update, context)
            return

    text = update.message.text

    if text == "⭐ Stars ishlash":
        await stars_work(update, context)

    elif text == "👥 Referal":
        await referral(update, context)

    elif text == "📊 Statistika":
        await statistics(update, context)

    elif text == "💳 Gift olish":
        await gift_menu(update, context)

    elif text == "ℹ️ Qoidalar":
        await rules(update, context)

    elif text == "🎁 So‘rovlar":
        await requests(update, context)

    elif text == "⭐ Bot Stars":
        await bot_stars(update, context)

    elif text == "📢 Kanallar":
        await channel_admin_menu(update, context)


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    # Task
    application.add_handler(
        CallbackQueryHandler(
            task_callback,
            pattern=r"^task:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            check_task_callback,
            pattern=r"^checktask:"
        )
    )

    # Gifts
    application.add_handler(
        CallbackQueryHandler(
            real_gift_callback,
            pattern=r"^realgift:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            confirm_gift_callback,
            pattern=r"^confirmgift:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            cancel_gift_callback,
            pattern=r"^cancelgift$"
        )
    )

    # Gift requests
    application.add_handler(
        CallbackQueryHandler(
            request_callback,
            pattern=r"^(approve|reject|delivered|rejectapproved):"
        )
    )

    # Channel management
    application.add_handler(
        CallbackQueryHandler(
            channel_admin_callback,
            pattern=r"^adminchannel:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            edit_channel_callback,
            pattern=r"^editchannel:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            edit_reward_callback,
            pattern=r"^editreward:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            delete_channel_callback,
            pattern=r"^deletechannel:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            confirm_delete_callback,
            pattern=r"^confirmdelete:"
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_router,
        )
    )

    print("🤖 FrostStars bot ishga tushdi...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
