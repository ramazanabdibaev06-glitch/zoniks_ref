#!/usr/bin/env python3
"""
Test URL building logic for channel buttons
"""

def build_telegram_url(ch: str) -> str:
    """Build Telegram URL from channel identifier"""
    # Check if already a full URL
    if ch.startswith(("http://", "https://", "tg://")):
        return ch
    else:
        # Build URL from username or ID
        return f"https://t.me/{ch.lstrip('@')}"

# Test cases
test_channels = [
    "@test_kanal121",
    "test_kanal121",
    "https://t.me/test_kanal121",
    "-1001234567890",
]

print("="*70)
print("URL BUILDING TEST")
print("="*70)

for ch in test_channels:
    url = build_telegram_url(ch)
    status = "✅" if url.count("https://t.me/") == 1 else "❌"
    print(f"\n{status} Input:  {ch}")
    print(f"   Output: {url}")

print("\n" + "="*70)
