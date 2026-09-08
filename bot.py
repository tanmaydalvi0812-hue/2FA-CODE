import json
import os
import secrets
import time

import pyotp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

KEYS_FILE = "keys.json"


# =========================
# DATABASE
# =========================

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}

    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_keys(keys):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=4)


# =========================
# ACCESS KEY
# =========================

def create_key():
    part1 = secrets.token_hex(3).upper()
    part2 = secrets.token_hex(3).upper()

    return f"KING-{part1}-{part2}"


def get_user_key(user_id):
    keys = load_keys()

    for key, data in keys.items():

        if data.get("user_id") != user_id:
            continue

        expires = data.get("expires", 0)

        if expires == 0:
            return key, data

        if time.time() < expires:
            return key, data

    return None, None


def format_expiry(timestamp):
    if timestamp == 0:
        return "Lifetime"

    return time.strftime(
        "%d/%m/%Y %H:%M",
        time.localtime(timestamp)
    )


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔐 KING 2FA\n\n"
        "Send your access key.\n\n"
        "Example:\n"
        "KING-ABC123-XYZ789\n\n"
        "After activation, send your own TOTP secret directly.\n\n"
        "MADE BY :- @KINGxHREE"
    )


# =========================
# ADMIN: GENERATE KEY
# =========================

async def gen2fakey(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Admin only."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n\n"
            "/gen2fakey 1\n"
            "/gen2fakey 7\n"
            "/gen2fakey 30\n"
            "/gen2fakey lifetime"
        )
        return

    duration = context.args[0].lower()

    if duration == "lifetime":

        expires = 0
        plan = "Lifetime"

    else:

        try:
            days = int(duration)

            if days <= 0:
                raise ValueError

            expires = time.time() + (
                days * 24 * 60 * 60
            )

            plan = f"{days} Days"

        except ValueError:

            await update.message.reply_text(
                "❌ Invalid duration.\n\n"
                "Use 1, 7, 30 or lifetime."
            )
            return

    key = create_key()

    keys = load_keys()

    keys[key] = {
        "plan": plan,
        "expires": expires,
        "user_id": None,
        "created": time.time(),
        "revoked": False
    }

    save_keys(keys)

    await update.message.reply_text(
        "🔑 KING 2FA KEY\n\n"
        f"Key: {key}\n"
        f"Plan: {plan}\n"
        "Status: Unused\n\n"
        "MADE BY :- @KINGxHREE"
    )


# =========================
# ADMIN: LIST KEYS
# =========================

async def listkeys(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Admin only."
        )
        return

    keys = load_keys()

    if not keys:
        await update.message.reply_text(
            "No keys created."
        )
        return

    output = "🔑 KING 2FA KEYS\n\n"

    for key, data in keys.items():

        if data.get("revoked"):
            status = "🚫 Revoked"

        elif data.get("user_id") is None:
            status = "🟢 Unused"

        else:
            status = f"👤 Used by {data.get('user_id')}"

        output += (
            f"{key}\n"
            f"Plan: {data.get('plan')}\n"
            f"Status: {status}\n"
            f"Expires: "
            f"{format_expiry(data.get('expires', 0))}\n\n"
        )

    await update.message.reply_text(output)


# =========================
# ADMIN: REVOKE
# =========================

async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Admin only."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/revoke KING-XXXXXX-XXXXXX"
        )
        return

    key = context.args[0].upper()

    keys = load_keys()

    if key not in keys:
        await update.message.reply_text(
            "❌ Key not found."
        )
        return

    keys[key]["revoked"] = True

    save_keys(keys)

    await update.message.reply_text(
        "✅ Key revoked."
    )


# =========================
# CUSTOMER MESSAGE
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    text = update.message.text.strip()

    keys = load_keys()

    # -------------------------
    # FIRST: CHECK ACCESS KEY
    # -------------------------

    if text.upper() in keys:

        key = text.upper()
        data = keys[key]

        if data.get("revoked"):
            await update.message.reply_text(
                "❌ This key has been revoked."
            )
            return

        expires = data.get("expires", 0)

        if expires != 0 and time.time() >= expires:
            await update.message.reply_text(
                "❌ This key has expired."
            )
            return

        existing_user = data.get("user_id")

        if existing_user is not None and existing_user != user_id:

            await update.message.reply_text(
                "❌ This key is already activated "
                "by another user."
            )
            return

        data["user_id"] = user_id
        keys[key] = data

        save_keys(keys)

        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━\n"
            "🔐 KING 2FA\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "✅ ACCESS GRANTED\n\n"
            f"📅 Plan: {data.get('plan')}\n"
            f"⏳ Expires: "
            f"{format_expiry(expires)}\n\n"
            "Now send your own TOTP secret directly.\n\n"
            "⚠️ Never send your Instagram password.\n\n"
            "MADE BY :- @KINGxHREE"
        )

        return

    # -------------------------
    # CHECK USER ACCESS
    # -------------------------

    user_key, user_data = get_user_key(user_id)

    if not user_key:

        await update.message.reply_text(
            "❌ Access denied.\n\n"
            "Send a valid KING 2FA access key first."
        )
        return

    # -------------------------
    # TOTP PROCESSING
    # -------------------------

    secret = text.replace(" ", "").replace("-", "")

    # Basic TOTP Base32 validation
    try:

        totp = pyotp.TOTP(secret)

        code = totp.now()

        remaining = 30 - (
            int(time.time()) % 30
        )

        # Don't store or log the secret.
        await update.message.reply_text(
            "🔐 KING 2FA\n\n"
            "Account: My Instagram\n"
            f"Code: {code}\n"
            f"Expires: {remaining} seconds\n\n"
            "⚠️ Keep this code private.\n\n"
            "MADE BY :- @KINGxHREE"
        )

    except Exception:

        await update.message.reply_text(
            "❌ Invalid TOTP key.\n\n"
            "Send a valid TOTP secret."
        )


# =========================
# HELP
# =========================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔐 KING 2FA\n\n"
        "Customer:\n"
        "1. Send access key\n"
        "2. Send your own TOTP secret\n\n"
        "Admin:\n"
        "/gen2fakey 30\n"
        "/keys\n"
        "/revoke KEY\n\n"
        "MADE BY :- @KINGxHREE"
    )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    if ADMIN_ID == 0:
        raise RuntimeError(
            "ADMIN_ID environment variable is missing."
        )

    app = Application.builder().token(
        BOT_TOKEN
    ).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("gen2fakey", gen2fakey)
    )

    app.add_handler(
        CommandHandler("keys", listkeys)
    )

    app.add_handler(
        CommandHandler("revoke", revoke)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("KING 2FA bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
