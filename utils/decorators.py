from functools import wraps
from pyrogram.types import Message
import config

def admin_check(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.from_user.id not in config.ADMIN_IDS:
            await message.reply_text(
                "⚠️ You are not authorized to use this command!\n"
                "Only bot admins can use this."
            )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper
