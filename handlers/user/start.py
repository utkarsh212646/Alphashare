from pyrogram import Client, filters
from pyrogram.types import Message
from database import Database
from utils import ButtonManager
import config
import asyncio
from ..utils.message_delete import schedule_message_deletion

db = Database()
button_manager = ButtonManager()

@Client.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await db.add_user(message.from_user.id, message.from_user.username)
    
    if len(message.command) > 1:
        command_arg = message.command[1]
        
        if not await button_manager.check_force_sub(client, message.from_user.id):
            await message.reply_text(
                "**⚠️ You must join our channel to use this bot!**\n\n"
                "Please join Our Forcesub Channel and try again.",
                reply_markup=button_manager.force_sub_button()
            )
            return
        
        # Handle batch downloads
        if command_arg.startswith("batch_"):
            batch_id = command_arg.replace("batch_", "")
            batch_data = await db.get_batch(batch_id)
            
            if not batch_data:
                await message.reply_text("❌ Batch not found or has been deleted!")
                return
            
            # Send batch info message
            info_msg = await message.reply_text(
                f"📦 **Batch Download Started**\n\n"
                f"• Total Files: `{batch_data['total_files']}`\n"
                f"• Description: {batch_data.get('description', 'Not provided')}\n\n"
                f"⬇️ Downloading files...",
                parse_mode="markdown"
            )
            
            # Send all files in batch
            success_count = 0
            for file_data in batch_data['files']:
                try:
                    msg = await client.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=config.DB_CHANNEL_ID,
                        message_id=file_data["message_id"]
                    )
                    
                    success_count += 1
                    
                    # Handle auto-delete if enabled
                    if file_data.get("auto_delete"):
                        delete_time = file_data.get("auto_delete_time")
                        if delete_time:
                            asyncio.create_task(schedule_message_deletion(
                                client, file_data["uuid"], message.chat.id, [msg.id], delete_time
                            ))
                    
                    await asyncio.sleep(1)  # Prevent flood
                except Exception as e:
                    print(f"Error sending batch file: {str(e)}")
                    continue
            
            # Update batch download counter
            await db.increment_batch_downloads(batch_id)
            
            # Send completion message
            await info_msg.edit_text(
                f"✅ **Batch Download Completed**\n\n"
                f"• Successfully sent: {success_count}/{batch_data['total_files']} files\n"
                f"• Description: {batch_data.get('description', 'Not provided')}\n\n"
                f"💡 **Note:** Save important files to your saved messages!",
                parse_mode="markdown"
            )
            return
            
        # Handle single file downloads
        file_data = await db.get_file(command_arg)
        if not file_data:
            await message.reply_text("❌ File not found or has been deleted!")
            return
        
        try:
            msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=config.DB_CHANNEL_ID,
                message_id=file_data["message_id"]
            )
            await db.increment_downloads(command_arg)
            await db.update_file_message_id(command_arg, msg.id, message.chat.id)
            
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
                        client, command_arg, message.chat.id, [msg.id, info_msg.id], delete_time
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
