#!/usr/bin/env python3
import asyncio
import os
import sqlite3
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)

async def main():
    user_id = 6320742043
    
    print("="*70)
    print(f"OBUNA TEKSHIRUVI - User ID: {user_id}")
    print("="*70)
    
    # Get channels from database
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM required_channels")
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"\n📋 Database-da {len(channels)} ta kanal:\n")
    
    telegram_channels = []
    for ch in channels:
        if "yt:" in ch:
            print(f"   ▶️  {ch} (YouTube - SKIP)")
        else:
            print(f"   📢 {ch} (Telegram - TEKSHIRILADI)")
            telegram_channels.append(ch)
    
    print(f"\n🔍 {len(telegram_channels)} ta Telegram kanalini tekshiryapman...\n")
    
    not_subscribed = []
    
    for ch in telegram_channels:
        try:
            # Normalize channel
            chat_ref = ch.strip()
            
            # Handle URLs
            if chat_ref.startswith(("http://", "https://", "tg://")):
                if "t.me/" in chat_ref:
                    after = chat_ref.split("t.me/", 1)[1]
                    slug = after.split("?")[0].strip().strip("/")
                    slug = slug.lstrip("@")
                    if slug:
                        chat_ref = f"@{slug}"
            
            # Handle numeric IDs
            elif chat_ref.lstrip("-").isdigit():
                chat_ref = int(chat_ref)
            
            print(f"📢 Kanal: {ch}")
            print(f"   Normalized: {chat_ref}")
            
            member = await bot.get_chat_member(chat_ref, user_id)
            
            if member.status in ("member", "administrator", "creator"):
                print(f"   ✅ OBUNA BO'LGAN (status: {member.status})\n")
            else:
                print(f"   ❌ OBUNA BO'LMAGAN (status: {member.status})\n")
                not_subscribed.append(ch)
                
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"   ⚠️  XATO: {error_msg}\n")
            not_subscribed.append(ch)
    
    print("="*70)
    print("NATIJA")
    print("="*70)
    
    if not not_subscribed:
        print("✅ BARCHA TELEGRAM KANALLARIGA OBUNA BO'LGAN!")
        print("   Bot foydalanuvchini kiritadi.")
    else:
        print(f"❌ {len(not_subscribed)} TA KANALGA OBUNA BO'LMAGAN!")
        print("   Bot foydalanuvchini bloklaydi.")
        print("\n   Obuna bo'lmagan kanallar:")
        for ch in not_subscribed:
            print(f"     • {ch}")
    
    print("="*70)
    
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
