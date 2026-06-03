# Bugfix Requirements Document

## Introduction

This document addresses a critical user experience bug in the Telegram bot's subscription verification logic. Currently, the bot displays both Telegram and YouTube channel subscription links to users but only verifies Telegram channel subscriptions. This creates confusion and a false perception that YouTube subscription verification is required when it technically cannot be enforced. The fix will clarify the messaging to accurately reflect what is actually being verified (Telegram channels only) while still displaying YouTube links as optional information for users.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN user starts the bot without being subscribed to all Telegram channels THEN the system displays the message "📣 Botdan foydalanish uchun quyidagi Telegram va YouTube kanallarimizga obuna bo'ling" which implies both Telegram AND YouTube subscriptions are mandatory

1.2 WHEN user presses ✅ Tekshirish button and is not subscribed to all Telegram channels THEN the system displays "⚠️ Hali barcha Telegram kanallarimizga obuna bo'lmagansiz" which correctly mentions only Telegram but contradicts the initial message

1.3 WHEN the guard_common() function blocks user access THEN the system displays "🔒 Obuna talab qilinadi" followed by "Quyidagi Telegram va YouTube kanallarimizga a'zo bo'ling" which again implies both are mandatory

1.4 WHEN user subscribes to all required Telegram channels but not YouTube THEN the system allows full bot access, revealing that YouTube subscriptions were never actually verified

### Expected Behavior (Correct)

2.1 WHEN user starts the bot without being subscribed to all Telegram channels THEN the system SHALL display a clear message "📣 Botdan foydalanish uchun quyidagi Telegram va YouTube kanallarimizga obuna bo'ling. Tayyor bo'lsangiz, ✅ Tekshirish tugmasini bosing." that presents both channel types but only enforces Telegram verification

2.2 WHEN user presses ✅ Tekshirish button and is not subscribed to all Telegram channels THEN the system SHALL display "⚠️ Hali barcha Telegram kanallarimizga obuna bo'lmagansiz. Quyidagilarga obuna bo'ling va qayta tekshiring." which accurately indicates only Telegram channels are being verified while still showing both Telegram and YouTube channel links

2.3 WHEN the guard_common() function detects missing Telegram subscriptions THEN the system SHALL display a message that clearly indicates only Telegram channels are verified: "🔒 Obuna talab qilinadi - Quyidagi Telegram va YouTube kanallarimizga a'zo bo'ling, so'ng ✅ Tekshirish tugmasini bosing."

2.4 WHEN user subscribes to all required Telegram channels (regardless of YouTube subscription status) THEN the system SHALL immediately grant full bot access without requesting or verifying YouTube subscriptions

2.5 WHEN check_subscription() function is called THEN the system SHALL skip all channels starting with "yt:" prefix and return only Telegram channels that user is not subscribed to

### Unchanged Behavior (Regression Prevention)

3.1 WHEN user is subscribed to all Telegram channels THEN the system SHALL CONTINUE TO allow immediate bot access regardless of YouTube subscription status

3.2 WHEN check_subscription() encounters a YouTube channel (prefixed with "yt:") THEN the system SHALL CONTINUE TO skip verification for that channel and log the skip action

3.3 WHEN displaying channel subscription buttons THEN the system SHALL CONTINUE TO show both Telegram channels (📢 prefix) and YouTube channels (▶️ YouTube: prefix) in the inline keyboard

3.4 WHEN processing Telegram channel formats (@username, numeric IDs, URLs) THEN the system SHALL CONTINUE TO normalize and verify them correctly using bot.get_chat_member()

3.5 WHEN admin manages required channels THEN the system SHALL CONTINUE TO allow adding, removing, and listing both Telegram and YouTube channels

3.6 WHEN referral rewards are granted THEN the system SHALL CONTINUE TO trigger only after user completes both Telegram channel subscription AND phone verification
