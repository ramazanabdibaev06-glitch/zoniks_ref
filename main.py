# main.py — Yangilangan FreeFire bot (Captchasiz, yangi tugmalar)
import asyncio
import os
import time
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand
)
from dotenv import load_dotenv

from config import OWNER_ID, OWNER2_ID, REQUIRED_CHANNELS_DEFAULT
from database import (
    init_db, add_user, get_user, add_almaz, get_leaderboard,
    get_ref_by, set_ref_by_if_empty, is_verified, set_verified, set_phone_verified,
    list_admins, add_admin, remove_admin, is_admin,
    get_dynamic_text, update_dynamic_text,
    list_required_channels, add_required_channel, remove_required_channel, required_channels_count,
    set_suspension, get_suspension_remaining,
    create_referral, mark_referral_verified, count_verified_referrals, count_all_referrals,
    get_top_referrers_today,
    create_withdraw_request, get_withdraw_request, update_withdraw_status,
    get_withdraw_stats,
    add_withdraw_notification, get_withdraw_notifications,
    backup_database,
    get_setting, set_setting, delete_setting,
)

PROOF_CHANNEL_SETTING_KEY = "proof_channel_id"
PROOF_CHANNEL_BUTTON = "proof_channel_link"

# ==== Logging ====
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
log = logging.getLogger("bot")

# ==== ENV / BOT ====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env dan topilmadi")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def normalize_proof_channel_value(raw: str) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    lowered = value.lower()
    if lowered in {"0", "none", "null", "off"}:
        return None

    if value.startswith(("http://", "https://", "tg://")):
        marker = "t.me/"
        if marker in value:
            after = value.split(marker, 1)[1]
            slug = after.split("?")[0].strip().strip("/")
            slug = slug.lstrip("@")
            if not slug:
                raise ValueError("Kanal username aniqlanmadi.")
            return f"@{slug}"
        raise ValueError("Faqat https://t.me/ ko'rinishidagi havolalar qabul qilinadi.")

    if value.startswith("@"):
        username = value[1:].strip()
        if not username:
            raise ValueError("Username bo'sh bo'lishi mumkin emas.")
        return f"@{username}"

    try:
        int(value)
        return value
    except ValueError:
        raise ValueError("Kanal ID faqat raqamlardan iborat bo'lishi kerak yoki @username ishlating.")


def resolve_proof_chat_id(value: str | None) -> str | int | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    
    # Normalize HTTPS URLs to @username
    if value.startswith(("http://", "https://", "tg://")):
        marker = "t.me/"
        if marker in value:
            after = value.split(marker, 1)[1]
            slug = after.split("?")[0].strip().strip("/")
            slug = slug.lstrip("@")
            if slug:
                value = f"@{slug}"
    
    if value.startswith("@"):
        return value
    try:
        return int(value)
    except ValueError:
        return None


def build_proof_channel_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("@"):
        return f"https://t.me/{value[1:]}"
    return None


async def get_proof_channel_value() -> str | None:
    value = await get_setting(PROOF_CHANNEL_SETTING_KEY)
    if not value:
        return None
    value = value.strip()
    return value or None


async def build_proof_button() -> InlineKeyboardButton:
    channel_value = await get_proof_channel_value()
    if not channel_value:
        return InlineKeyboardButton(text="📜 Isbotlar", callback_data=PROOF_CHANNEL_BUTTON)
    url = build_proof_channel_url(channel_value)
    if url:
        return InlineKeyboardButton(text="📜 Isbotlar", url=url)
    return InlineKeyboardButton(text="📜 Isbotlar", callback_data=PROOF_CHANNEL_BUTTON)


async def build_proof_keyboard() -> Optional[InlineKeyboardMarkup]:
    button = await build_proof_button()
    if not button:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


# =================== STATES ===================
class VerifyStates(StatesGroup):
    PHONE = State()


class TextEdit(StatesGroup):
    new_text = State()
    section = State()


class Broadcast(StatesGroup):
    WAITING = State()


class ChanManage(StatesGroup):
    ADD = State()
    REMOVE = State()


class AdminManage(StatesGroup):
    ADD = State()
    REMOVE = State()


class SearchUser(StatesGroup):
    WAIT = State()


class WithdrawStates(StatesGroup):
    WAITING_FF_ID = State()


class WithdrawEdit(StatesGroup):
    WAITING_TEXT = State()


class SuspensionInput(StatesGroup):
    WAIT = State()


class GiveAlmaz(StatesGroup):
    WAIT = State()


class ProofChannelSetup(StatesGroup):
    WAITING = State()


def format_user_short(name: str, username: Optional[str]) -> str:
    if username:
        return f"@{username}"
    return name


async def is_owner_or_admin(user_id: int) -> bool:
    # True if user is either owner (OWNER_ID or OWNER2_ID) or an admin
    if user_id == OWNER_ID or user_id == OWNER2_ID:
        return True
    return await is_admin(user_id)


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id == OWNER2_ID


async def get_referral_reward() -> int:
    v = await get_setting("referral_reward")
    try:
        return int(v)
    except:
        return 1


# =================== MENUS ===================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💎 Almaz Topish"), KeyboardButton(text="👤 Mening Profilim")],
        [KeyboardButton(text="🏅 Top Foydalanuvchilar"), KeyboardButton(text="🛒 Almaz Do'koni")],
        [KeyboardButton(text="📣 Yangiliklar & Bonuslar")],
    ], resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Foydalanuvchilar soni")],
        [KeyboardButton(text="📰 Reklama/Yangilik sozlash"), KeyboardButton(text="💰 Almaz sotib olish matni")],
        [KeyboardButton(text="📢 Reklama yuborish"), KeyboardButton(text="🔎 Foydalanuvchini topish")],
        [KeyboardButton(text="🧩 Majburiy kanallar"), KeyboardButton(text="🛡 Admin boshqaruvi")],
        [KeyboardButton(text="💎 Qo'lda almaz berish"), KeyboardButton(text="📈 Statistika")],
        [KeyboardButton(text="⏳ Tanaffus berish"), KeyboardButton(text="🔧 Referal almaz qiymati")],
        [KeyboardButton(text="📜 Isbotlar kanali")],
        [KeyboardButton(text="💾 Backup yaratish")],
        [KeyboardButton(text="⬅️ Chiqish")],
    ], resize_keyboard=True
)

back_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
    resize_keyboard=True
)


