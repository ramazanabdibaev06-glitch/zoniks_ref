#!/usr/bin/env python3
"""
Script to fix incorrect channel entries in the database.
This will:
1. Remove @vsyuqvio_bot (it's a bot, not a channel)
2. Remove @yt:@bekwiner (incorrect format)
3. Add yt:@bekwiner (correct YouTube format)
"""
import sqlite3

DB_NAME = "bot_data.db"

def fix_channels():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("Current channels:")
    cursor.execute("SELECT username FROM required_channels")
    for row in cursor.fetchall():
        print(f"  - {row[0]}")
    
    print("\nRemoving incorrect entries...")
    
    # Remove bot entry
    cursor.execute("DELETE FROM required_channels WHERE username = ?", ("@vsyuqvio_bot",))
    print("  ✓ Removed @vsyuqvio_bot (bot)")
    
    # Remove incorrect YouTube format
    cursor.execute("DELETE FROM required_channels WHERE username LIKE ?", ("%@yt:%",))
    print("  ✓ Removed @yt:@bekwiner (incorrect format)")
    
    # Add correct YouTube format
    cursor.execute("INSERT OR IGNORE INTO required_channels(username) VALUES(?)", ("yt:@bekwiner",))
    print("  ✓ Added yt:@bekwiner (correct format)")
    
    conn.commit()
    
    print("\nUpdated channels:")
    cursor.execute("SELECT username FROM required_channels")
    for row in cursor.fetchall():
        print(f"  - {row[0]}")
    
    conn.close()
    print("\n✅ Database updated successfully!")

if __name__ == "__main__":
    fix_channels()
