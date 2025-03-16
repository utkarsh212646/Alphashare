from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import Database
from datetime import datetime
import logging
import uuid
import asyncio
import os
from typing import Dict, List, Optional, Union
from utils import format_bytes, get_file_type, generate_thumbnail
import config
from pyrogram.errors import FloodWait, MessageNotModified
from utils.decorators import admin_check

logger = logging.getLogger(__name__)
db = Database()

class BatchSession:
    def __init__(self):
        self.batch_id = str(uuid.uuid4())
        self.files = []
        self.start_time = datetime.utcnow()
        self.description = ""
        self.current_message = None
        self.auto_delete = False
        self.auto_delete_time = config.DEFAULT_DELETE_TIME

batch_sessions: Dict[int, BatchSession] = {}

@Client.on_message(filters.command("batch") & filters.private & admin_check)
async def start_batch(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in batch_sessions:
        await message.reply_text("❌ You already have an active batch session!\nUse /cancel to stop the current session.")
        return
    
    batch_sessions[user_id] = BatchSession()
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Add Description", callback_data="batch_add_desc"),
            InlineKeyboardButton("Toggle Auto-Delete", callback_data="batch_toggle_delete")
        ],
        [
            InlineKeyboardButton("✅ Done", callback_data="batch_done"),
            InlineKeyboardButton("❌ Cancel", callback_data="batch_cancel")
        ]
    ])
    
    batch_sessions[user_id].current_message = await message.reply_text(
        "📦 Batch Upload Mode Started!\n\n"
        "• Send me the files one by one\n"
        "• I'll forward them to the DB channel\n"
        "• Use buttons below when finished\n\n"
        "Status: Ready to receive files ✅\n"
        "Auto-Delete: ❌ Disabled\n"
        "Files: 0",
        reply_markup=keyboard
    )

async def update_batch_message(session: BatchSession, message: Message):
    try:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Add Description", callback_data="batch_add_desc"),
                InlineKeyboardButton("Toggle Auto-Delete", callback_data="batch_toggle_delete")
            ],
            [
                InlineKeyboardButton("✅ Done", callback_data="batch_done"),
                InlineKeyboardButton("❌ Cancel", callback_data="batch_cancel")
            ]
        ])
        
        text = (
            "📦 Batch Upload Mode\n\n"
            f"• Files Received: {len(session.files)}\n"
            f"• Auto-Delete: {'✅ Enabled' if session.auto_delete else '❌ Disabled'}\n"
        )
        
        if session.auto_delete:
            text += f"• Delete After: {session.auto_delete_time} minutes\n"
            
        if session.description:
            text += f"\nDescription: {session.description}\n"
            
        text += "\nStatus: Receiving files ✅"
        
        await message.edit_text(text, reply_markup=keyboard)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Failed to update batch message: {e}")

@Client.on_callback_query(filters.regex('^batch_'))
async def handle_batch_callbacks(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if user_id not in batch_sessions:
        await callback_query.answer("No active batch session!", show_alert=True)
        return
    
    session = batch_sessions[user_id]
    
    if data == "batch_add_desc":
        await callback_query.message.reply_text(
            "📝 Please send the description for this batch.\n"
            "Send /cancel to cancel."
        )
        session.awaiting_description = True
        
    elif data == "batch_toggle_delete":
        session.auto_delete = not session.auto_delete
        await update_batch_message(session, callback_query.message)
        await callback_query.answer(
            f"Auto-delete {'enabled' if session.auto_delete else 'disabled'}!",
            show_alert=True
        )
        
    elif data == "batch_done":
        if len(session.files) == 0:
            await callback_query.answer("❌ No files in batch!", show_alert=True)
            return
            
        await finish_batch(client, callback_query.message, user_id)
        
    elif data == "batch_cancel":
        del batch_sessions[user_id]
        await callback_query.message.edit_text("❌ Batch upload cancelled!")
        
    await callback_query.answer()

async def finish_batch(client: Client, message: Message, user_id: int):
    session = batch_sessions[user_id]
    
    try:
        batch_data = {
            "batch_id": session.batch_id,
            "created_by": user_id,
            "total_files": len(session.files),
            "files": session.files,
            "creation_time": datetime.utcnow(),
            "downloads": 0,
            "description": session.description,
            "auto_delete": session.auto_delete,
            "auto_delete_time": session.auto_delete_time
        }
        
        await db.batches.insert_one(batch_data)
        
        bot_username = (await client.get_me()).username
        batch_link = f"https://t.me/{bot_username}?start=batch_{session.batch_id}"
        
        completion_text = (
            f"✅ Batch Upload Success!\n\n"
            f"📊 Files: {len(session.files)}\n"
            f"⏱ Time: {(datetime.utcnow() - session.start_time).seconds} seconds\n"
        )
        
        if session.description:
            completion_text += f"\n📝 Description: {session.description}\n"
            
        if session.auto_delete:
            completion_text += f"\n⏳ Auto-Delete: {session.auto_delete_time} minutes\n"
            
        completion_text += f"\nShare this link to access all files:\n{batch_link}"
        
        await message.edit_text(completion_text)
        logger.info(f"Created batch {session.batch_id} with {len(session.files)} files")
        
    except Exception as e:
        logger.error(f"Failed to create batch: {e}")
        await message.edit_text("❌ Failed to create batch")
    
    finally:
        del batch_sessions[user_id]

@Client.on_message(filters.private & ~filters.command(["batch", "cancel"]) & admin_check)
async def handle_batch_file(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        return
        
    session = batch_sessions[user_id]
    
    if hasattr(session, 'awaiting_description') and session.awaiting_description:
        if message.text == "/cancel":
            session.awaiting_description = False
            await message.reply_text("❌ Description cancelled!")
            return
            
        session.description = message.text
        session.awaiting_description = False
        await message.reply_text("✅ Description added!")
        await update_batch_message(session, session.current_message)
        return
    
    if not message.media:
        return
    
    try:
        file_type = get_file_type(message)
        if not file_type:
            await message.reply_text("❌ Unsupported file type!")
            return
            
        forwarded = await message.forward(chat_id=config.DB_CHANNEL_ID)
        
        file_data = {
            "message_id": forwarded.id,
            "file_name": getattr(message.document, "file_name", None) or f"file_{len(session.files) + 1}",
            "file_size": getattr(message.document, "file_size", 0),
            "mime_type": getattr(message.document, "mime_type", ""),
            "file_type": file_type,
            "upload_time": datetime.utcnow()
        }
        
        if message.document and message.document.thumbs:
            file_data["thumbnail"] = await generate_thumbnail(message)
        
        session.files.append(file_data)
        
        await message.reply_text(
            f"✅ File received ({len(session.files)})\n"
            f"📁 Name: {file_data['file_name']}\n"
            f"📊 Size: {format_bytes(file_data['file_size'])}"
        )
        
        await update_batch_message(session, session.current_message)
        
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Failed to process file: {e}")
        await message.reply_text("❌ Failed to process file")

@Client.on_message(filters.command("cancel") & filters.private & admin_check)
async def cancel_batch(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        await message.reply_text("❌ No active batch session!")
        return
        
    del batch_sessions[user_id]
    await message.reply_text("❌ Batch upload cancelled!")
