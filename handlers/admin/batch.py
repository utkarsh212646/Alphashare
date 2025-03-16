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
        self.file_count = 0

@Client.on_message(filters.command("batch"))
async def start_batch(client: Client, message: Message):
    """Start a new batch upload session"""
    user_id = message.from_user.id
    
    if user_id in batch_sessions:
        await message.reply_text(
            "❗️ You already have an active batch session.\n"
            "Please complete it with /done or cancel it with /cancel first."
        )
        return
    
    # Create new batch session
    batch_id = str(uuid.uuid4())
    batch_sessions[user_id] = BatchSession(user_id, batch_id)
    
    # Send instructions
    await message.reply_text(
        "🎯 **Batch Mode Activated! Send your files now.**\n\n"
        "📤 Send me the files you want to include in this batch.\n"
        "📝 I'll acknowledge each file as it's uploaded.\n\n"
        "Commands:\n"
        "• /done - Complete batch and get link\n"
        "• /cancel - Cancel batch upload\n\n"
        "Current Status: Waiting for files...",
        parse_mode="html"
    )

@Client.on_message(filters.command(["done", "cancel"]))
async def handle_batch_commands(client: Client, message: Message):
    """Handle /done and /cancel commands"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        await message.reply_text("❌ No active batch session found!\nUse /batch to start one.")
        return
    
    session = batch_sessions[user_id]
    command = message.command[0]
    
    if command == "cancel":
        del batch_sessions[user_id]
        await message.reply_text("🚫 Batch upload cancelled successfully!")
        return
    
    if command == "done":
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
                "files": session.files,
                "creation_time": session.start_time.isoformat()
            })
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Download All Files", url=batch_link)]
            ])
            
            await message.reply_text(
                f"✅ **Batch Upload Completed!**\n\n"
                f"📊 Total Files: {len(session.files)}\n"
                f"⏱ Time Taken: {(datetime.utcnow() - session.start_time).seconds}s\n\n"
                f"Click the button below to access all files:",
                reply_markup=keyboard,
                parse_mode="html"
            )
            
            del batch_sessions[user_id]
            
        except Exception as e:
            await message.reply_text(f"❌ Error saving batch: {str(e)}")
            return

@Client.on_message(filters.media & ~filters.command)
async def handle_batch_file(client: Client, message: Message):
    """Handle incoming files during batch upload"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        return
    
    session = batch_sessions[user_id]
    session.file_count += 1
    
    # Get file info
    try:
        file_data = {
            "file_id": message.media.file_id if hasattr(message.media, "file_id") else None,
            "file_name": getattr(message.media, "file_name", f"File_{session.file_count}"),
            "file_size": getattr(message.media, "file_size", 0),
            "file_type": message.media.__class__.__name__.lower(),
            "uuid": str(uuid.uuid4()),
            "uploader_id": user_id,
            "message_id": message.id,
            "batch_id": session.batch_id
        }
        
        # Store file info in session
        session.files.append(file_data)
        
        # Send acknowledgment
        ordinal_suffix = lambda n: str(n) + ("th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))
        await message.reply_text(
            f"✅ {ordinal_suffix(session.file_count)} file uploaded.\n"
            f"📁 Name: {file_data['file_name']}\n"
            f"💾 Size: {file_data['file_size']} bytes"
        )
            
    except Exception as e:
        await message.reply_text(f"❌ Error processing file: {str(e)}")
