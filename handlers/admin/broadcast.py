from pyrogram import Client, filters
from pyrogram.types import Message
from database import Database
from utils import is_admin
import asyncio

db = Database()

@Client.on_message(filters.command("broadcast") & filters.reply)
async def broadcast_command(client: Client, message: Message):
    if not is_admin(message):
        await message.reply_text("⚠️ You are not authorized to broadcast!")
        return

    replied_msg = message.reply_to_message
    if not replied_msg:
        await message.reply_text("❌ Please reply to a message to broadcast!")
        return
    
    status_msg = await message.reply_text("🔄 Broadcasting message...")
    users = await db.get_all_users()
    success = 0
    failed = 0
    
    for user in users:
        try:
            if replied_msg.text:
                await client.send_message(user["user_id"], replied_msg.text)
            elif replied_msg.media:
                await client.copy_message(
                    chat_id=user["user_id"],
                    from_chat_id=replied_msg.chat.id,
                    message_id=replied_msg.message_id
                )
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)
    
    broadcast_text = (
        "✅ **Broadcast Completed**\n\n"
        f"✓ Success: {success}\n"
        f"× Failed: {failed}\n"
        f"📊 Total: {success + failed}"
    )
    await status_msg.edit_text(broadcast_text)