# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ================== ÇÀÌÅÍÈÒÅ ÝÒÈ 3 ÇÍÀ×ÅÍÈß ==================
BOT_TOKEN = "8818244911:AAEYe7-3fcOyHUOvvN8dN64P68hUeM6mVkc"
SUPABASE_URL = "https://ytnvmyivcrbeorfwreoy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0bnZteWl2Y3JiZW9yZndyZW95Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg5MzA3MTksImV4cCI6MjA5NDUwNjcxOX0.JlE8z_VrAiFdg_vVPi8EujXMUG1QuX9HxVcWa0DzM54"
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="?? Ìîè ïîäïèñêè")],
        [KeyboardButton(text="? Äîáàâèòü ïîäïèñêó")],
        [KeyboardButton(text="?? Ïðîôèëü")]
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
        print(f"Îøèáêà: {e}")
    
    await message.answer(
        "Ïðèâåò! ß ïîìîãó îòñëåæèâàòü ïîäïèñêè.\n\n"
        "• Áåñïëàòíî: äî 3 ïîäïèñîê\n"
        "• Íàïîìèíàþ çà 1 äåíü äî ñïèñàíèÿ\n\n"
        "Íàæìèòå «Äîáàâèòü ïîäïèñêó» èëè íàïèøèòå:\n"
        "«ßíäåêñ Ïëþñ 299 25 monthly»",
        reply_markup=main_kb
    )

@dp.message(F.text == "? Äîáàâèòü ïîäïèñêó")
async def add_btn(message: types.Message):
    await message.answer(
        "Íàïèøèòå â ôîðìàòå:\n<b>Íàçâàíèå Ñóììà Äåíü Ïåðèîä</b>\n\n"
        "Ïðèìåð: ßíäåêñ Ïëþñ 299 15 monthly",
        parse_mode="HTML"
    )

@dp.message(F.text.regexp(r"^[\w\s\-à-ÿÀ-ß¸¨\.]+ \d+ \d+ (monthly|yearly)$"))
async def parse_subscription(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.rsplit(" ", 3)
    name, amount, day, freq = parts[0], int(parts[1]), int(parts[2]), parts[3]
    
    try:
        subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        user = supabase.table("users").select("is_premium").eq("telegram_id", user_id).execute()
        is_premium = user.data[0]["is_premium"] if user.data else False
        
        if len(subs.data) >= 3 and not is_premium:
            await message.answer("? Ëèìèò: 3 ïîäïèñêè. Ïðåìèóì 149 ?/ìåñ.")
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
            "next_date": next_date.strftime("%Y-%m-%d"), "frequency": freq, "category": "ïðî÷åå"
        }).execute()
        
        await message.answer(
            f"? <b>{name}</b>\nÑóììà: {amount} ?\nÑëåä. ñïèñàíèå: {next_date.strftime('%d.%m.%Y')}",
            parse_mode="HTML", reply_markup=main_kb
        )
    except Exception as e:
        await message.answer(f"Îøèáêà: {e}")
        print(e)

@dp.message(F.text == "?? Ìîè ïîäïèñêè")
async def list_subs(message: types.Message):
    user_id = message.from_user.id
    try:
        subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        if not subs.data:
            await message.answer("Ïîäïèñîê ïîêà íåò.")
            return
        
        total = sum(s["amount"] for s in subs.data)
        text = f"<b>Ïîäïèñêè</b> ({len(subs.data)} øò.)\nÂñåãî: <b>{total} ?/ìåñ</b>\n\n"
        for s in subs.data:
            days = (datetime.strptime(s["next_date"], "%Y-%m-%d") - datetime.now()).days
            emoji = "??" if days <= 1 else "??" if days <= 3 else "??"
            text += f"{emoji} <b>{s['name']}</b> — {s['amount']} ?\nÑïèñàíèå: {s['next_date']} ({days} äí.)\n\n"
        await message.answer(text, parse_mode="HTML", reply_markup=main_kb)
    except Exception as e:
        print(e)

@dp.message(F.text == "?? Ïðîôèëü")
async def profile(message: types.Message):
    user_id = message.from_user.id
    try:
        user = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
        subs = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        status = "?? Ïðåìèóì" if user.data and user.data[0]["is_premium"] else "?? Áåñïëàòíî (3 ïîäïèñêè)"
        await message.answer(f"<b>Ïðîôèëü</b>\n\nÏîäïèñîê: {len(subs.data)}\nÑòàòóñ: {status}\n\nÏðåìèóì: 149 ?/ìåñ", parse_mode="HTML")
    except Exception as e:
        print(e)

async def check_reminders():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        subs = supabase.table("subscriptions").select("*, users!inner(telegram_id)").eq("next_date", tomorrow).eq("is_active", True).execute()
        for s in subs.data:
            uid = s["users"]["telegram_id"]
            await bot.send_message(uid, f"? Çàâòðà ñïèñàíèå: <b>{s['name']}</b> — {s['amount']} ?", parse_mode="HTML")
            old = datetime.strptime(s["next_date"], "%Y-%m-%d")
            new = old.replace(month=old.month+1) if old.month < 12 else old.replace(year=old.year+1, month=1)
            if s["frequency"] == "yearly":
                new = old.replace(year=old.year+1)
            supabase.table("subscriptions").update({"next_date": new.strftime("%Y-%m-%d")}).eq("id", s["id"]).execute()
    except Exception as e:
        print(f"Íàïîìèíàíèÿ: {e}")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, CronTrigger(hour=9, minute=0))
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
