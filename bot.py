import requests
from bs4 import BeautifulSoup
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
import asyncio
from datetime import datetime, timedelta
import pytz
import re

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن‌ها و تنظیمات
BOT_TOKEN = "8352379642:AAHFHEU_Z5MuLEz2-maRMH0murAAJVrwx94"
GROUP_ID = -4843735218

class ForexNewsBot:
    def __init__(self):
        self.base_url = "https://www.forexfactory.com"
        self.tehran_tz = pytz.timezone('Asia/Tehran')
        
    def convert_to_tehran_time(self, time_str):
        """تبدیل زمان به وقت تهران"""
        try:
            if time_str == "تمام روز" or not time_str.strip():
                return "تمام روز"
            
            if re.match(r'\d{1,2}:\d{2}', time_str):
                time_obj = datetime.strptime(time_str.strip(), '%H:%M')
                utc_time = datetime.utcnow().replace(
                    hour=time_obj.hour, 
                    minute=time_obj.minute, 
                    second=0, 
                    microsecond=0
                )
                tehran_time = utc_time.astimezone(self.tehran_tz)
                return tehran_time.strftime('%H:%M') + " (تهران)"
            
            return time_str + " (تهران)"
        except Exception as e:
            logger.error(f"Error converting time: {e}")
            return time_str

    def get_available_dates(self):
        """همه تاریخ‌های موجود در صفحه رو پیدا میکنه"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.base_url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            calendar_table = soup.find('table', class_='calendar__table')
            
            if not calendar_table:
                return []
            
            available_dates = []
            rows = calendar_table.find_all('tr', class_='calendar__row')
            
            for row in rows:
                date_row = row.find('td', class_='calendar__date')
                if date_row:
                    date_text = date_row.get_text(strip=True)
                    if date_text and date_text not in available_dates:
                        available_dates.append(date_text)
            
            logger.info(f"Available dates on site: {available_dates}")
            return available_dates
            
        except Exception as e:
            logger.error(f"Error getting available dates: {e}")
            return []

    def get_news_by_date_text(self, date_text):
        """اخبار بر اساس متن تاریخ از سایت میگیره"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.base_url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            calendar_table = soup.find('table', class_='calendar__table')
            
            if not calendar_table:
                return "❌ خطا در دریافت اطلاعات از سایت"
            
            news_items = []
            rows = calendar_table.find_all('tr', class_='calendar__row')
            found_target_date = False
            
            for row in rows:
                # چک کردن ردیف تاریخ
                current_date_row = row.find('td', class_='calendar__date')
                if current_date_row:
                    current_date_text = current_date_row.get_text(strip=True)
                    if current_date_text == date_text:
                        found_target_date = True
                    elif found_target_date:
                        # به تاریخ بعدی رسیدیم، متوقف شو
                        break
                
                if found_target_date:
                    time_cell = row.find('td', class_='calendar__time')
                    currency_cell = row.find('td', class_='calendar__currency')
                    event_cell = row.find('td', class_='calendar__event')
                    actual_cell = row.find('td', class_='calendar__actual')
                    forecast_cell = row.find('td', class_='calendar__forecast')
                    previous_cell = row.find('td', class_='calendar__previous')
                    
                    if all([time_cell, currency_cell, event_cell]):
                        time = time_cell.get_text(strip=True) or "تمام روز"
                        currency = currency_cell.get_text(strip=True)
                        event = event_cell.get_text(strip=True)
                        
                        if currency == 'USD':
                            actual = actual_cell.get_text(strip=True) if actual_cell else "-"
                            forecast = forecast_cell.get_text(strip=True) if forecast_cell else "-"
                            previous = previous_cell.get_text(strip=True) if previous_cell else "-"
                            tehran_time = self.convert_to_tehran_time(time)
                            
                            news_item = f"""
🕒 زمان: {tehran_time}
💰 ارز: {currency}
📊 رویداد: {event}
📈 قبلی: {previous}
🎯 پیش‌بینی: {forecast}
✅ واقعی: {actual}
────────────────────
"""
                            news_items.append(news_item)
            
            if not news_items:
                return f"📭 هیچ خبر USD برای {date_text} یافت نشد"
            
            date_header = f"📰 اخبار اقتصادی USD - {date_text}:\n"
            return date_header + "\n".join(news_items)
                
        except Exception as e:
            logger.error(f"Error getting news by date text: {e}")
            return f"❌ خطا در دریافت اخبار: {str(e)}"

    def get_today_news(self):
        """اخبار امروز رو پیدا میکنه"""
        try:
            available_dates = self.get_available_dates()
            if not available_dates:
                return "📭 هیچ خبری در سایت موجود نیست"
            
            # پیدا کردن تاریخ امروز در بین تاریخ‌های موجود
            today = datetime.now(self.tehran_tz)
            today_day = today.day
            today_month = today.strftime('%b')  # مثل Oct
            
            for date_text in available_dates:
                if str(today_day) in date_text and today_month in date_text:
                    return self.get_news_by_date_text(date_text)
            
            # اگر امروز پیدا نشد، اولین تاریخ موجود رو برگردون
            return self.get_news_by_date_text(available_dates[0])
            
        except Exception as e:
            logger.error(f"Error getting today news: {e}")
            return f"❌ خطا در دریافت اخبار امروز: {str(e)}"

