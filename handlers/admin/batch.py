from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from config import ADMIN_IDS, DB_CHANNEL_ID
import uuid
from datetime import datetime

# Store ongoing batch sessions
batch_sessions = {}

class BatchSession:
    def __init__(self, user_id: int):
        self.batch_id = str(uuid.uuid4())
        self.user_id = user_id
        self.files = []
        self.start_time = datetime.utcnow()
        self.file_count = 0

@Client.on_message(filters.command("batch") & filters.private)
async def start_batch(client: Client, message: Message):
    """Start a new batch upload session"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.reply_text("⚠️ Only admins can use this command!")
        return
    
    if user_id in batch_sessions:
        await message.reply_text(
            "❗️ You already have an active batch session.\n"
            "Please complete it with /done or cancel it with /cancel first."
        )
        return
    
    batch_sessions[user_id] = BatchSession(user_id)
    
    await message.reply_text(
        "📦 **Batch Upload Mode Started!**\n\n"
        "• Send me the files one by one\n"
        "• I'll forward them to the DB channel\n"
        "• Use /done when finished\n"
        "• Use /cancel to cancel\n\n"
        "Status: Ready to receive files ✅"
    )

@Client.on_message(filters.command(["done", "cancel"]) & filters.private)
async def handle_batch_commands(client: Client, message: Message):
    """Handle /done and /cancel commands"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        await message.reply_text("❌ No active batch session found!")
        return
    
    session = batch_sessions[user_id]
    command = message.command[0]
    
    if command == "cancel":
        del batch_sessions[user_id]
        await message.reply_text("🚫 Batch upload cancelled!")
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
            
            time_taken = (datetime.utcnow() - session.start_time).seconds
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Download All Files", url=batch_link)]
            ])
            
            await message.reply_text(
                f"✅ **Batch Upload Success!**\n\n"
                f"📊 Files: {len(session.files)}\n"
                f"⏱ Time: {time_taken} seconds\n\n"
                f"Share this link to access all files:",
                reply_markup=keyboard
            )
            
            del batch_sessions[user_id]
            
        except Exception as e:
            await message.reply_text(f"❌ Database Error: {str(e)}")
            return

@Client.on_message(filters.private & filters.media)
async def handle_batch_file(client: Client, message: Message):
    """Handle incoming files during batch upload"""
    user_id = message.from_user.id
    
    if user_id not in batch_sessions:
        return
    
    session = batch_sessions[user_id]
    session.file_count += 1
    
    try:
        # Forward file to database channel
        forwarded = await message.forward(DB_CHANNEL_ID)
        
        # Get file info
        file_data = {
            "file_id": message.media.file_id,
            "file_name": getattr(message.media, "file_name", f"File_{session.file_count}"),
            "file_size": getattr(message.media, "file_size", 0),
            "file_type": message.media.__class__.__name__.lower(),
            "uuid": str(uuid.uuid4()),
            "uploader_id": user_id,
            "message_id": forwarded.id,
            "batch_id": session.batch_id
        }
        
        # Add file to session
        session.files.append(file_data)
        
        # Send acknowledgment with ordinal number
        ordinal = lambda n: str(n) + ("th" if 4<=n%100<=20 else {1:"st",2:"nd",3:"rd"}.get(n%10, "th"))
        
        await message.reply_text(
            f"✅ {ordinal(session.file_count)} file received\n"
            f"📁 Name: {file_data['file_name']}"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
