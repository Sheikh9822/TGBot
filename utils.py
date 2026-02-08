import time
import humanize
import PTN
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

def get_eta(rem, speed):
    if speed <= 0: return "Unknown"
    seconds = rem / speed
    return time.strftime("%Hh %Mm %Ss", time.gmtime(seconds))

def get_prog_bar(pct):
    p = int(pct / 10)
    return "█" * p + "░" * (10 - p)

def clean_rename(original_name):
    parsed = PTN.parse(original_name)
    if parsed.get('season') or parsed.get('episode'):
        s = f"S{parsed.get('season', 0):02d}"
        e = f"E{parsed.get('episode', 0):02d}"
        t = parsed.get('title', 'File')
        q = parsed.get('quality', 'HD')
        return f"[{s}{e}] {t} [{q}].mkv"
    return original_name

async def edit_msg(client, chat_id, message_id, text, reply_markup=None):
    try:
        await client.edit_message_text(chat_id, message_id, text, reply_markup=reply_markup)
    except MessageNotModified: pass
    except Exception as e: print(f"Edit Error: {e}")

def gen_selection_kb(active_tasks, h_hash, page=0, per_page=8):
    task = active_tasks[h_hash]
    files, selected = task["files"], task["selected"]
    start, end = page * per_page, (page + 1) * per_page
    btns = []
    for i, f in enumerate(files[start:end]):
        idx = start + i
        icon = "✅" if idx in selected else "⬜"
        btns.append([InlineKeyboardButton(f"{icon} {f['name'][:35]}", callback_data=f"tog_{h_hash}_{idx}_{page}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{h_hash}_{page-1}"))
    if end < len(files): nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{h_hash}_{page+1}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🚀 START PROCESS", callback_data=f"start_{h_hash}")])
    btns.append([InlineKeyboardButton("❌ CANCEL", callback_data=f"ca_{h_hash}")])
    return InlineKeyboardMarkup(btns)
