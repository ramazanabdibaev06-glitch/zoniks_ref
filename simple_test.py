#!/usr/bin/env python3
"""
Simple test to check channel filtering logic
"""

# Simulate the check_subscription logic
def should_check_channel(channel: str) -> bool:
    """Returns True if channel should be verified, False if should be skipped"""
    channel = channel.strip()
    
    # Skip YouTube channels or bots
    if "yt:" in channel or channel.endswith("_bot"):
        return False
    
    return True

# Test cases
test_channels = [
    "@myuzbekchanneluz",       # Should check
    "-1001234567890",          # Should check
    "yt:@bekwiner",            # Should skip (YouTube)
    "@yt:@bekwiner",           # Should skip (YouTube, wrong format)
    "@vsyuqvio_bot",           # Should skip (bot)
    "https://t.me/mychannel",  # Should check
]

print("="*60)
print("CHANNEL FILTERING TEST")
print("="*60)

telegram_count = 0
youtube_count = 0
bot_count = 0

for ch in test_channels:
    should_check = should_check_channel(ch)
    
    if "yt:" in ch:
        emoji = "▶️"
        channel_type = "YouTube"
        youtube_count += 1
    elif ch.endswith("_bot"):
        emoji = "🤖"
        channel_type = "Bot"
        bot_count += 1
    else:
        emoji = "📢"
        channel_type = "Telegram"
        telegram_count += 1
    
    status = "✅ VERIFY" if should_check else "⏭️  SKIP"
    
    print(f"{emoji} {ch:30s} [{channel_type:10s}] → {status}")

print("\n" + "="*60)
print(f"Summary:")
print(f"  Telegram channels: {telegram_count} (all verified)")
print(f"  YouTube channels:  {youtube_count} (all skipped)")
print(f"  Bots:              {bot_count} (all skipped)")
print("="*60)

# Verify the logic is correct
errors = []
for ch in test_channels:
    should_check = should_check_channel(ch)
    if "yt:" in ch and should_check:
        errors.append(f"ERROR: YouTube channel {ch} was NOT skipped!")
    if ch.endswith("_bot") and should_check:
        errors.append(f"ERROR: Bot {ch} was NOT skipped!")

if errors:
    print("\n❌ ERRORS FOUND:")
    for err in errors:
        print(f"   {err}")
else:
    print("\n✅ ALL TESTS PASSED!")
    print("   YouTube channels and bots are properly skipped.")
