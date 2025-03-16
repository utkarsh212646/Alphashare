from pyrogram import Client, filters
from pyrogram.types import Message
from database import Database
from utils import ButtonManager
import config
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize database and button manager
db = Database()
button_manager = ButtonManager()

# Import message deletion utility with error handling
try:
    from utils.message_delete import schedule_message_deletion
except ImportError:
    # Try the alternative import path
    try:
        from ..utils.message_delete import schedule_message_deletion
    except ImportError:
        # Define a fallback function if import fails
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
    """Handle the /start command and its deep linking parameters"""
    # Log the start command received
    logger.info(f"Start command received from user {message.from_user.id} with args: {message.command}")
    
    # Add user to database
    try:
        await db.add_user(message.from_user.id, message.from_user.username)
    except Exception as e:
        logger.error(f"Failed to add user to database: {e}")
    
    # Check if there's a parameter after /start
    if len(message.command) > 1:
        command_arg = message.command[1]
        logger.info(f"Processing start parameter: {command_arg}")
        
        # Check for force subscription if required
        if hasattr(button_manager, 'check_force_sub'):
            try:
                if not await button_manager.check_force_sub(client, message.from_user.id):
                    await message.reply_text(
                        "⚠️ You must join our channel to use this bot!\n\n"
                        "Please join Our Forcesub Channel and try again.",
                        reply_markup=button_manager.force_sub_button()
                    )
                    return
            except Exception as e:
                logger.error(f"Force subscription check failed: {e}")
        
        # Handle batch downloads
        if command_arg.startswith("batch_"):
            batch_id = command_arg.replace("batch_", "")
            logger.info(f"Processing batch download with ID: {batch_id}")
            
            try:
                batch_data = await db.get_batch(batch_id)
                
                if not batch_data:
                    await message.reply_text("❌ Batch not found or has been deleted!")
                    return
                
                # Send batch info message without parse mode
                info_msg = await message.reply_text(
                    f"📦 Batch Download Started\n\n"
                    f"• Total Files: {batch_data['total_files']}\n"
                    f"• Description: {batch_data.get('description', 'Not provided')}\n\n"
                    f"⬇️ Downloading files..."
                )
                
                # Send all files in batch
                success_count = 0
                failed_count = 0
                
                for index, file_data in enumerate(batch_data['files'], 1):
                    try:
                        # Add progress indicator
                        if index % 5 == 0:
                            await info_msg.edit_text(
                                f"📦 Batch Download in Progress\n\n"
                                f"• Processing: {index}/{batch_data['total_files']} files\n"
                                f"• Successful: {success_count}\n"
                                f"• Failed: {failed_count}\n\n"
                                f"⏳ Please wait..."
                            )
                        
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
                                    client, 
                                    file_data.get("uuid", f"batch_{batch_id}_{index}"), 
                                    message.chat.id, 
                                    [msg.id], 
                                    delete_time
                                ))
                        
                        # Add a small delay to prevent flood
                        await asyncio.sleep(1.5)  # Increased delay to prevent rate limiting
                        
                    except Exception as e:
                        logger.error(f"Error sending batch file {index}: {str(e)}")
                        failed_count += 1
                        continue
                
                # Update batch download counter
                try:
                    await db.increment_batch_downloads(batch_id)
                except Exception as e:
                    logger.error(f"Failed to increment batch downloads: {e}")
                
                # Send completion message without parse mode
                completion_text = (
                    f"✅ Batch Download Completed\n\n"
                    f"• Total Files: {batch_data['total_files']}\n"
                    f"• Successfully Sent: {success_count}\n"
                    f"• Failed: {failed_count}\n"
                    f"• Description: {batch_data.get('description', 'Not provided')}\n\n"
                )
                
                if failed_count > 0:
                    completion_text += "⚠️ Some files failed to send. Please try again later.\n\n"
                
                completion_text += "💡 Note: Save important files to your saved messages!"
                
                await info_msg.edit_text(completion_text)
                
            except Exception as e:
                logger.error(f"Batch download failed: {e}")
                await message.reply_text(f"❌ Error processing batch: {str(e)}")
            return
        
        # Handle single file downloads
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
                delete_time = file_data.get("auto_delete_time")
                if delete_time:
                    info_msg = await msg.reply_text(
                        f"⏳ File Auto-Delete Information\n\n"
                        f"This file will be automatically deleted in {delete_time} minutes\n"
                        f"• Delete Time: {delete_time} minutes\n"
                        f"• Time Left: {delete_time} minutes\n\n"
                        f"💡 Save this file to your saved messages before it's deleted!"
                    )
                    
                    asyncio.create_task(schedule_message_deletion(
                        client, command_arg, message.chat.id, [msg.id, info_msg.id], delete_time
                    ))
                    
        except Exception as e:
            logger.error(f"Single file download failed: {e}")
            await message.reply_text(f"❌ Error: {str(e)}")
        return
    
    # If no parameter is provided, send the welcome message
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
        # Fallback welcome message
        await message.reply_text(
            f"👋 Welcome to the bot, {message.from_user.mention}!\n\n"
            f"Use this bot to store and share your files."
            )
