from pyrogram import Client, filters
from pyrogram.types import Message
from database import Database
from utils import ButtonManager
import config
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db = Database()
button_manager = ButtonManager()

try:
    from utils.message_delete import schedule_message_deletion
except ImportError:
    try:
        from ..utils.message_delete import schedule_message_deletion
    except ImportError:
        async def schedule_message_deletion(client, file_id, chat_id, message_ids, delete_time):
            logger.warning(f"Message deletion module not found. Using fallback for file {file_id}")
            await asyncio.sleep(delete_time * 60)
            for msg_id in message_ids:
                try:
                    await client.delete_messages(chat_id, msg_id)
                except Exception as e:
                    logger.error(f"Failed to delete message: {e}")

@Client.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    logger.info(f"Start command received from user {message.from_user.id} with args: {message.command}")
    
    try:
        await db.add_user(message.from_user.id, message.from_user.username)
    except Exception as e:
        logger.error(f"Failed to add user to database: {e}")
    
    if len(message.command) > 1:
        command_arg = message.command[1]
        logger.info(f"Processing start parameter: {command_arg}")
        
        if hasattr(button_manager, 'check_force_sub'):
            try:
                if not await button_manager.check_force_sub(client, message.from_user.id):
                    await message.reply_text(
                        "⚠️ You must join our channel to use this bot!\n\nPlease join Our Forcesub Channel and try again.",
                        reply_markup=button_manager.force_sub_button()
                    )
                    return
            except Exception as e:
                logger.error(f"Force subscription check failed: {e}")
        
        if command_arg.startswith("batch_"):
            batch_id = command_arg.replace("batch_", "")
            logger.info(f"Processing batch download with ID: {batch_id}")
            
            try:
                batch_data = await db.get_batch(batch_id)
                
                if not batch_data:
                    await message.reply_text("❌ Batch not found or has been deleted!")
                    return
                
                status_msg = await message.reply_text(f"🚀 Starting batch transfer...\n📦 Total files: {len(batch_data['files'])}")
                
                success_count = 0
                failed_count = 0
                sent_messages = []
                
                logger.info(f"Found {len(batch_data['files'])} files in batch {batch_id}")
                
                for file_data in batch_data['files']:
                    try:
                        logger.info(f"Attempting to send file with message_id: {file_data.get('message_id')}")
                        
                        if not file_data.get('message_id'):
                            logger.error("Missing message_id in file_data")
                            failed_count += 1
                            continue
                        
                        copied_msg = await client.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=config.DB_CHANNEL_ID,
                            message_id=file_data['message_id']
                        )
                        
                        if copied_msg:
                            success_count += 1
                            sent_messages.append(copied_msg.id)
                            
                            if success_count % 2 == 0 or success_count == len(batch_data['files']):
                                try:
                                    await status_msg.edit_text(
                                        f"📤 Sending files: {success_count}/{len(batch_data['files'])}\n"
                                        f"✅ Successfully sent: {success_count}\n"
                                        f"❌ Failed: {failed_count}"
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to update status: {e}")
                        
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Error sending file: {str(e)}")
                        failed_count += 1
                        continue
                
                try:
                    await db.increment_batch_downloads(batch_id)
                except Exception as e:
                    logger.error(f"Failed to increment batch downloads: {e}")
                
                final_text = (
                    f"✅ Batch Files Sent Successfully\n\n"
                    f"• Total Files: {len(batch_data['files'])}\n"
                    f"• Successfully Sent: {success_count}\n"
                )
                
                if failed_count > 0:
                    final_text += f"• Failed to Send: {failed_count}\n"
                
                if batch_data.get('description'):
                    final_text += f"• Description: {batch_data['description']}\n"
                
                auto_delete_time = config.DEFAULT_DELETE_TIME
                if sent_messages:
                    final_text += f"\n⏳ Auto-Delete: Files will be deleted in {auto_delete_time} minutes"
                    asyncio.create_task(schedule_message_deletion(
                        client,
                        f"batch_{batch_id}",
                        message.chat.id,
                        sent_messages + [status_msg.id],
                        auto_delete_time
                    ))
                
                await status_msg.edit_text(final_text)
                logger.info(f"Batch {batch_id} completed. Success: {success_count}, Failed: {failed_count}")
                
            except Exception as e:
                error_msg = f"Error processing batch: {str(e)}"
                logger.error(error_msg)
                await message.reply_text(f"❌ {error_msg}")
            return
        
        try:
            file_data = await db.get_file(command_arg)
            if not file_data:
                await message.reply_text("❌ File not found or has been deleted!")
                return
            
            msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=config.DB_CHANNEL_ID,
                message_id=file_data["message_id"]
            )
            
            await db.increment_downloads(command_arg)
            await db.update_file_message_id(command_arg, msg.id, message.chat.id)
            
            if file_data.get("auto_delete"):
                delete_time = file_data.get("auto_delete_time", config.DEFAULT_DELETE_TIME)
                if delete_time:
                    info_msg = await msg.reply_text(
                        f"⏳ File Auto-Delete Information\n\n"
                        f"This file will be automatically deleted in {delete_time} minutes\n"
                        f"• Delete Time: {delete_time} minutes\n"
                        f"• Time Left: {delete_time} minutes\n\n"
                        f"💡 Save this file to your saved messages before it's deleted!"
                    )
                    
                    asyncio.create_task(schedule_message_deletion(
                        client,
                        command_arg,
                        message.chat.id,
                        [msg.id, info_msg.id],
                        delete_time
                    ))
                    
        except Exception as e:
            logger.error(f"Single file download failed: {e}")
            await message.reply_text(f"❌ Error: {str(e)}")
        return
    
    try:
        await message.reply_text(
            config.Messages.START_TEXT.format(
                bot_name=config.BOT_NAME,
                user_mention=message.from_user.mention
            ),
            reply_markup=button_manager.start_button()
        )
    except Exception as e:
        logger.error(f"Failed to send welcome message: {e}")
        await message.reply_text(
            f"👋 Welcome to the bot, {message.from_user.mention}!\n\n"
            f"Use this bot to store and share your files."
        )