async def start_command(update: Update, context: CallbackContext):
    """دستور start"""
    keyboard = [
        [InlineKeyboardButton("📊 اخبار امروز", callback_data="today_news")],
        [InlineKeyboardButton("🗓 اخبار هفته", callback_data="week_menu")],
        [InlineKeyboardButton("🔔 رویدادهای آینده", callback_data="upcoming")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 ربات اخبار فارکس خوش آمدید!\n"
        "لطفا یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: CallbackContext):
    """مدیریت کلیک روی دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    bot = ForexNewsBot()
    
    if query.data == "today_news":
        news = bot.get_today_news()
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if len(news) > 4000:
            parts = [news[i:i+4000] for i in range(0, len(news), 4000)]
            for part in parts:
                await context.bot.send_message(chat_id=query.message.chat_id, text=part)
            await context.bot.send_message(chat_id=query.message.chat_id, text="🔙 بازگشت:", reply_markup=reply_markup)
        else:
            await query.edit_message_text(news, reply_markup=reply_markup)
        
    elif query.data == "week_menu":
        # منوی هفته با تاریخ‌های واقعی موجود در سایت
        await show_available_dates(query, context)
    
    elif query.data.startswith("date_"):
        # نمایش اخبار تاریخ خاص
        date_text = query.data.replace("date_", "").replace("_", " ")
        news = bot.get_news_by_date_text(date_text)
        
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت به منوی تاریخ‌ها", callback_data="week_menu")],
            [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if len(news) > 4000:
            parts = [news[i:i+4000] for i in range(0, len(news), 4000)]
            for part in parts:
                await context.bot.send_message(chat_id=query.message.chat_id, text=part)
            await context.bot.send_message(chat_id=query.message.chat_id, text="🔙 بازگشت:", reply_markup=reply_markup)
        else:
            await query.edit_message_text(news, reply_markup=reply_markup)
    
    elif query.data == "upcoming":
        events = bot.get_today_news()
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if len(events) > 4000:
            parts = [events[i:i+4000] for i in range(0, len(events), 4000)]
            for part in parts:
                await context.bot.send_message(chat_id=query.message.chat_id, text=part)
            await context.bot.send_message(chat_id=query.message.chat_id, text="🔙 بازگشت:", reply_markup=reply_markup)
        else:
            await query.edit_message_text(events if events else "📭 رویداد آینده‌ای یافت نشد", reply_markup=reply_markup)
    
    elif query.data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("📊 اخبار امروز", callback_data="today_news")],
            [InlineKeyboardButton("🗓 اخبار هفته", callback_data="week_menu")],
            [InlineKeyboardButton("🔔 رویدادهای آینده", callback_data="upcoming")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🤖 ربات اخبار فارکس\nلطفا یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=reply_markup
        )

async def show_available_dates(query, context):
    """نمایش تاریخ‌های موجود در سایت"""
    bot = ForexNewsBot()
    available_dates = bot.get_available_dates()
    
    if not available_dates:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📭 هیچ تاریخ فعالی در سایت پیدا نشد",
            reply_markup=reply_markup
        )
        return
    
    keyboard = []
    for date_text in available_dates:
        # تبدیل به callback data (جای فضای خالی با underline)
        callback_data = f"date_{date_text.replace(' ', '_')}"
        keyboard.append([InlineKeyboardButton(f"📅 {date_text}", callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🗓 تاریخ‌های موجود در فارکس فکتوری:\n"
        "لطفا تاریخ مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def today_news_command(update: Update, context: CallbackContext):
    """دستور اخبار امروز"""
    bot = ForexNewsBot()
    news = bot.get_today_news()
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if len(news) > 4000:
        parts = [news[i:i+4000] for i in range(0, len(news), 4000)]
        for part in parts:
            await update.message.reply_text(part)
        await update.message.reply_text("🔙 بازگشت:", reply_markup=reply_markup)
    else:
        await update.message.reply_text(news, reply_markup=reply_markup)

async def week_news_command(update: Update, context: CallbackContext):
    """دستور اخبار هفته"""
    await update.message.reply_text(
        "لطفا از منوی زیر گزینه مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗓 منوی اخبار هفته", callback_data="week_menu")]
        ])
    )

# توابع زمان‌بندی شده
async def send_daily_news(context: CallbackContext):
    """ارسال اخبار روزانه"""
    try:
        bot = ForexNewsBot()
        news = bot.get_today_news()
        
        message = f"⏰ اخبار روزانه:\n{news}"
        if len(message) > 4000:
            message = message[:4000]
            
        await context.bot.send_message(chat_id=GROUP_ID, text=message)
        logger.info("اخبار روزانه ارسال شد")
            
    except Exception as e:
        logger.error(f"Error in daily news: {e}")

def main():
    """تابع اصلی"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("today", today_news_command))
    application.add_handler(CommandHandler("week", week_news_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # تنظیم job queue
    job_queue = application.job_queue
    tehrantz = pytz.timezone('Asia/Tehran')
    
    # اخبار روزانه - ساعت ۸ صبح به وقت تهران
    job_queue.run_daily(
        send_daily_news,
        time=datetime.strptime("08:00", "%H:%M").replace(tzinfo=tehrantz).time(),
        days=(0, 1, 2, 3, 4, 5, 6),
        name="daily_news"
    )
    
    logger.info("ربات هوشمند شروع به کار کرد...")
    print("🤖 ربات فعال شد! برای توقف Ctrl+C را بزنید")
    application.run_polling()

if __name__ == '__main__':
    main()