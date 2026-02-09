import time
import humanize
import os
from config import DUMP_CHAT_ID
from utils import edit_msg, get_status_card, generate_thumbnail

async def tg_prog(current, total, client, chat_id, message_id, start_time, filename):
    if time.time() - getattr(tg_prog, "last_up", 0) < 5: return
    tg_prog.last_up = time.time()
    pct = (current / total) * 100
    speed = current / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
    eta = "Calculating..." if speed == 0 else humanize.precisedelta(int((total-current)/speed))
    
    text = get_status_card(filename, pct, speed, eta, "📤", "Telegram")
    await edit_msg(client, chat_id, message_id, text)

async def upload_to_tg_db(client, path, filename, status_chat_id, status_msg_id):
    thumb = generate_thumbnail(path)
    try:
        # Upload to Storage Channel
        sent_file = await client.send_document(
            chat_id=DUMP_CHAT_ID,
            document=path,
            thumb=thumb,
            caption=f"✅ `{filename}`",
            progress=tg_prog,
            progress_args=(client, status_chat_id, status_msg_id, time.time(), filename)
        )
        
        # AUTO-COPY: Send to the user who requested it
        try:
            await sent_file.copy(chat_id=status_chat_id, caption=f"🏁 **Your File is Ready!**\n`{filename}`")
        except: pass

        if thumb and os.path.exists(thumb): os.remove(thumb)
        return sent_file.link
    except Exception as e:
        if thumb and os.path.exists(thumb): os.remove(thumb)
        return f"TG Upload Failed: {e}"
