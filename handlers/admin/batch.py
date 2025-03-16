from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from config import ADMIN_IDS
import uuid
import asyncio
from datetime import datetime

# Store ongoing batch sessions
batch_sessions = {}

class BatchSession:
    def __init__(self, user_id: int, batch_id: str):
        self.user_id = user_id
        self.batch_id = batch_id
        self.files = []
        self.status_message = None
        self.start_time = datetime.utcnow()
        self.description = ""

@Client.on_message(filters.command("batch") & filters.user(ADMIN_IDS))
async def start_batch(client: Client, message: Message):
    """Start a new batch upload session"""
    user_id = message.from_user.id
    
    if user_id in batch_sessions:
        await message.reply_text(
            "❗️ You already have an active batch session.\n"
            "Please complete it with /done or cancel it with /cancel_batch first."
        )
        return
    
    # Create new batch session
    batch_id = str(uuid.uuid4())
    batch_sessions[user_id] = BatchSession(user_id, batch_id)
    
    # Send instructions
    await message.reply_text(
        "📦 <b>Batch Upload Mode Started!</b>\n\n"
        "• Send me files one by one\n"
        "• Use /adddesc to add a description to this batch\n"
        "• Use /done when you finish uploading\n"
        "• Use /cancel_batch to cancel this session\n\n"
        "<b>Current Status:</b>\n"
        "Files received: 0",
        parse_mode="html"
    )

@Client.on_message(filters.command("adddesc") & filters.user(ADMIN_IDS))
async def add_batch_description(client: Client, message: Message):
    """Add description to current batch"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        await message.reply_text("❌ No active batch session found!")
        return
    
    # Get description from command
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide a description!\n/adddesc your description here")
        return
    
    description = " ".join(message.command[1:])
    batch_sessions[user_id].description = description
    
    await message.reply_text(
        "✅ <b>Batch description added successfully!</b>\n\n"
        f"Description: {description}",
        parse_mode="html"
    )

@Client.on_message(filters.command("done") & filters.user(ADMIN_IDS))
async def finish_batch(client: Client, message: Message):
    """Complete the batch upload session"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        await message.reply_text("❌ No active batch session found!")
        return
    
    session = batch_sessions[user_id]
    
    if len(session.files) == 0:
        await message.reply_text("❌ No files were uploaded in this batch!")
        del batch_sessions[user_id]
        return
    
    # Get bot username for link generation
    bot_username = (await client.get_me()).username
    batch_link = f"https://t.me/{bot_username}?start=batch_{session.batch_id}"
    
    # Store batch in database
    db = Database()
    try:
        await db.add_batch({
            "batch_id": session.batch_id,
            "created_by": user_id,
            "total_files": len(session.files),
            "description": session.description
        })
    except Exception as e:
        await message.reply_text(f"❌ Error saving batch: {str(e)}")
        return
    
    # Clean up status message
    if session.status_message:
        try:
            await session.status_message.delete()
        except:
            pass
    
    # Send completion message
    duration = datetime.utcnow() - session.start_time
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Batch Link", url=batch_link)]
    ])
    
    await message.reply_text(
        f"✅ <b>Batch Upload Completed!</b>\n\n"
        f"• Total Files: <code>{len(session.files)}</code>\n"
        f"• Batch ID: <code>{session.batch_id}</code>\n"
        f"• Time Taken: <code>{duration.seconds}s</code>\n"
        f"• Description: {session.description or 'Not provided'}\n\n"
        f"Share this link to access all files:",
        reply_markup=keyboard,
        parse_mode="html"
    )
    
    # Clear session
    del batch_sessions[user_id]

@Client.on_message(filters.command("cancel_batch") & filters.user(ADMIN_IDS))
async def cancel_batch(client: Client, message: Message):
    """Cancel the current batch upload session"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        await message.reply_text("❌ No active batch session found!")
        return
    
    # Clean up status message if exists
    session = batch_sessions[user_id]
    if session.status_message:
        try:
            await session.status_message.delete()
        except:
            pass
    
    del batch_sessions[user_id]
    await message.reply_text("🚫 Batch upload session cancelled!")

@Client.on_message(filters.user(ADMIN_IDS) & filters.media)
async def handle_batch_file(client: Client, message: Message):
    """Handle incoming files during batch upload"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        return
    
    session = batch_sessions[user_id]
    
    # Get file info
    try:
        file_data = {
            "file_id": message.media.file_id if hasattr(message.media, "file_id") else None,
            "file_name": getattr(message.media, "file_name", f"File_{len(session.files) + 1}"),
            "file_size": getattr(message.media, "file_size", 0),
            "file_type": message.media.__class__.__name__.lower(),
            "uuid": str(uuid.uuid4()),
            "uploader_id": user_id,
            "message_id": message.id,
            "batch_id": session.batch_id
        }
        
        # Store file in database
        db = Database()
        await db.add_file(file_data)
        
        # Add file to session
        session.files.append(file_data)
        
        # Update status message
        status_text = (
            f"📦 <b>Batch Upload in Progress</b>\n\n"
            f"• Files Received: <code>{len(session.files)}</code>\n"
            f"• Last File: <code>{file_data['file_name']}</code>\n"
            f"• Description: {session.description or 'Not set'}\n\n"
            f"Send more files or use:\n"
            f"• /done - Complete batch\n"
            f"• /adddesc - Add description\n"
            f"• /cancel_batch - Cancel session"
        )
        
        try:
            if session.status_message:
                await session.status_message.edit_text(status_text, parse_mode="html")
            else:
                session.status_message = await message.reply_text(status_text, parse_mode="html")
        except Exception as e:
            print(f"Error updating status: {str(e)}")
            
    except Exception as e:
        await message.reply_text(f"❌ Error processing file: {str(e)}")

# Last updated: 2025-03-16 06:38:41
# Updated by: utkarsh212646
