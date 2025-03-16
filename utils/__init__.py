import os
import math
from typing import Union
from pyrogram.types import Message
from PIL import Image

from .button_manager import ButtonManager
from .progress import progress_callback, humanbytes, TimeFormatter
from .admin_check import is_admin

# Utility Functions
def format_bytes(size: Union[int, float]) -> str:
    if not size:
        return "0B"
    
    size = float(size)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    return f"{size:.2f}{units[unit_index]}"

def get_file_type(message: Message) -> str:
    if message.document:
        return "document"
    elif message.video:
        return "video"
    elif message.audio:
        return "audio"
    elif message.photo:
        return "photo"
    elif message.voice:
        return "voice"
    elif message.video_note:
        return "video_note"
    elif message.sticker:
        return "sticker"
    elif message.animation:
        return "animation"
    else:
        return None

async def generate_thumbnail(message: Message) -> str:
    if not message.document or not message.document.thumbs:
        return None
    
    try:
        thumb = message.document.thumbs[0]
        file_path = f"downloads/{message.document.file_id}.jpg"
        
        if not os.path.exists("downloads"):
            os.makedirs("downloads")
        
        await message.download_media(
            file_name=file_path,
            thumb=-1
        )
        
        # Optimize thumbnail
        try:
            img = Image.open(file_path)
            img.thumbnail((320, 320))
            img.save(file_path, "JPEG", quality=95)
        except Exception as e:
            print(f"Thumbnail optimization failed: {e}")
        
        return file_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None

def get_file_name(message: Message) -> str:
    try:
        if message.document:
            return message.document.file_name or "document"
        elif message.video:
            return message.video.file_name or "video"
        elif message.audio:
            return message.audio.file_name or "audio"
        elif message.voice:
            return f"voice_{message.date.strftime('%Y%m%d_%H%M%S')}"
        elif message.photo:
            return f"photo_{message.date.strftime('%Y%m%d_%H%M%S')}.jpg"
        elif message.sticker:
            return f"sticker_{message.date.strftime('%Y%m%d_%H%M%S')}"
        elif message.animation:
            return message.animation.file_name or "animation"
        else:
            return f"file_{message.date.strftime('%Y%m%d_%H%M%S')}"
    except:
        return f"file_{message.date.strftime('%Y%m%d_%H%M%S')}"

def get_file_size(message: Message) -> int:
    try:
        if message.document:
            return message.document.file_size
        elif message.video:
            return message.video.file_size
        elif message.audio:
            return message.audio.file_size
        elif message.photo:
            return max([p.file_size for p in message.photo.sizes])
        elif message.voice:
            return message.voice.file_size
        elif message.sticker:
            return message.sticker.file_size
        elif message.animation:
            return message.animation.file_size
        else:
            return 0
    except:
        return 0

def clean_filename(filename: str) -> str:
    if not filename:
        return "file"
        
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    
    filename = filename.strip()
    if len(filename) > 60:
        name, ext = os.path.splitext(filename)
        filename = name[:56] + "..." + ext if ext else name[:60]
    
    return filename or "file"

def get_media_info(message: Message) -> dict:
    try:
        media_types = {
            "document": message.document,
            "video": message.video,
            "audio": message.audio,
            "photo": message.photo,
            "voice": message.voice,
            "video_note": message.video_note,
            "sticker": message.sticker,
            "animation": message.animation
        }
        
        for media_type, media in media_types.items():
            if media:
                return {
                    "type": media_type,
                    "file_id": getattr(media, "file_id", None),
                    "file_name": get_file_name(message),
                    "file_size": get_file_size(message),
                    "mime_type": getattr(media, "mime_type", None),
                    "duration": getattr(media, "duration", None),
                    "width": getattr(media, "width", None),
                    "height": getattr(media, "height", None)
                }
        return None
    except Exception as e:
        print(f"Error getting media info: {e}")
        return None

async def process_media(message: Message) -> dict:
    try:
        media_info = get_media_info(message)
        if not media_info:
            return None
            
        media_info["file_name"] = clean_filename(media_info["file_name"])
        media_info["formatted_size"] = format_bytes(media_info["file_size"])
        
        if message.document and message.document.thumbs:
            media_info["thumbnail"] = await generate_thumbnail(message)
            
        return media_info
    except Exception as e:
        print(f"Error processing media: {e}")
        return None

class ButtonManager:
    @staticmethod
    def start_button():
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Help", callback_data="help"),
                InlineKeyboardButton("About", callback_data="about")
            ],
            [
                InlineKeyboardButton("Channel", url="https://t.me/thealphabotz"),
                InlineKeyboardButton("Support", url="https://t.me/Alphabotzchat")
            ]
        ])

# Expose functions for external imports
__all__ = [
    'ButtonManager',
    'progress_callback',
    'humanbytes',
    'TimeFormatter',
    'is_admin',
    'format_bytes',
    'get_file_type',
    'generate_thumbnail',
    'get_file_name',
    'get_file_size',
    'clean_filename',
    'get_media_info',
    'process_media'
    ]
