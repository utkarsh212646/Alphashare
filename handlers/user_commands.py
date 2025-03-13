from pyrogram import Client, filters
from pyrogram.types import Message
from .command_handler import db, button_manager
from .utils import schedule_message_deletion
import config
import asyncio

@Client.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await db.add_user(message.from_user.id, message.from_user.username)
    
    if len(message.command) > 1:
        file_uuid = message.command[1]
        
        if not await button_manager.check_force_sub(client, message.from_user.id):
            await message.reply_text(
                "**⚠️ You must join our channel to use this bot!**\n\n"
                "Please join Our Forcesub Channel and try again.",
                reply_markup=button_manager.force_sub_button()
            )
            return
        
        file_data = await db.get_file(file_uuid)
        if not file_data:
            await message.reply_text("❌ File not found or has been deleted!")
            return
        
        try:
            msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=config.DB_CHANNEL_ID,
                message_id=file_data["message_id"]
            )
            await db.increment_downloads(file_uuid)
            await db.update_file_message_id(file_uuid, msg.id, message.chat.id)
            
            if file_data.get("auto_delete"):
                delete_time = file_data.get("auto_delete_time")
                if delete_time:
                    info_msg = await msg.reply_text(
                        f"⏳ **File Auto-Delete Information**\n\n"
                        f"This file will be automatically deleted in {delete_time} minutes\n"
                        f"• Delete Time: {delete_time} minutes\n"
                        f"• Time Left: {delete_time} minutes\n"
                        f"💡 **Save this file to your saved messages before it's deleted!**"
                    )
                    
                    asyncio.create_task(schedule_message_deletion(
                        client, file_uuid, message.chat.id, [msg.id, info_msg.id], delete_time
                    ))
                
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
        return
    
    await message.reply_text(
        config.Messages.START_TEXT.format(
            bot_name=config.BOT_NAME,
            user_mention=message.from_user.mention
        ),
        reply_markup=button_manager.start_button()
    )

@Client.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = (
        "**📚 Bot Commands & Usage**\n\n"
        "Here are the available commands:\n\n"
        "👥 **User Commands:**\n"
        "• /start - Start the bot\n"
        "• /help - Show this help message\n"
        "• /about - About the bot\n\n"
        "👮‍♂️ **Admin Commands:**\n"
        "• /upload - Upload a file (reply to file)\n"
        "• /auto_del - Set auto-delete time\n"
        "• /stats - View bot statistics\n"
        "• /broadcast - Broadcast message to users\n\n"
        "💡 **Auto-Delete Feature:**\n"
        "Files are automatically deleted after the set time.\n"
        "Use /auto_del to change the deletion time."
    )
    await message.reply_text(help_text, reply_markup=button_manager.help_button())

@Client.on_message(filters.command("about"))
async def about_command(client: Client, message: Message):
    about_text = config.Messages.ABOUT_TEXT.format(
        bot_name=config.BOT_NAME,
        version=config.BOT_VERSION
    )
    await message.reply_text(about_text, reply_markup=button_manager.about_button())
