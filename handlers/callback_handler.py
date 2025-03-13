from pyrogram import Client
from database import Database
from utils import ButtonManager

from .admin_commands import (
    auto_delete_command,
    broadcast_command,
    stats_command,
    upload_command
)
from .user_commands import (
    start_command,
    help_command,
    about_command
)
from .utils import schedule_message_deletion

db = Database()
button_manager = ButtonManager()

def register_handlers(app: Client):
    app.on_message()(auto_delete_command)
    app.on_message()(broadcast_command)
    app.on_message()(stats_command)
    app.on_message()(upload_command)
    app.on_message()(start_command)
    app.on_message()(help_command)
    app.on_message()(about_command)