def sub_required_markup(channels: list[str]):
    """Show only channels that user is NOT subscribed to"""
    buttons = []
    for ch in channels:
        if ch.startswith("yt:"):
            # Handle YouTube channels
            if ch.startswith("yt:@"):
                yt_handle = ch.replace("yt:@", "")
                yt_url = f"https://www.youtube.com/@{yt_handle}"
            elif ch.startswith("yt:c:"):
                yt_channel = ch.replace("yt:c:", "")
                yt_url = f"https://www.youtube.com/c/{yt_channel}"
            elif ch.startswith("yt:u:"):
                yt_user = ch.replace("yt:u:", "")
                yt_url = f"https://www.youtube.com/user/{yt_user}"
            else:
                continue
            buttons.append([InlineKeyboardButton(text=f"▶️ YouTube: {ch[3:]}", url=yt_url)])
        else:
            # Handle Telegram channels
            # Check if already a full URL
            if ch.startswith(("http://", "https://", "tg://")):
                tg_url = ch
            else:
                # Build URL from username or ID
                tg_url = f"https://t.me/{ch.lstrip('@')}"
            buttons.append([InlineKeyboardButton(text=f"📢 {ch}", url=tg_url)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sub_required_markup_all(channels: list[str]):
    """Show ALL channels (both subscribed and not subscribed)"""
    buttons = []
    for ch in channels:
        if ch.startswith("yt:"):
            # Handle YouTube channels
            if ch.startswith("yt:@"):
                yt_handle = ch.replace("yt:@", "")
                yt_url = f"https://www.youtube.com/@{yt_handle}"
            elif ch.startswith("yt:c:"):
                yt_channel = ch.replace("yt:c:", "")
                yt_url = f"https://www.youtube.com/c/{yt_channel}"
            elif ch.startswith("yt:u:"):
                yt_user = ch.replace("yt:u:", "")
                yt_url = f"https://www.youtube.com/user/{yt_user}"
            else:
                continue
            buttons.append([InlineKeyboardButton(text=f"▶️ YouTube: {ch[3:]}", url=yt_url)])
        else:
            # Handle Telegram channels
            # Check if already a full URL
            if ch.startswith(("http://", "https://", "tg://")):
                tg_url = ch
            else:
                # Build URL from username or ID
                tg_url = f"https://t.me/{ch.lstrip('@')}"
            buttons.append([InlineKeyboardButton(text=f"📢 {ch}", url=tg_url)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================ HELPERS ================
async def setup_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="admin", description="Admin panel"),
    ])


async def _get_required_channels():
    current = await list_required_channels()
    if not current:
        for ch in REQUIRED_CHANNELS_DEFAULT:
            try:
                await add_required_channel(ch)
            except Exception:
                pass
        current = await list_required_channels()
    return current


async def check_subscription(user_id: int) -> list[str]:
    """
    Check subscription status for Telegram channels ONLY.
    YouTube channels (starting with "yt:") are completely ignored and never verified.
    Returns list of Telegram channels user is NOT subscribed to.
    """
    not_sub = []
    channels = await _get_required_channels()
    log.debug(f"Checking subscription for user {user_id}. Required channels: {channels}")
    
    for ch in channels:
        chat_ref: Optional[str | int] = ch.strip()
        
        # Skip YouTube channels - they cannot be verified and are displayed as optional only
        # Check for both "yt:" and "@yt:" formats (incorrect database entries)
        if isinstance(chat_ref, str) and ("yt:" in chat_ref or chat_ref.endswith("_bot")):
            log.info(f"Skipping YouTube channel or bot (not verifiable): {ch}")
            continue
        
        try:
            # Normalize channels to proper format
            original_ref = chat_ref
            
            # Handle URLs
            if isinstance(chat_ref, str) and chat_ref.startswith(("http://", "https://", "tg://")):
                if "t.me/" in chat_ref:
                    # Extract from URL
                    after = chat_ref.split("t.me/", 1)[1]
                    slug = after.split("?")[0].strip().strip("/")
                    slug = slug.lstrip("@")
                    if slug:
                        chat_ref = f"@{slug}"
                        log.debug(f"Normalized URL {original_ref} to {chat_ref}")
                    else:
                        log.warning(f"Could not extract username from URL: {original_ref}")
                        not_sub.append(ch)
                        continue
                else:
                    log.warning(f"Unsupported URL format: {original_ref}")
                    not_sub.append(ch)
                    continue
            
            # Handle numeric IDs (including negative ones for supergroups)
            elif isinstance(chat_ref, str) and (chat_ref.lstrip("-").isdigit()):
                try:
                    chat_ref = int(chat_ref)
                    log.debug(f"Converted ID string {original_ref} to integer {chat_ref}")
                except ValueError:
                    log.warning(f"Could not convert to integer: {original_ref}")
                    not_sub.append(ch)
                    continue
            
            # @username format - already correct
            elif isinstance(chat_ref, str) and chat_ref.startswith("@"):
                log.debug(f"Channel is already in @username format: {chat_ref}")
            
            # Other format - try as-is
            else:
                if isinstance(chat_ref, str) and chat_ref:
                    # Could be numeric string without @
                    try:
                        chat_ref = int(chat_ref)
                        log.debug(f"Converted {original_ref} to integer ID")
                    except ValueError:
                        log.warning(f"Unknown channel format: {original_ref}")
                        not_sub.append(ch)
                        continue
            
            # Now check membership
            log.debug(f"Checking user {user_id} membership in {chat_ref} (type: {type(chat_ref).__name__})")
            member = await bot.get_chat_member(chat_ref, user_id)
            
            if member.status in ("member", "administrator", "creator"):
                log.info(f"✓ User {user_id} IS subscribed to {original_ref} (status: {member.status})")
            else:
                log.warning(f"✗ User {user_id} is NOT subscribed to {original_ref} (status: {member.status})")
                not_sub.append(ch)
                
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log.error(f"ERROR checking {ch} for user {user_id}: {error_msg}")
            not_sub.append(ch)
    
    log.info(f"User {user_id} subscription check complete. Not subscribed to {len(not_sub)} channels: {not_sub}")
    return not_sub
    
    return not_sub


async def guard_common(message: Message) -> bool:
    if message.chat.type != "private":
        return False

    remain = await get_suspension_remaining(message.from_user.id)
    if remain > 0:
        await message.answer(
            "😴 Siz hozircha tanaffusdasiz.\n"
            f"⏰ {remain} soniyadan so'ng bot qayta faollashadi.",
            parse_mode="HTML"
        )
        return True

    # Check ONLY Telegram channels (YouTube is displayed but never verified)
    not_sub = await check_subscription(message.from_user.id)
    
    # If all Telegram channels are subscribed, allow through immediately
    if not not_sub:
        return False
    
    # User is missing some Telegram channels - show blocking message with ALL channels
    all_channels = await _get_required_channels()
    await message.answer(
        "🔒 <b>Obuna talab qilinadi</b>\n\n"
        "Quyidagi Telegram kanallarimizga obuna bo'ling (YouTube tavsiya etiladi), so'ng <b>✅ Tekshirish</b> tugmasini bosing.",
        parse_mode="HTML", reply_markup=sub_required_markup_all(all_channels)
    )
    return True


async def update_withdraw_admin_messages(request_id: int, status_label: str):
    notifications = await get_withdraw_notifications(request_id)
    req = await get_withdraw_request(request_id)
    if not req:
        return
    r_id, user_id, amount, ff_id, status, created_at, processed_at, processed_by, note = req
    user = await get_user(user_id)
    username = user[1] if user else None
    almaz = user[3] if user and len(user) > 3 and user[3] is not None else 0
    refs = await count_verified_referrals(user_id)

    created_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(created_at or int(time.time())))
    processed_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(processed_at)) if processed_at else "—"
    note_part = f"\n📝 Izoh: {note}" if note else ""

    base_text = (
        "🧾 <b>Almaz yechish so'rovi</b>\n\n"
        f"👤 Foydalanuvchi: @{username or 'Anonim'} (ID: <code>{user_id}</code>)\n"
        f"💎 Joriy balans: <b>{almaz} Almaz</b>\n"
        f"🔥 Yechmoqchi bo'lgan miqdor: <b>{amount} Almaz</b>\n"
        f"👥 Umumiy tasdiqlangan takliflar: <b>{refs}</b>\n"
        f"🎮 Free Fire ID: <code>{ff_id}</code>\n"
        f"🕒 So'rov vaqti: {created_str}\n"
        f"🕒 Qayta ishlangan: {processed_str}"
        f"{note_part}\n\n"
        f"{status_label}"
    )

    for chat_id, message_id in notifications:
        try:
            await bot.edit_message_text(
                base_text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
        except Exception as e:
            log.warning("withdraw msg edit failed: %s", e)


async def send_proof_receipt(request_id: int, user_id: int, amount: int, ff_id: Optional[str]):
    channel_value = await get_proof_channel_value()
    chat_id = resolve_proof_chat_id(channel_value)
    if not chat_id:
        return

    user = await get_user(user_id)
    username = user[1] if user else None
    mention = f"@{username}" if username else f"ID: {user_id}"
    verified_refs = await count_verified_referrals(user_id)
    ff_value = ff_id or "Ko'rsatilmagan"
    now = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime())

    text = (
        "✅ <b>Almaz yechish tasdiqlandi</b>\n\n"
        f"👤 Foydalanuvchi: {mention} (ID: <code>{user_id}</code>)\n"
        f"🎮 Free Fire ID: <code>{ff_value}</code>\n"
        f"💎 Miqdor: <b>{amount} Almaz</b>\n"
        f"👥 Umumiy tasdiqlangan takliflari: <b>{verified_refs}</b>\n"
        f"🆔 So'rov ID: <code>{request_id}</code>\n"
        f"🕒 Tasdiqlangan vaqt: {now}"
    )

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as exc:
        log.warning("Isbotlar kanaliga yuborib bo'lmadi (%s): %s", channel_value, exc)


