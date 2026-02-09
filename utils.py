import time
import humanize
import PTN
import subprocess
import os
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

def get_eta(rem, speed):
    if speed <= 0: return "Unknown"
    seconds = rem / speed
    return time.strftime("%Hh %Mm %Ss", time.gmtime(seconds))

def get_prog_bar(pct):
    p = int(pct / 10)
    return "▰" * p + "▱" * (10 - p)

def get_status_card(filename, pct, speed, eta, engine_icon, engine_name):
    """Standardized Premium Status Card"""
    return (
        f"📝 **File:** `{filename[:50]}...`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"[{get_prog_bar(pct)}]  **{pct:.1f}%**\n"
        f"🚀 **Speed:** `{humanize.naturalsize(speed)}/s`\n"
        f"⏳ **ETA:** `{eta}`\n"
        f"⚙️ **Engine:** {engine_icon} `{engine_name}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

def generate_thumbnail(video_path):
    output_path = video_path + ".jpg"
    try:
        # Take a snapshot at 10% of the video duration or 10s
        cmd = [
            "ffmpeg", "-ss", "00:00:10", "-i", video_path,
            "-vframes", "1", "-q:v", "2", output_path, "-y"
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_path):
            return output_path
    except: pass
    return None

def get_media_info(path):
    try:
        result = subprocess.check_output(["mediainfo", "--Inform=Video;%Width%x%Height%, %DisplayAspectRatio/String%, %FrameRate% fps", path])
        return result.decode().strip()
    except: return "Unknown Info"

def clean_rename(original_name):
    parsed = PTN.parse(original_name)
    if parsed.get('season') or parsed.get('episode'):
        s = f"S{parsed.get('season', 0):02d}"
        e = f"E{parsed.get('episode', 0):02d}"
        t = parsed.get('title', 'File')
        return f"[{s}{e}] {t}.mkv"
    return original_name

async def edit_msg(client, chat_id, message_id, text, reply_markup=None):
    try:
        await client.edit_message_text(chat_id, message_id, text, reply_markup=reply_markup)
    except MessageNotModified: pass

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
