#!/usr/bin/env python3
"""
Quick test - check current database channels
"""
import asyncio
import os
import sqlite3
from aiogram import Bot
from dotenv import load_dotenv

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN topilmadi!")
    exit(1)

bot = Bot(BOT_TOKEN)


async def test_current_channels():
    print("="*70)
    print("DATABASE-DAGI KANALLARNI TEKSHIRISH")
    print("="*70)
    
    # Read channels from database
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM required_channels")
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not channels:
        print("\n⚠️  Database-da hech qanday kanal yo'q!")
        print("   Admin panel orqali kanal qo'shing: /admin → 🧩 Majburiy kanallar")
        return
    
    print(f"\n📋 Database-da {len(channels)} ta kanal topildi:\n")
    
    telegram_channels = []
    youtube_channels = []
    
    for ch in channels:
        if "yt:" in ch:
            youtube_channels.append(ch)
            print(f"   ▶️  {ch} (YouTube - skip qilinadi)")
        else:
            telegram_channels.append(ch)
            print(f"   📢 {ch} (Telegram - tekshiriladi)")
    
    print("\n" + "="*70)
    print("XULOSA")
    print("="*70)
    print(f"📢 Telegram kanallari:  {len(telegram_channels)} ta (TEKSHIRILADI)")
    print(f"▶️  YouTube kanallari:   {len(youtube_channels)} ta (SKIP QILINADI)")
    
    if not telegram_channels:
        print("\n⚠️  OGOHLANTIRISH: Hech qanday Telegram kanal yo'q!")
        print("   Foydalanuvchilar botga kirishi uchun kamida 1 ta Telegram kanal qo'shing.")
    
    print("\n" + "="*70)
    
    # Test with user ID if provided
    user_id_str = input("\nTest uchun User ID kiriting (skip uchun Enter): ").strip()
    
    if user_id_str and telegram_channels:
        try:
            user_id = int(user_id_str)
            print(f"\n🔍 User {user_id} uchun Telegram kanallarni tekshiryapman...\n")
            
            not_subscribed = []
            for ch in telegram_channels:
                try:
                    chat_ref = ch
                    if ch.lstrip("-").isdigit():
                        chat_ref = int(ch)
                    
                    member = await bot.get_chat_member(chat_ref, user_id)
                    
                    if member.status in ("member", "administrator", "creator"):
                        print(f"   ✅ {ch} - OBUNA BO'LGAN")
                    else:
                        print(f"   ❌ {ch} - OBUNA BO'LMAGAN (status: {member.status})")
                        not_subscribed.append(ch)
                except Exception as e:
                    print(f"   ⚠️  {ch} - XATO: {type(e).__name__}")
                    not_subscribed.append(ch)
            
            print("\n" + "="*70)
            if not not_subscribed:
                print("✅ Foydalanuvchi BARCHA Telegram kanallariga obuna bo'lgan!")
                print("   Bot kirishga ruxsat beradi.")
            else:
                print(f"❌ Foydalanuvchi {len(not_subscribed)} ta kanalga obuna bo'lmagan!")
                print("   Bot kirishni blokleydi.")
                for ch in not_subscribed:
                    print(f"     • {ch}")
            print("="*70)
            
        except ValueError:
            print("❌ Noto'g'ri User ID!")
    
    await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_current_channels())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test bekor qilindi")
    except Exception as e:
        print(f"\n\n❌ Xato: {e}")
