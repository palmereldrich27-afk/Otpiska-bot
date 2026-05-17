import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ================== ЗАМЕНИТЕ ЭТИ 3 ЗНАЧЕНИЯ ==================
BOT_TOKEN = "8818244911:AAEYe7-3fcOyHUOvvN8dN64P68hUeM6mVkc"
SUPABASE_URL = "https://ytnvmyivcrbeorfwreoy.supabase.co"
SUPABASE_KEY = "sb_publishable_hfkPckvm66I8VBQQT9x4WQ_nY83JRZM"
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="?? Мои подписки")],
        [KeyboardButton(text="? Добавить подписку")],
        [KeyboardButton(text="?? Профиль")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    try:
        existing = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
        if not existing.data:
            supabase.table("users").insert({
                "telegram_id": user_id,
                "username": username,
                "is_premium": False
            }).execute()
    except Exception as e:
        print(f"Ошибка: {e}")
    
    await message.answer(
        "Привет! Я помогу отслеживать подписки.\n\n"
        "• Бесплатно: до 3 подписок\n"
        "• Напоминаю за 1 день до списания\n\n"
        "Нажмите «Добавить подписку» или напишите:\n"
        "«Яндекс Плюс 299 25 monthly»",
        reply_markup=main_kb
    )

@dp.message(F.text == "? Добавить подписку")
async def add_btn(message: types.Message):
    await message.answer(
        "Напишите в формате:\n<b>Название Сумма День Период</b>\n\n"
        "Пример: Яндекс Плюс 299 15 monthly",
        parse_mode="HTML"
    )

@dp.message(F.text.regexp(r"^[\w\s\-а-яА-ЯёЁ\.]+ \d+ \d+ (monthly|yearly)$"))
async def parse_subscription(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.rsplit(" ", 3)
    name, amount, day, freq = parts[0], int(parts[1]), int(parts[2]), parts[3]
    
    try:
        subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        user = supabase.table("users").select("is_premium").eq("telegram_id", user_id).execute()
        is_premium = user.data[0]["is_premium"] if user.data else False
        
        if len(subs.data) >= 3 and not is_premium:
            await message.answer("? Лимит: 3 подписки. Премиум 149 ?/мес.")
            return
        
        today = datetime.now()
        if day >= today.day:
            next_date = today.replace(day=day)
        else:
            if today.month == 12:
                next_date = today.replace(year=today.year+1, month=1, day=day)
            else:
                next_date = today.replace(month=today.month+1, day=day)
        
        supabase.table("subscriptions").insert({
            "user_id": user_id, "name": name, "amount": amount,
            "next_date": next_date.strftime("%Y-%m-%d"), "frequency": freq, "category": "прочее"
        }).execute()
        
        await message.answer(
            f"? <b>{name}</b>\nСумма: {amount} ?\nСлед. списание: {next_date.strftime('%d.%m.%Y')}",
            parse_mode="HTML", reply_markup=main_kb
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        print(e)

@dp.message(F.text == "?? Мои подписки")
async def list_subs(message: types.Message):
    user_id = message.from_user.id
    try:
        subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        if not subs.data:
            await message.answer("Подписок пока нет.")
            return
        
        total = sum(s["amount"] for s in subs.data)
        text = f"<b>Подписки</b> ({len(subs.data)} шт.)\nВсего: <b>{total} ?/мес</b>\n\n"
        for s in subs.data:
            days = (datetime.strptime(s["next_date"], "%Y-%m-%d") - datetime.now()).days
            emoji = "??" if days <= 1 else "??" if days <= 3 else "??"
            text += f"{emoji} <b>{s['name']}</b> — {s['amount']} ?\nСписание: {s['next_date']} ({days} дн.)\n\n"
        await message.answer(text, parse_mode="HTML", reply_markup=main_kb)
    except Exception as e:
        print(e)

@dp.message(F.text == "?? Профиль")
async def profile(message: types.Message):
    user_id = message.from_user.id
    try:
        user = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
        subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        status = "?? Премиум" if user.data and user.data[0]["is_premium"] else "?? Бесплатно (3 подписки)"
        await message.answer(f"<b>Профиль</b>\n\nПодписок: {len(subs.data)}\nСтатус: {status}\n\nПремиум: 149 ?/мес", parse_mode="HTML")
    except Exception as e:
        print(e)

async def check_reminders():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        subs = supabase.table("subscriptions").select("*, users!inner(telegram_id)").eq("next_date", tomorrow).eq("is_active", True).execute()
        for s in subs.data:
            uid = s["users"]["telegram_id"]
            await bot.send_message(uid, f"? Завтра списание: <b>{s['name']}</b> — {s['amount']} ?", parse_mode="HTML")
            old = datetime.strptime(s["next_date"], "%Y-%m-%d")
            new = old.replace(month=old.month+1) if old.month < 12 else old.replace(year=old.year+1, month=1)
            if s["frequency"] == "yearly":
                new = old.replace(year=old.year+1)
            supabase.table("subscriptions").update({"next_date": new.strftime("%Y-%m-%d")}).eq("id", s["id"]).execute()
    except Exception as e:
        print(f"Напоминания: {e}")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, CronTrigger(hour=9, minute=0))
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())