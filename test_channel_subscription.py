#!/usr/bin/env python3
"""
Test script to check if a user is subscribed to Telegram channels
"""
import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN topilmadi .env faylida!")
    exit(1)

bot = Bot(BOT_TOKEN)


async def check_user_subscription(user_id: int, channel: str):
    """Check if user is subscribed to a channel"""
    try:
        # Normalize channel format
        chat_ref = channel.strip()
        
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
        
        # Check membership
        print(f"🔍 Checking: {channel} (normalized to: {chat_ref})")
        member = await bot.get_chat_member(chat_ref, user_id)
        
        status = member.status
        if status in ("member", "administrator", "creator"):
            print(f"   ✅ OBUNA BO'LGAN (status: {status})")
            return True
        else:
            print(f"   ❌ OBUNA BO'LMAGAN (status: {status})")
            return False
            
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"   ⚠️  XATO: {error_msg}")
        return False


async def test_subscription():
    print("="*70)
    print("TELEGRAM KANAL OBUNA TEKSHIRUVI")
    print("="*70)
    
    # Get user ID to test
    print("\nIltimos, tekshirmoqchi bo'lgan foydalanuvchi ID'sini kiriting:")
    print("(Telegram'da @userinfobot orqali ID olishingiz mumkin)")
    user_id_str = input("User ID: ").strip()
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        print("❌ Noto'g'ri format! Faqat raqamlar kiriting.")
        return
    
    print(f"\n👤 Foydalanuvchi ID: {user_id}")
    
    # Get channels to test
    print("\nTekshirmoqchi bo'lgan kanallarni kiriting (har birini alohida qatorda):")
    print("Formatlar: @username, -1001234567890, https://t.me/username")
    print("Tugatish uchun bo'sh qator qoldiring.\n")
    
    channels = []
    while True:
        channel = input(f"Kanal #{len(channels)+1}: ").strip()
        if not channel:
            break
        channels.append(channel)
    
    if not channels:
        print("❌ Hech qanday kanal kiritilmadi!")
        return
    
    print("\n" + "="*70)
    print(f"NATIJALAR (Jami: {len(channels)} ta kanal)")
    print("="*70 + "\n")
    
    subscribed = []
    not_subscribed = []
    errors = []
    
    for i, channel in enumerate(channels, 1):
        print(f"[{i}/{len(channels)}] {channel}")
        result = await check_user_subscription(user_id, channel)
        print()
        
        if result is True:
            subscribed.append(channel)
        elif result is False:
            not_subscribed.append(channel)
        else:
            errors.append(channel)
    
    print("="*70)
    print("XULOSA")
    print("="*70)
    print(f"✅ Obuna bo'lgan:     {len(subscribed)}/{len(channels)}")
    print(f"❌ Obuna bo'lmagan:   {len(not_subscribed)}/{len(channels)}")
    print(f"⚠️  Xato bergan:      {len(errors)}/{len(channels)}")
    
    if subscribed:
        print("\n✅ Obuna bo'lgan kanallar:")
        for ch in subscribed:
            print(f"   • {ch}")
    
    if not_subscribed:
        print("\n❌ Obuna bo'lmagan kanallar:")
        for ch in not_subscribed:
            print(f"   • {ch}")
    
    if errors:
        print("\n⚠️  Xato bergan kanallar:")
        for ch in errors:
            print(f"   • {ch}")
    
    print("\n" + "="*70)
    
    # Close bot session
    await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_subscription())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test bekor qilindi (Ctrl+C)")
    except Exception as e:
        print(f"\n\n❌ Kutilmagan xato: {e}")
