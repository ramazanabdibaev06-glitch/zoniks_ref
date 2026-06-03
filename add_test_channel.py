#!/usr/bin/env python3
"""
Add a test Telegram channel to the database
"""
import sqlite3
import sys

DB_NAME = "bot_data.db"

def add_channel(channel: str):
    """Add channel to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Normalize channel format
    channel = channel.strip()
    
    # Skip if it's YouTube
    if "yt:" in channel or "youtube.com" in channel or "youtu.be" in channel:
        print(f"⚠️  Bu YouTube kanal - qo'shilmaydi: {channel}")
        print("   YouTube kanallari faqat tavsiya sifatida ko'rsatiladi.")
        return False
    
    # Add @ for usernames
    if not channel.startswith(("@", "-", "http")):
        channel = "@" + channel
    
    try:
        cursor.execute("INSERT INTO required_channels(username) VALUES(?)", (channel,))
        conn.commit()
        print(f"✅ Kanal qo'shildi: {channel}")
        return True
    except sqlite3.IntegrityError:
        print(f"⚠️  Kanal allaqachon mavjud: {channel}")
        return False
    except Exception as e:
        print(f"❌ Xato: {e}")
        return False
    finally:
        conn.close()


def list_channels():
    """List all channels"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM required_channels ORDER BY username")
    channels = cursor.fetchall()
    conn.close()
    
    if not channels:
        print("📋 Hozirda hech qanday kanal yo'q.")
        return
    
    print(f"\n📋 Hozirgi kanallar ({len(channels)} ta):")
    telegram_count = 0
    youtube_count = 0
    
    for ch in channels:
        if "yt:" in ch[0]:
            print(f"   ▶️  {ch[0]} (YouTube - skip)")
            youtube_count += 1
        else:
            print(f"   📢 {ch[0]} (Telegram - verify)")
            telegram_count += 1
    
    print(f"\nJami: {telegram_count} Telegram, {youtube_count} YouTube")


if __name__ == "__main__":
    print("="*70)
    print("TELEGRAM KANAL QO'SHISH")
    print("="*70)
    
    if len(sys.argv) > 1:
        # Channel provided as argument
        channel = " ".join(sys.argv[1:])
        add_channel(channel)
    else:
        # Interactive mode
        print("\nQo'shmoqchi bo'lgan Telegram kanalini kiriting:")
        print("Formatlar:")
        print("  • @username")
        print("  • -1001234567890")
        print("  • https://t.me/username")
        print()
        
        channel = input("Kanal: ").strip()
        
        if channel:
            add_channel(channel)
        else:
            print("❌ Kanal kiritilmadi!")
    
    # Show current channels
    list_channels()
    
    print("\n" + "="*70)