async def notify_admins_about_withdraw(request_id: int):
    req = await get_withdraw_request(request_id)
    if not req:
        return
    r_id, user_id, amount, ff_id, status, created_at, processed_at, processed_by, note = req
    user = await get_user(user_id)
    username = user[1] if user else None
    almaz = user[3] if user and len(user) > 3 and user[3] is not None else 0
    refs = await count_verified_referrals(user_id)
    created_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(created_at or int(time.time())))

    text = (
        "🧾 <b>Yangi almaz yechish so'rovi</b>\n\n"
        f"👤 Foydalanuvchi: @{username or 'Anonim'} (ID: <code>{user_id}</code>)\n"
        f"💎 Joriy balans: <b>{almaz} Almaz</b>\n"
        f"🔥 Yechmoqchi: <b>{amount} Almaz</b>\n"
        f"👥 Umumiy tasdiqlangan takliflar: <b>{refs}</b>\n"
        f"🎮 Free Fire ID: <code>{ff_id}</code>\n"
        f"🕒 So'rov vaqti: {created_str}\n\n"
        "Quyidagi tugmalar orqali so'rovni boshqaring 👇"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"wd_ok:{request_id}"),
                InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"wd_edit:{request_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"wd_reject:{request_id}"),
            ]
        ]
    )

    admin_ids = [OWNER_ID, OWNER2_ID]
    extra_admins = await list_admins()
    for uid, _ in extra_admins:
        if uid not in admin_ids:
            admin_ids.append(uid)

    for chat_id in admin_ids:
        try:
            msg = await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)
            await add_withdraw_notification(request_id, chat_id, msg.message_id)
        except Exception as e:
            log.warning("failed to send withdraw notify to %s: %s", chat_id, e)


# ============== CALLBACK: obunani qayta tekshirish ==============
@dp.callback_query(F.data == "check_subs")
async def recheck_subs(cb: CallbackQuery, state: FSMContext):
    from aiogram.exceptions import TelegramBadRequest
    
    # Check ONLY Telegram channels (YouTube is displayed but never verified)
    not_sub = await check_subscription(cb.from_user.id)
    
    # If all Telegram channels are subscribed
    if not not_sub:
        # Check if this is the first time user passed Telegram verification
        state_data = await state.get_data()
        youtube_check_done = state_data.get("youtube_check_done", False)
        
        if not youtube_check_done:
            # First time - show fake YouTube warning
            await state.update_data(youtube_check_done=True)
            all_channels = await _get_required_channels()
            try:
                await cb.message.edit_text(
                    "⚠️ Iltimos, YouTube kanallarimizga ham obuna bo'ling va qayta tekshiring.",
                    reply_markup=sub_required_markup_all(all_channels)
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise
            await cb.answer("⚠️ YouTube kanalimizga obuna bo'ling!", show_alert=True)
            return
        
        # Second time - allow access
        try:
            await cb.message.edit_text("✅ Barcha majburiy kanallarimizga obuna bo'ldingiz! Davom etamiz…")
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        await cb.answer("✅ Tabriklaymiz!")
        await cmd_start(cb.message, state)
        return
    
    # User still hasn't subscribed to all Telegram channels - show all channels
    all_channels = await _get_required_channels()
    try:
        await cb.message.edit_text(
            "⚠️ Hali barcha majburiy kanallarimizga obuna bo'lmagansiz.\n"
            "Quyidagi kanallariga obuna bo'ling va qayta tekshiring.",
            reply_markup=sub_required_markup_all(all_channels)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    # Always answer the callback to stop the loading spinner (popup alert gives feedback)
    await cb.answer(
        "❌ Siz hali barcha Telegram kanallarga obuna bo'lmagansiz!",
        show_alert=True
    )


# ============== /start ==============
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id

    ref_id = None
    payload = (message.text or "").replace("/start", "", 1).strip()

    state_data = await state.get_data()
    saved_ref_id = state_data.get("referral_id")

    if payload:
        first = payload.split()[0]
        if first.startswith("ref_"):
            cleaned = first.split("\n")[0].split("?")[0].split("@")[0]
            try:
                ref_id = int(cleaned.replace("ref_", ""))
            except:
                ref_id = None
        elif first.isdigit():
            ref_id = int(first)

    if ref_id == user_id:
        ref_id = None

    if ref_id is None and saved_ref_id:
        ref_id = saved_ref_id

    if ref_id:
        await state.update_data(referral_id=ref_id)

    existing_before = await get_user(user_id)
    is_new_user = existing_before is None

    if is_new_user:
        await add_user(user_id, message.from_user.username, ref_id)
        
        if ref_id:
            actual_ref = await get_ref_by(user_id)
            if actual_ref and actual_ref == ref_id:
                try:
                    created = await create_referral(ref_id, user_id)
                    # only notify inviter when a new referral record was actually created
                    if created:
                        try:
                            invited_label = format_user_short(
                                message.from_user.first_name,
                                message.from_user.username
                            )
                            reward = await get_referral_reward()

                            await bot.send_message(
                                ref_id,
                                "🧲 <b>A’lo! Yangi foydalanuvchi jalb qilindi</b>\n\n"
                                f"🎮 Siz taklif qilgan <b>{invited_label}</b> botga muvaffaqiyatli qo‘shildi.\n\n"
                                "⏳ Endi faqat <b>2 ta qadam</b> qoldi:\n"
                                "• Kanalga a’zo bo‘lish\n"
                                "• Telefon raqamni tasdiqlash\n\n"
                                f"💎 Ushbu jarayon yakunlangach, siz <b>{reward} Almaz</b>ga ega bo‘lasiz.\n"
                                "⚡ Do‘stlaringiz harakati — sizning foydangiz!",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            log.warning("Referral 1-xabar error: %s", e)
                except Exception as e:
                    log.warning("Referral creation error: %s", e)
    else:
        await add_user(user_id, message.from_user.username, None)

    # Check only Telegram channels (YouTube is displayed but never verified)
    not_sub = await check_subscription(user_id)
    
    if not_sub:
        all_channels = await _get_required_channels()
        await message.answer(
            "📣 Botdan foydalanish uchun quyidagi kanallarimizga obuna bo'ling \n"
            "Tayyor bo'lsangiz, <b>✅ Tekshirish</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=sub_required_markup_all(all_channels),
        )
        return

    current_state = await state.get_state()
    if current_state == VerifyStates.PHONE.state:
        await message.answer(
            "📱 Iltimos, telefon raqamingizni ulashing.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text='📱 Kontaktni ulashish', request_contact=True)]],
                resize_keyboard=True
            )
        )
        return

    verified = await is_verified(user_id)
    if not verified:
        await state.set_state(VerifyStates.PHONE)
        await message.answer(
            "📞 Davom etish uchun telefon raqamingizni tasdiqlang.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📱 Kontaktni ulashish", request_contact=True)],
                    [KeyboardButton(text="⬅️ Orqaga")]
                ],
                resize_keyboard=True
            ),
        )
        return

    await state.clear()
    
    await bot.send_message(
    chat_id=message.chat.id,
    text=(
         f"🎉 <b>Tabriklaymiz, {message.from_user.first_name}!</b>\n\n"
        "✅ Siz barcha tekshiruvlardan muvaffaqiyatli o‘tdingiz.\n"
        "🚀 Endi botning barcha imkoniyatlari siz uchun ochiq!\n\n"
        "💎 Almaz toping, profilingizni rivojlantiring va mukofotlarni qo‘lga kiriting.\n\n"
        "👇 Quyidagi menyudan boshlang:"
    ),
    reply_markup=main_menu,
    parse_mode="HTML"
    )


