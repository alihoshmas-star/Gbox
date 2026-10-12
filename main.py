import os
import re
import logging
from io import BytesIO
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def extract_id(url: str):
    """استخراج ID از لینک img یا a"""
    # برای /img/XXXX یا /a/XXXX
    match = re.search(r'goonbox\.cr/(?:img|a)/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام!\n\n"
        "لینک آلبوم یا عکس goonbox رو بفرست:\n"
        "• آلبوم: `https://goonbox.cr/a/XXXXX`\n"
        "• عکس تکی: `https://goonbox.cr/img/XXXXX`\n\n"
        "همه عکس‌های آلبوم رو برات دانلود و ارسال می‌کنم.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "goonbox.cr" not in url:
        await update.message.reply_text("فقط لینک‌های goonbox.cr پشتیبانی می‌شن.")
        return

    album_id = extract_id(url)
    if not album_id:
        await update.message.reply_text("لینک معتبر نیست. مثال:\nhttps://goonbox.cr/a/azjQGo")
        return

    is_album = "/a/" in url
    await update.message.reply_text("در حال دریافت اطلاعات...")

    try:
        if is_album:
            api_url = f"https://goonbox.cr/api/albums/{album_id}"
        else:
            api_url = f"https://goonbox.cr/api/images/{album_id}"

        resp = requests.get(api_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        images = []

        if is_album:
            # آلبوم
            album_title = data.get("album", {}).get("title", "آلبوم")
            images = data.get("images", [])
            
            # اگر صفحه‌بندی داشت، صفحات بعدی رو هم بگیر
            pagination = data.get("pagination", {})
            current = pagination.get("current_page", 1)
            last = pagination.get("last_page", 1)

            while current < last:
                current += 1
                next_resp = requests.get(
                    f"{api_url}?page={current}",
                    headers=HEADERS,
                    timeout=20
                )
                if next_resp.status_code == 200:
                    next_data = next_resp.json()
                    images.extend(next_data.get("images", []))
                else:
                    break

            await update.message.reply_text(
                f"آلبوم: **{album_title}**\n"
                f"تعداد عکس: {len(images)}\n"
                f"شروع ارسال...",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # عکس تکی
            img = data.get("image")
            if img:
                images = [img]
            await update.message.reply_text("عکس پیدا شد. در حال ارسال...")

        if not images:
            await update.message.reply_text("هیچ عکسی پیدا نشد.")
            return

        sent = 0
        failed = 0

        for img in images:
            original_url = img.get("original_url")
            if not original_url:
                failed += 1
                continue

            try:
                img_resp = requests.get(original_url, headers=HEADERS, timeout=30)
                if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                    bio = BytesIO(img_resp.content)
                    bio.name = f"{img.get('encoded_id', 'photo')}.jpg"
                    await update.message.reply_photo(photo=bio)
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"خطا در دانلود {original_url}: {e}")
                failed += 1

        await update.message.reply_text(
            f"تمام شد ✅\n"
            f"ارسال موفق: {sent}\n"
            f"ناموفق: {failed}"
        )

    except requests.exceptions.HTTPError as e:
        await update.message.reply_text(f"خطای سرور: {e.response.status_code}")
    except Exception as e:
        logger.exception(e)
        await update.message.reply_text(f"خطا رخ داد:\n{str(e)}")

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN تنظیم نشده است")
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    print("ربات روشن شد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
