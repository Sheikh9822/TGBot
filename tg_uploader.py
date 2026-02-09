import time
import humanize
from config import DUMP_CHAT_ID
from utils import edit_msg

async def tg_prog(current, total, client, chat_id, message_id, start_time, filename):
    if time.time() - getattr(tg_prog, "last_up", 0) < 5: return
    tg_prog.last_up = time.time()
    pct = (current / total) * 100
    speed = current / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
    text = f"📤 **TG Uploading:** `{filename}`\n`{pct:.1f}%` | 🚀 `{humanize.naturalsize(speed)}/s`"
    await edit_msg(client, chat_id, message_id, text)

async def upload_to_tg_db(client, path, filename, status_chat_id, status_msg_id):
    try:
        sent_file = await client.send_document(
            chat_id=DUMP_CHAT_ID,
            document=path,
            caption=f"✅ `{filename}`",
            progress=tg_prog,
            progress_args=(client, status_chat_id, status_msg_id, time.time(), filename)
        )
        return sent_file.link
    except Exception as e:
        return f"TG Upload Failed: {e}"