# ==================== TELEFON VERIFICATION ====================
@dp.message(VerifyStates.PHONE, F.content_type == ContentType.CONTACT)
async def phone_contact_ok(message: Message, state: FSMContext):
    user_id = message.from_user.id
    contact = message.contact

    if not contact or contact.user_id != user_id:
        await message.answer(
            "⚠️ Iltimos, faqat o'z raqamingizni ulashing.\n"
            "Pastdagi '📱 Kontaktni ulashish' tugmasidan foydalaning."
        )
        return

    phone = (contact.phone_number or "").strip()
    phone = phone if phone.startswith("+") else "+" + phone
    # Qabul qilinadigan davlatlar: O'zbekiston (+998), Qozog'iston (+77),
    # Qirg'iziston (+996), Tojikiston (+992)
    allowed_prefixes = ("+998", "+996", "+992", "+77")
    if not phone.startswith(allowed_prefixes):
        await message.answer(
            "❌ Faqat quyidagi davlat raqamlari qabul qilinadi:\n"
            "🇺🇿 O'zbekiston (+998)\n"
            "🇰🇿 Qozog'iston (+77)\n"
            "🇰🇬 Qirg'iziston (+996)\n"
            "🇹🇯 Tojikiston (+992)"
        )
        return

    await set_phone_verified(user_id, phone)
    await set_verified(user_id)

    ref_by = await get_ref_by(user_id)
    # ---------------- 2-XABAR + BONUS (faqat 1 marta) ----------------
    if ref_by and ref_by != user_id:
        # mark_referral_verified returns True only when we actually transitioned to verified
        did_verify = await mark_referral_verified(user_id)
        if did_verify:
            # Step 2: Add Almaz reward (with error handling)
            try:
                reward = await get_referral_reward()
                await add_almaz(ref_by, reward)
            except Exception as e:
                log.warning("Almaz qo'shishda xatolik: %s", e)

            # Step 3: Update rank (with error handling)
            try:
                await update_user_rank(ref_by, with_notification=True)
            except Exception as e:
                log.warning("Rank yangilashda xatolik: %s", e)

            # Step 4: Send 2nd message (SEPARATE try-catch to ensure it runs)
            try:
                total = await count_verified_referrals(ref_by)
                invited_label = format_user_short(
                    message.from_user.first_name or "Foydalanuvchi",
                    message.from_user.username
                )

                txt = (
                    "🎊 <b>Mukofot tayyor! Zo‘r ishladingiz</b>\n\n"
                    f"✅ Siz taklif qilgan <b>{invited_label}</b> barcha tekshiruvlardan muvaffaqiyatli o‘tdi.\n\n"
                    f"💎 Hisobingizga <b>{reward} Almaz</b> muvaffaqiyatli qo‘shildi!\n"
                    f"👥 Tasdiqlangan takliflaringiz soni: <b>{total}</b>\n\n"
                    "🔥 Qanchalik ko‘p do‘st taklif qilsangiz — shunchalik tez kuchli mukofotlarga yetasiz.\n"
                    "🚀 Davom eting, imkoniyat siz tomonda!"

                )

                await bot.send_message(ref_by, txt, parse_mode="HTML")
                log.info(f"✅ 2-xabar muvaffaqiyatli yuborildi: {ref_by}")

            except Exception as e:
                # Even if message fails, Almaz is already added
                log.error(f"❌ 2-xabar yuborishda xatolik (ref_by={ref_by}): {e}")

    await state.clear()

    await message.answer(
        "🎉 Telefon raqamingiz tasdiqlandi!\nEndi botdan to'liq foydalanishingiz mumkin.",
        reply_markup=main_menu
    )


@dp.message(VerifyStates.PHONE)
async def phone_contact_waiting(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Kontaktni ulashish", request_contact=True)],
            [KeyboardButton(text="⬅️ Orqaga")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "⚠️ Raqam qo'lda yozilmadi.\n"
        "Iltimos, pastdagi <b>📱 Kontaktni ulashish</b> tugmasidan foydalaning.",
        parse_mode="HTML", reply_markup=kb
    )


# ============== HELP ==============
@dp.message(Command("help"))
async def user_help(message: Message):
    await message.answer(
        "🆘 <b>Yordam</b>\n\n"
        "💎 Almaz Topish — Do'st chaqirish orqali Almaz\n"
        "👤 Mening Profilim — Profil va balans ma'lumotlari\n"
        "🏅 Top Foydalanuvchilar — Top 15 foydalanuvchi (Almaz bo'yicha)\n"
        "🛒 Almaz Do'koni — To'lov variantlari\n"
        "📣 Yangiliklar & Bonuslar — E'lonlar",
        parse_mode="HTML"
    )


# ============== Profil / Reyting / Almaz / News / Buy ==============
@dp.message(F.text == "👤 Mening Profilim")
async def show_profile(message: Message):
    if await guard_common(message):
        return
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username or "Noma'lum")
        user = await get_user(message.from_user.id)

    almaz = user[3] if len(user) > 3 and user[3] is not None else 0
    total_refs = await count_verified_referrals(message.from_user.id)
    username = user[1] or (message.from_user.username or "Anonim")

    text = (
        "👤 <b>Sizning profilingiz</b>\n\n"
        f"🆔 <b>Username:</b> @{username}\n"
        f"💎 <b>Balans:</b> {almaz} Almaz\n"
        f"🤝 <b>Faol takliflar:</b> {total_refs}\n\n"
        "📈 Bu yerda barcha yutuqlaringiz jamlangan.\n"
        "👇 Almazlaringizni hoziroq foydaga aylantiring!"
    )



    withdraw_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Almazni yechish", callback_data="withdraw_start")]
        ]
    )

    await message.answer(text, parse_mode="HTML", reply_markup=withdraw_kb)


@dp.message(F.text == "🏅 Top Foydalanuvchilar")
async def show_leaderboard_handler(message: Message):
    if await guard_common(message):
        return
    leaders = await get_leaderboard(limit=15)
    if not leaders:
        return await message.answer("📉 Hozircha reyting bo'sh.")
    text = "🏅 <b>Top 15 foydalanuvchi (Almaz bo'yicha)</b>\n\n"
    for i, (username, almaz) in enumerate(leaders[:15], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "⭐"
        text += f"{medal} @{(username or 'Anonim')} — 💎 {almaz}\n"
    proof_kb = await build_proof_keyboard()
    await message.answer(text, parse_mode="HTML", reply_markup=proof_kb)


@dp.callback_query(F.data == PROOF_CHANNEL_BUTTON)
async def proof_channel_button_handler(cb: CallbackQuery):
    channel_value = await get_proof_channel_value()
    if not channel_value:
        await cb.answer("❌ Isbotlar kanali hali sozlanmagan.", show_alert=True)
        return

    url = build_proof_channel_url(channel_value)
    if url:
        await cb.message.answer(f"📜 Isbotlar kanali: {url}")
        await cb.answer("🔗 Havola yuborildi.", show_alert=True)
        return

    await cb.answer("ℹ️ Kanal maxfiy formatda saqlangan. Havola mavjud emas.", show_alert=True)


@dp.message(F.text == "💎 Almaz Topish")
async def earn_almaz(message: Message):
    if await guard_common(message):
        return

    me = await bot.get_me()
    bot_username = me.username
    user_id = message.from_user.id
    reward = await get_referral_reward()

    html_text = (
        "🎯 <b>Almaz Topish — tez, bepul va samarali</b>\n\n"
        "💎 Bu bo‘limda siz hech qanday sarmoyasiz almaz yig‘asiz.\n"
        "Faqat do‘stlaringizni taklif qiling — qolganini tizim bajaradi.\n\n"

        "⚙️ <b>Jarayon juda oddiy:</b>\n"
        f"Do‘st → Bot → Tasdiq → Sizga <b>{reward} Almaz</b> 💎\n\n"

        "🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n"
        f"https://t.me/{bot_username}?start=ref_{user_id}\n\n"

        "🔥 Ko‘proq do‘st = ko‘proq kuch.\n"
        "Bugunoq boshlang va farqni his qiling!"

    )

    plain_text = (
        f"💎 Almaz Topish — eng tez yo'l!\n\n"
        f"Free Fire'da kuchli bo'lishni xohlaysizmi? 🔥\n"
        f"Qimmat skinlar, elita pass va itemlarga bepul ega bo'lish imkoniyatini qo'ldan boy bermang! 💎\n\n"
        f"Do'stingizni taklif qiling va darhol {reward} Almaz oling!\n"
        f"Taklif havolangiz: https://t.me/{bot_username}?start={user_id}"
    )

    share_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Do'stlarga ulashish",
                    switch_inline_query=plain_text
                )
            ]
        ]
    )

    await message.answer(html_text, parse_mode="HTML", reply_markup=share_kb)


@dp.message(F.text == "📣 Yangiliklar & Bonuslar")
async def show_news(message: Message):
    if await guard_common(message):
        return
    content = await get_dynamic_text("news")
    if not content:
        return await message.answer("🔭 Hozircha yangiliklar yo'q.")
    if content.startswith("MSG:"):
        try:
            _, chat_id_str, msg_id_str = content.split(":")
            await bot.copy_message(message.chat.id, int(chat_id_str), int(msg_id_str))
            return
        except Exception as e:
            log.warning("copy news failed: %s", e)
    await message.answer(f"📰 <b>So'nggi yangiliklar</b>\n\n{content}", parse_mode="HTML")


