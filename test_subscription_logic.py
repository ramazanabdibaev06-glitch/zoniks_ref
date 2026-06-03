#!/usr/bin/env python3
"""
Test script to verify subscription checking logic
"""
import asyncio
from main import check_subscription, _get_required_channels

async def test_logic():
    print("="*60)
    print("SUBSCRIPTION LOGIC TEST")
    print("="*60)
    
    # Get current channels
    channels = await _get_required_channels()
    print(f"\n📋 Current required channels ({len(channels)}):")
    for ch in channels:
        if "yt:" in ch:
            print(f"  ▶️  {ch} (YouTube - DISPLAY ONLY)")
        else:
            print(f"  📢 {ch} (Telegram - VERIFIED)")
    
    # Test with a fake user ID
    test_user_id = 999999999
    print(f"\n🔍 Testing subscription check for user {test_user_id}...")
    print("   (This will fail for Telegram channels, but YouTube should be skipped)")
    
    not_subscribed = await check_subscription(test_user_id)
    
    print(f"\n📊 Results:")
    print(f"   Total channels: {len(channels)}")
    print(f"   Not subscribed to: {len(not_subscribed)}")
    print(f"   YouTube channels skipped: {len([c for c in channels if 'yt:' in c])}")
    
    if not_subscribed:
        print(f"\n❌ User is NOT subscribed to:")
        for ch in not_subscribed:
            print(f"     - {ch}")
    else:
        print(f"\n✅ User IS subscribed to all required Telegram channels!")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    
    # Verify YouTube channels were skipped
    youtube_in_result = [ch for ch in not_subscribed if "yt:" in ch]
    if youtube_in_result:
        print("\n⚠️  WARNING: YouTube channels were NOT skipped!")
        print(f"   Found in results: {youtube_in_result}")
    else:
        print("\n✅ SUCCESS: YouTube channels were properly skipped!")

if __name__ == "__main__":
    asyncio.run(test_logic())