@dp.message(F.text == "🛒 Almaz Do'koni")
async def buy_almaz(message: Message):
    if await guard_common(message):
        return
    text = await get_dynamic_text("almaz_buy")
    if not text:
        text = (
            "🛒 <b>Almaz Do'koni</b>\n\n"
            "1️⃣ 10 000 so'm → 100 Almaz\n"
            "2️⃣ 25 000 so'm → 300 Almaz\n"
            "3️⃣ 40 000 so'm → 500 Almaz\n\n"
            "To'lovdan so'ng shuni yozing: <code>10000 123456789</code>"
        )
    await message.answer(text, parse_mode="HTML")


# ============== Almaz YECHISH ==============
@dp.callback_query(F.data == "withdraw_start")
async def withdraw_start(cb: CallbackQuery, state: FSMContext):
    user_id = cb.from_user.id
    user = await get_user(user_id)
    if not user:
        await cb.answer("Avval ro'yxatdan o'ting.", show_alert=True)
        return
    balance = user[3] if len(user) > 3 and user[3] is not None else 0
    if balance < 105:
        await cb.message.answer(
            "⚠️ Hali almaz yechish uchun balansingiz yetarli emas.\n\n"
            "Eng kamida <b>105 Almaz</b> to'plasangiz, ishlagan almazlaringizni Free Fire akkauntingizga yechib olishingiz mumkin.",
            parse_mode="HTML"
        )
        await cb.answer()
        return

    buttons = []
    if balance >= 105:
        buttons.append(InlineKeyboardButton(text="105 Almaz 💎", callback_data="wd_amount:105"))
    if balance >= 210:
        buttons.append(InlineKeyboardButton(text="210 Almaz 💎", callback_data="wd_amount:210"))
    if balance >= 326:
        buttons.append(InlineKeyboardButton(text="326 Almaz 💎", callback_data="wd_amount:326"))

    kb = InlineKeyboardMarkup(inline_keyboard=[buttons])

    await cb.message.answer(
        "💳 <b>Almaz yechish</b>\n\n"
        f"Balansingiz: <b>{balance} Almaz</b>\n"
        "Qancha almazni yechmoqchi ekanligingizni tanlang:",
        parse_mode="HTML",
        reply_markup=kb
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("wd_amount:"))
async def withdraw_choose_amount(cb: CallbackQuery, state: FSMContext):
    user_id = cb.from_user.id
    user = await get_user(user_id)
    if not user:
        await cb.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    balance = user[3] if len(user) > 3 and user[3] is not None else 0
    try:
        amount = int(cb.data.split(":")[1])
    except ValueError:
        await cb.answer("Noto'g'ri miqdor.", show_alert=True)
        return

    if balance < amount:
        await cb.answer("Balansingiz o'zgargan, yechish uchun yetarli emas.", show_alert=True)
        return

    await state.set_state(WithdrawStates.WAITING_FF_ID)
    await state.update_data(withdraw_amount=amount)

    await cb.message.answer(
        "🎮 Endi, almaz yechmoqchi bo'lgan Free Fire akkauntingiz <b>ID raqamini</b> yuboring.\n\n"
        "ID ni diqqat bilan tekshirib yuboring — almaz aynan shu akkauntga tushiriladi.",
        parse_mode="HTML"
    )
    await cb.answer()


@dp.message(WithdrawStates.WAITING_FF_ID)
async def withdraw_receive_ff_id(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    ff_id = (message.text or "").strip()

    if not amount or not ff_id:
        await message.answer("❌ Noto'g'ri ma'lumot. /start yuborib qayta urinib ko'ring.")
        await state.clear()
        return

    if len(ff_id) < 3:
        await message.answer("⚠️ Free Fire ID juda qisqa ko'rinmoqda. Iltimos, qayta tekshirib yuboring.")
        return

    request_id = await create_withdraw_request(user_id, int(amount), ff_id)
    await state.clear()

    await message.answer(
        "✅ Almaz yechish bo'yicha so'rovingiz qabul qilindi!\n\n"
        f"🔥 Miqdor: <b>{amount} Almaz</b>\n"
        f"🎮 Free Fire ID: <code>{ff_id}</code>\n\n"
        "Almaz 24 soat ichida Free Fire akkauntingizga tushiriladi. Iltimos, sabr qiling 🙂",
        parse_mode="HTML"
    )

    await notify_admins_about_withdraw(request_id)


# ============== Withdraw admin callbacklari ==============
@dp.callback_query(F.data.startswith("wd_ok:"))
async def withdraw_approve(cb: CallbackQuery):
    if not await is_owner_or_admin(cb.from_user.id):
        await cb.answer("Sizda bu amal uchun ruxsat yo'q.", show_alert=True)
        return
    try:
        req_id = int(cb.data.split(":")[1])
    except ValueError:
        await cb.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    req = await get_withdraw_request(req_id)
    if not req:
        await cb.answer("So'rov topilmadi yoki o'chirib yuborilgan.", show_alert=True)
        return

    r_id, user_id, amount, ff_id, status, created_at, processed_at, processed_by, note = req
    if status != "pending":
        await cb.answer(f"Bu so'rov allaqachon '{status}' holatida.", show_alert=True)
        return

    user = await get_user(user_id)
    balance = user[3] if user and len(user) > 3 and user[3] is not None else 0
    if balance < amount:
        await cb.answer("Foydalanuvchi balansida bu miqdor yetarli emas.", show_alert=True)
        return

    await add_almaz(user_id, -amount)
    await update_withdraw_status(req_id, "approved", cb.from_user.id, None)
    await update_withdraw_admin_messages(req_id, "✅ Tasdiqlandi")

    try:
        await bot.send_message(
            user_id,
            "🎉 Almaz yechish so'rovingiz tasdiqlandi!\n\n"
            f"💎 Miqdor: <b>{amount} Almaz</b>\n"
            "Almazingiz Free Fire akkauntingizga muvaffaqiyatli tashlab berildi. Rahmat! 😊",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await send_proof_receipt(req_id, user_id, amount, ff_id)
    await cb.answer("So'rov tasdiqlandi.")


@dp.callback_query(F.data.startswith("wd_reject:"))
async def withdraw_reject(cb: CallbackQuery):
    if not await is_owner_or_admin(cb.from_user.id):
        await cb.answer("Sizda bu amal uchun ruxsat yo'q.", show_alert=True)
        return
    try:
        req_id = int(cb.data.split(":")[1])
    except ValueError:
        await cb.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    req = await get_withdraw_request(req_id)
    if not req:
        await cb.answer("So'rov topilmadi yoki o'chirib yuborilgan.", show_alert=True)
        return

    r_id, user_id, amount, ff_id, status, created_at, processed_at, processed_by, note = req
    if status != "pending":
        await cb.answer(f"Bu so'rov allaqachon '{status}' holatida.", show_alert=True)
        return

    await update_withdraw_status(req_id, "rejected", cb.from_user.id, None)
    await update_withdraw_admin_messages(req_id, "❌ Rad etildi")

    try:
        await bot.send_message(
            user_id,
            "❌ Almaz yechish bo'yicha so'rovingiz rad etildi.\n\n"
            "Bunga turli sabablar bo'lishi mumkin (qoidabuzarlik, noto'g'ri ma'lumot va hokazo).\n"
            "Agar bu xatolik deb o'ylasangiz, qo'llab-quvvatlashga murojaat qilishingiz mumkin.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await cb.answer("So'rov rad etildi.")


@dp.callback_query(F.data.startswith("wd_edit:"))
async def withdraw_edit_start(cb: CallbackQuery, state: FSMContext):
    if not await is_owner_or_admin(cb.from_user.id):
        await cb.answer("Sizda bu amal uchun ruxsat yo'q.", show_alert=True)
        return
    try:
        req_id = int(cb.data.split(":")[1])
    except ValueError:
        await cb.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    req = await get_withdraw_request(req_id)
    if not req:
        await cb.answer("So'rov topilmadi yoki o'chirib yuborilgan.", show_alert=True)
        return
    if req[4] != "pending":
        await cb.answer(f"Bu so'rov allaqachon '{req[4]}' holatida.", show_alert=True)
        return

    await state.set_state(WithdrawEdit.WAITING_TEXT)
    await state.update_data(edit_request_id=req_id)

    await cb.message.answer(
        "✏️ Foydalanuvchiga yuboriladigan xabar matnini kiriting.\n"
        "Masalan: Free Fire ID noto'g'ri ko'rsatilgan, iltimos, qayta yuboring.",
        reply_markup=back_kb
    )
    await cb.answer()


@dp.message(WithdrawEdit.WAITING_TEXT)
async def withdraw_edit_send(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    data = await state.get_data()
    req_id = data.get("edit_request_id")
    if not req_id:
        await state.clear()
        await message.answer("❌ So'rov topilmadi. Qaytadan urinib ko'ring.", reply_markup=admin_menu)
        return

    note = (message.text or "").strip()
    req = await get_withdraw_request(int(req_id))
    if not req:
        await state.clear()
        await message.answer("❌ So'rov bazadan topilmadi.", reply_markup=admin_menu)
        return

    r_id, user_id, amount, ff_id, status, created_at, processed_at, processed_by, old_note = req
    if status != "pending":
        await state.clear()
        await message.answer(f"ℹ️ Bu so'rov allaqachon '{status}' holatiga o'tkazilgan.", reply_markup=admin_menu)
        return

    try:
        await bot.send_message(
            user_id,
            f"✏️ Almaz yechish so'rovi bo'yicha xabar:\n\n{note}"
        )
    except Exception:
        pass

    await update_withdraw_status(int(req_id), "edited", message.from_user.id, note)
    await update_withdraw_admin_messages(int(req_id), "✏️ Tahrirlandi")

    await state.clear()
    await message.answer(
        "✅ Izoh foydalanuvchiga yuborildi va so'rov <b>tahrirlandi</b> holatiga o'tkazildi.",
        parse_mode="HTML",
        reply_markup=admin_menu
    )

# ============== ADMIN PANEL ==============
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_owner_or_admin(message.from_user.id):
        return await message.answer("🚫 Siz admin emassiz.")
    await message.answer("👑 <b>Admin panel</b>", parse_mode="HTML", reply_markup=admin_menu)


@dp.message(F.text == "📊 Foydalanuvchilar soni")
async def user_count(message: Message):
    if not await is_owner_or_admin(message.from_user.id):
        return
    from database import DB_NAME
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]
    await message.answer(f"📈 Jami foydalanuvchilar: <b>{total}</b>", parse_mode="HTML")


@dp.message(F.text == "📜 Isbotlar kanali")
async def proof_channel_prompt(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return

    current = await get_proof_channel_value()
    current_text = f"<code>{current}</code>" if current else "❌ Sozlanmagan"
    info = (
        "📜 <b>Isbotlar kanali</b>\n\n"
        "Bot tasdiqlangan almaz yechish cheklarining nusxasini shu kanalda joylaydi.\n"
        "Botni kanalga admin qiling va <b>@username</b> yoki <b>-100...</b> ID yuboring.\n"
        "Sozlamani o'chirish uchun <b>0</b> yuboring.\n"
        "Bekor qilish uchun <b>⬅️ Orqaga</b> tugmasidan foydalaning.\n\n"
        f"Hozirgi qiymat: {current_text}\n"
        "ℹ️ Kanal maxfiy ID bo'lsa, foydalanuvchilar uchun tugma havola bera olmaydi."
    )
    await state.set_state(ProofChannelSetup.WAITING)
    await message.answer(info, parse_mode="HTML", reply_markup=back_kb)


@dp.message(F.text == "⬅️ Orqaga", StateFilter(ProofChannelSetup.WAITING))
async def proof_channel_cancel(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏎ Isbotlar kanali sozlamalari bekor qilindi.", reply_markup=admin_menu)


@dp.message(StateFilter(ProofChannelSetup.WAITING))
async def proof_channel_save(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    try:
        normalized = normalize_proof_channel_value(raw)
    except ValueError as exc:
        await message.answer(f"❌ {exc}", reply_markup=back_kb)
        return

    await state.clear()
    if normalized is None:
        await delete_setting(PROOF_CHANNEL_SETTING_KEY)
        await message.answer("ℹ️ Isbotlar kanali o'chirildi.", reply_markup=admin_menu)
        return

    await set_setting(PROOF_CHANNEL_SETTING_KEY, normalized)
    url_hint = build_proof_channel_url(normalized)
    extra = f"\n🔗 Havola: {url_hint}" if url_hint else "\nℹ️ Kanal ID ko'rinishida saqlandi."
    await message.answer(
        "✅ Isbotlar kanali yangilandi.\n"
        f"Saqlangan qiymat: <code>{normalized}</code>{extra}",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


@dp.message(F.text == "📰 Reklama/Yangilik sozlash")
async def edit_news(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.set_state(TextEdit.new_text)
    await state.update_data(section="news")
    await message.answer("📰 Yangi yangilik xabarini yuboring (matn yoki media).", reply_markup=back_kb)


@dp.message(F.text == "💰 Almaz sotib olish matni")
async def edit_buy_text(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.set_state(TextEdit.new_text)
    await state.update_data(section="almaz_buy")
    await message.answer("💰 Almaz sotib olish bo'limi uchun matn yuboring:", reply_markup=back_kb)


@dp.message(F.text == "⬅️ Orqaga", StateFilter(TextEdit.new_text))
async def cancel_text_edit(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏎ O'zgartirish bekor qilindi.", reply_markup=admin_menu)


@dp.message(StateFilter(TextEdit.new_text))
async def save_dynamic_text(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    data = await state.get_data()
    section = data.get("section")
    if section == "news":
        if message.text and not message.caption:
            await update_dynamic_text("news", message.text)
        else:
            await update_dynamic_text("news", f"MSG:{message.chat.id}:{message.message_id}")
        await state.clear()
        return await message.answer("✅ Yangilik xabari yangilandi.", reply_markup=admin_menu)
    if section == "almaz_buy":
        await update_dynamic_text("almaz_buy", message.text or "")
        await state.clear()
        return await message.answer("✅ Matn yangilandi.", reply_markup=admin_menu)


@dp.message(F.text == "📢 Reklama yuborish")
async def ask_broadcast(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await message.answer("📢 Reklama xabarini yuboring (matn yoki media).", reply_markup=back_kb)
    await state.set_state(Broadcast.WAITING)


@dp.message(F.text == "⬅️ Orqaga", StateFilter(Broadcast.WAITING))
async def cancel_broadcast(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏎ Reklama yuborish bekor qilindi.", reply_markup=admin_menu)


@dp.message(
    StateFilter(Broadcast.WAITING),
    F.content_type.in_({
        ContentType.TEXT, ContentType.PHOTO, ContentType.VIDEO, ContentType.AUDIO,
        ContentType.DOCUMENT, ContentType.VOICE, ContentType.STICKER, ContentType.VIDEO_NOTE
    })
)
async def handle_broadcast(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🚀 Reklama yuborilmoqda… ⏳")

    from database import DB_NAME
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM users")
        users = [r[0] for r in await cur.fetchall()]

    total, success, failed = len(users), 0, 0
    for uid in users:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.03)
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Reklama yakunlandi!\n📬 Yuborilgan: <b>{success}</b>\n❌ Yetkazilmagan: <b>{failed}</b>\n👥 Jami: <b>{total}</b>",
        parse_mode="HTML", reply_markup=admin_menu
    )


@dp.message(F.text == "🧩 Majburiy kanallar")
async def channels_menu(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    channels = await list_required_channels()
    text = "🧩 <b>Majburiy kanallar</b>\n\n" + ("\n".join(f"• {ch}" for ch in channels) if channels else "– Hozircha kanal yo'q.")
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Kanal qo'shish"), KeyboardButton(text="➖ Kanal o'chirish")],
            [KeyboardButton(text="⬅️ Chiqish")]
        ], resize_keyboard=True
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.message(F.text == "➕ Kanal qo'shish")
async def channel_add_prompt(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    cnt = await required_channels_count()
    if cnt >= 6:
        return await message.answer("⚠️ 6 tadan ortiq kanal ulash mumkin emas.")
    await state.set_state(ChanManage.ADD)
    await message.answer(
        "Kanal username'ini yuboring:\n\n"
        "<b>Telegram kanallar:</b>\n"
        "• @mychannel\n"
        "• https://t.me/mychannel\n"
        "• -100123456789\n\n"
        "<b>YouTube kanallar:</b>\n"
        "• https://www.youtube.com/@channelname\n"
        "• https://www.youtube.com/c/channelname\n"
        "• https://www.youtube.com/user/username",
        parse_mode="HTML",
        reply_markup=back_kb
    )


@dp.message(StateFilter(ChanManage.ADD))
async def channel_add(message: Message, state: FSMContext):
    ch = (message.text or "").strip()
    if not await is_owner_or_admin(message.from_user.id):
        return
    if ch == "⬅️ Orqaga":
        await state.clear()
        return await message.answer("⏎ Bekor qilindi.", reply_markup=admin_menu)
    
    # Normalize URLs to usable format
    if ch.startswith(("http://", "https://", "tg://")):
        # Handle t.me (Telegram) URLs
        if "t.me/" in ch:
            after = ch.split("t.me/", 1)[1]
            slug = after.split("?")[0].strip().strip("/")
            slug = slug.lstrip("@")
            if slug:
                ch = f"@{slug}"
            else:
                await state.clear()
                return await message.answer("⚠️ t.me URL dan kanal username aniqlanmadi. Iltimos, @username yuboring.")
        # Handle YouTube URLs
        elif "youtube.com/" in ch or "youtu.be/" in ch:
            if "youtube.com/@" in ch:
                # https://www.youtube.com/@channelname format
                slug = ch.split("@", 1)[1].split("?")[0].split("/")[0].strip()
                if slug:
                    ch = f"yt:@{slug}"
                else:
                    await state.clear()
                    return await message.answer("⚠️ YouTube URL dan kanal nomi aniqlanmadi.")
            elif "youtube.com/c/" in ch:
                # https://www.youtube.com/c/channelname format
                slug = ch.split("/c/", 1)[1].split("?")[0].split("/")[0].strip()
                if slug:
                    ch = f"yt:c:{slug}"
                else:
                    await state.clear()
                    return await message.answer("⚠️ YouTube URL dan kanal nomi aniqlanmadi.")
            elif "youtube.com/user/" in ch:
                # https://www.youtube.com/user/username format
                slug = ch.split("/user/", 1)[1].split("?")[0].split("/")[0].strip()
                if slug:
                    ch = f"yt:u:{slug}"
                else:
                    await state.clear()
                    return await message.answer("⚠️ YouTube URL dan foydalanuvchi nomi aniqlanmadi.")
            else:
                await state.clear()
                return await message.answer("⚠️ YouTube URL noto'g'ri format. Qo'llab-quvvatlanadigan formatlar:\n• https://www.youtube.com/@channelname\n• https://www.youtube.com/c/channelname\n• https://www.youtube.com/user/username")
        else:
            await state.clear()
            return await message.answer("⚠️ Qo'llab-quvvatlanadigan URL'lar: t.me/username yoki YouTube URL.")
    
    # Validate format
    is_valid = (ch.startswith("@") or ch.startswith("-100") or ch.startswith("yt:") or 
                (ch.lstrip("-").isdigit() and not ch.startswith("yt")))
    
    if not is_valid:
        await state.clear()
        return await message.answer("⚠️ Iltimos, @username, t.me/username, YouTube URL yoki -100... chat ID yuboring.")
    
    ok = await add_required_channel(ch)
    await state.clear()
    if ok:
        await message.answer("✅ Kanal qo'shildi.", reply_markup=admin_menu)
    else:
        await message.answer("ℹ️ Bu kanal allaqachon mavjud.", reply_markup=admin_menu)


@dp.message(F.text == "➖ Kanal o'chirish")
async def channel_remove_prompt(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.set_state(ChanManage.REMOVE)
    await message.answer("O'chirish uchun @username yoki -100... chat ID yuboring:", reply_markup=back_kb)


@dp.message(StateFilter(ChanManage.REMOVE))
async def channel_remove(message: Message, state: FSMContext):
    ch = (message.text or "").strip()
    if not await is_owner_or_admin(message.from_user.id):
        return
    if ch == "⬅️ Orqaga":
        await state.clear()
        return await message.answer("⏎ Bekor qilindi.", reply_markup=admin_menu)
    ok = await remove_required_channel(ch)
    await state.clear()
    if ok:
        await message.answer("✅ Kanal o'chirildi.", reply_markup=admin_menu)
    else:
        await message.answer("ℹ️ Bunday kanal topilmadi.", reply_markup=admin_menu)


@dp.message(F.text == "🛡 Admin boshqaruvi")
async def admin_manage_menu(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("🚫 Bu bo'lim faqat egasi uchun.")
    admins = await list_admins()
    text = "🛡 <b>Adminlar ro'yxati:</b>\n" + ("\n".join(f"• @{u or 'unknown'} – <code>{uid}</code>" for uid, u in admins) if admins else "– Hech kim yo'q.")
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Admin qo'shish"), KeyboardButton(text="🗑 Adminni o'chirish")],
            [KeyboardButton(text="⬅️ Chiqish")]
        ], resize_keyboard=True
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.message(F.text == "👤 Admin qo'shish")
async def admin_add_prompt(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    await state.set_state(AdminManage.ADD)
    await message.answer("Admin qilish uchun foydalanuvchi ID yuboring:", reply_markup=back_kb)


@dp.message(StateFilter(AdminManage.ADD))
async def admin_add_exec(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    if (message.text or "").strip() == "⬅️ Orqaga":
        await state.clear()
        return await message.answer("⏎ Bekor qilindi.", reply_markup=admin_menu)
    if not (message.text or "").isdigit():
        return await message.answer("ID faqat raqamlardan iborat bo'lishi kerak.")
    uid = int(message.text)
    ok = await add_admin(uid, None)
    await state.clear()
    await message.answer("✅ Admin qo'shildi." if ok else "ℹ️ Bu foydalanuvchi allaqachon admin.", reply_markup=admin_menu)


@dp.message(F.text == "🗑 Adminni o'chirish")
async def admin_remove_prompt(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    await state.set_state(AdminManage.REMOVE)
    await message.answer("O'chirish uchun admin ID yuboring:", reply_markup=back_kb)


@dp.message(StateFilter(AdminManage.REMOVE))
async def admin_remove_exec(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    if (message.text or "").strip() == "⬅️ Orqaga":
        await state.clear()
        return await message.answer("⏎ Bekor qilindi.", reply_markup=admin_menu)
    if not (message.text or "").isdigit():
        return await message.answer("ID faqat raqamlardan iborat bo'lishi kerak.")
    uid = int(message.text)
    ok = await remove_admin(uid)
    await state.clear()
    await message.answer("✅ Admin o'chirildi." if ok else "ℹ️ Bunday admin topilmadi.", reply_markup=admin_menu)


@dp.message(F.text == "💎 Qo'lda almaz berish")
async def give_almaz_prompt(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.set_state(GiveAlmaz.WAIT)
    await message.answer(
        "Bu bo'limda foydalanuvchilarga qo'lda Almaz berishingiz mumkin.\n\n"
        "ID va Almaz miqdorini quyidagi ko'rinishda yuboring:\n"
        "<code>123456789 10</code>  (ID + Almaz miqdori)",
        parse_mode="HTML",
        reply_markup=back_kb
    )


@dp.message(StateFilter(GiveAlmaz.WAIT))
async def give_almaz_exec(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if text == "⬅️ Orqaga":
        await state.clear()
        return await message.answer("⏎ Amaliyot bekor qilindi.", reply_markup=admin_menu)

    parts = text.split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return await message.answer(
            "⚠️ Iltimos, formatga rioya qiling:\n"
            "<code>ID MIQDOR</code>\nMasalan: <code>123456789 10</code>",
            parse_mode="HTML"
        )

    user_id = int(parts[0])
    amount = int(parts[1])

    from database import DB_NAME
    import aiosqlite
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT username, almaz FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()

    if not row:
        return await message.answer("❌ Bunday foydalanuvchi bazada topilmadi.")

    await add_almaz(user_id, amount)
    await state.clear()

    try:
        await bot.send_message(
            user_id,
            f"🎁 Sizga bot administratori tomonidan <b>{amount} Almaz</b> taqdim qilindi! Tabriklaymiz 🎉",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer(
        f"✅ <code>{user_id}</code> foydalanuvchi hisobiga {amount} Almaz qo'shildi.",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


@dp.message(F.text == "💾 Backup yaratish")
async def create_backup(message: Message):
    if not await is_owner_or_admin(message.from_user.id):
        return
    result = await backup_database()
    if result.startswith("Backup xatosi"):
        await message.answer(f"❌ {result}", reply_markup=admin_menu)
    else:
        await message.answer(
            f"✅ Baza muvaffaqiyatli zaxiralandi!\n📁 Fayl: <code>{result}</code>",
            parse_mode="HTML",
            reply_markup=admin_menu
        )


@dp.message(F.text == "🔧 Referal almaz qiymati")
async def change_ref_reward(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    current = await get_referral_reward()
    await state.set_state("WAITING_REF_REWARD")
    await message.answer(
        f"🔧 Hozirgi referal mukofoti: <b>{current} Almaz</b>\n\n"
        "Yangi qiymatni kiriting (faqat raqam):",
        parse_mode="HTML",
        reply_markup=back_kb
    )


@dp.message(StateFilter("WAITING_REF_REWARD"))
async def save_new_ref_reward(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return

    if message.text.strip() == "⬅️ Orqaga":
        await state.clear()
        return await message.answer("⏎ Bekor qilindi.", reply_markup=admin_menu)

    if not message.text.isdigit():
        return await message.answer("⚠ Iltimos, faqat raqam kiriting.")

    value = message.text.strip()
    await set_setting("referral_reward", value)

    await state.clear()
    await message.answer(
        f"✅ Referal mukofoti yangilandi: <b>{value} Almaz</b>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


@dp.message(F.text == "📈 Statistika")
async def show_stats(message: Message):
    if not await is_owner_or_admin(message.from_user.id):
        return
    top = await get_top_referrers_today(limit=10)
    total, pending, approved, edited, rejected = await get_withdraw_stats()

    text = "📈 <b>Statistika</b>\n\n"

    text += "🏆 Bugungi TOP-10 taklif qiluvchilar (tasdiqlangan referallar):\n"
    if not top:
        text += "– Hozircha ma'lumot yo'q.\n"
    else:
        for i, (uid, username, cnt) in enumerate(top, 1):
            uname = f"@{username}" if username else f"ID:{uid}"
            text += f"{i}. {uname} – {cnt} ta tasdiqlangan referal\n"

    text += "\n💳 <b>Almaz yechish so'rovlari</b>:\n"
    text += f"• Umumiy so'rovlar: <b>{total}</b>\n"
    text += f"• Tasdiqlangan: <b>{approved}</b>\n"
    text += f"• Tahrirlangan: <b>{edited}</b>\n"
    text += f"• Rad etilgan: <b>{rejected}</b>\n"
    text += f"• Hozirda kutilayotgan: <b>{pending}</b>\n"

    await message.answer(text, parse_mode="HTML")

    if top:
        buttons = []
        for uid, username, cnt in top:
            label = f"{'@'+username if username else str(uid)} – {cnt} ta"
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"topuser:{uid}")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(
            "🔍 TOP-10 ichidan foydalanuvchi profilini ko'rish uchun tanlang:",
            reply_markup=kb
        )


@dp.callback_query(F.data.startswith("topuser:"))
async def top_user_profile(cb: CallbackQuery):
    if not await is_owner_or_admin(cb.from_user.id):
        await cb.answer("Siz admin emassiz.", show_alert=True)
        return
    try:
        uid = int(cb.data.split(":")[1])
    except ValueError:
        await cb.answer("Noto'g'ri ID.", show_alert=True)
        return

    user = await get_user(uid)
    if not user:
        await cb.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    almaz = user[3] if len(user) > 3 and user[3] is not None else 0
    phone = user[5] if len(user) > 5 else None
    total_refs_verified = await count_verified_referrals(uid)
    remain = await get_suspension_remaining(uid)

    txt = (
        "🔎 <b>Foydalanuvchi profili</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Username: @{user[1] or 'Anonim'}\n"
        f"📞 Telefon: {phone or '–'}\n"
        f"💎 Almaz: {almaz}\n"
        f"🤝 Tasdiqlangan takliflar: {total_refs_verified}\n"
        f"⏳ Tanaffus (qolgan): {remain} s\n"
    )
    await cb.message.answer(txt, parse_mode="HTML")
    await cb.answer()


@dp.message(F.text == "⏳ Tanaffus berish")
async def suspend_prompt(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.set_state(SuspensionInput.WAIT)
    await message.answer(
        "🕒 Tanaffus berish: <code>user_id soat</code> ko'rinishida yuboring. Masalan:\n"
        "<code>123456789 2</code>  (2 soatga tanaffus)",
        parse_mode="HTML", reply_markup=back_kb
    )


@dp.message(F.text == "⬅️ Orqaga", StateFilter(SuspensionInput.WAIT))
async def suspend_back_handler(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏪ Tanaffus bo'limidan chiqildi.", reply_markup=admin_menu)


@dp.message(
    StateFilter(SuspensionInput.WAIT),
    lambda m: (m.text or "").strip().count(" ") == 1 and all(p.isdigit() for p in (m.text or "").split())
)
async def simple_two_ints_handler(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    uid_str, hour_str = (message.text or "").split()
    uid, hours = int(uid_str), int(hour_str)
    seconds = hours * 3600
    await set_suspension(uid, seconds)
    remain = await get_suspension_remaining(uid)
    try:
        await bot.send_message(
            uid,
            "😴 Profilingiz vaqtincha tanaffusda.\n"
            f"⏰ Tanaffus {hours} soatga belgilandi. Taxminan {remain} soniyadan so'ng bot qayta faollashadi.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await state.clear()
    await message.answer(
        f"✅ <code>{uid}</code> foydalanuvchi {hours} soatga tanaffusga chiqarildi.",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


@dp.message(F.text == "🔎 Foydalanuvchini topish")
async def search_user_prompt(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.set_state(SearchUser.WAIT)
    await message.answer("ID yoki @username yuboring:", reply_markup=back_kb)


@dp.message(F.text == "⬅️ Orqaga", StateFilter(SearchUser.WAIT))
async def search_user_cancel(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏎ Qidiruv bekor qilindi.", reply_markup=admin_menu)


@dp.message(StateFilter(SearchUser.WAIT))
async def search_user_exec(message: Message, state: FSMContext):
    if not await is_owner_or_admin(message.from_user.id):
        return
    from database import DB_NAME
    import aiosqlite
    q = (message.text or "").strip()

    row = None
    async with aiosqlite.connect(DB_NAME) as db:
        if q.isdigit():
            cur = await db.execute(
                "SELECT user_id, username, almaz, ref_by, verified, phone, created_at FROM users WHERE user_id=?",
                (int(q),)
            )
            row = await cur.fetchone()
        elif q.startswith("@"):
            cur = await db.execute(
                "SELECT user_id, username, almaz, ref_by, verified, phone, created_at FROM users WHERE username=?",
                (q.lstrip("@"),)
            )
            row = await cur.fetchone()

        if not row:
            await state.clear()
            return await message.answer("❌ Foydalanuvchi topilmadi.", reply_markup=admin_menu)

        user_id, username, almaz, ref_by, verified, phone, created_at = row
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE ref_by=?", (user_id,))
        ref_cnt = (await cur.fetchone())[0]
    remain = await get_suspension_remaining(user_id)
    first_seen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_at or 0)) if created_at else "–"

    txt = (
        "🔎 <b>Foydalanuvchi ma’lumoti</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>Username:</b> @{username or 'Anonim'}\n"
        f"📞 <b>Telefon:</b> {phone or '—'}\n"
        f"✅ <b>Verified:</b> {'Ha' if (verified or 0) else 'Yo‘q'}\n"
        f"💎 <b>Almaz:</b> {almaz or 0}\n"
        f"🤝 <b>Referal soni (ref_by bilan):</b> {ref_cnt}\n"
        f"🕒 <b>Ro‘yxatdan o‘tgan:</b> {first_seen}\n"
        f"⏳ <b>Tanaffus (qolgan):</b> {remain} s\n"
    )
    
    await state.clear()
    await message.answer(txt, parse_mode="HTML", reply_markup=admin_menu)


@dp.message(F.text == "⬅️ Chiqish")
async def admin_exit_to_main(message: Message, state: FSMContext):
    if await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return await message.answer("🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu)
    await state.clear()
    await message.answer("🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu)


# Bootstrap
async def main():
    await init_db()
    await setup_bot_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())