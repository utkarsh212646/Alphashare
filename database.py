from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import config
from typing import Dict, Any, Optional, List


class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(config.MONGO_URI)
        self.db = self.client[config.DATABASE_NAME]
        self.files = self.db.files
        self.users = self.db.users
        self.batches = self.db.batches  # New collection for batches
        print("Database Connected Successfully!")

    async def add_file(self, file_data: Dict[str, Any]) -> str:
        file_doc = {
            "file_id": file_data["file_id"],
            "file_name": file_data["file_name"],
            "file_size": file_data["file_size"],
            "file_type": file_data["file_type"],
            "uuid": file_data["uuid"],
            "uploader_id": file_data["uploader_id"],
            "message_id": file_data["message_id"],
            "downloads": 0,
            "auto_delete": file_data.get("auto_delete", False),
            "auto_delete_time": file_data.get("auto_delete_time", None),
            "uploaded_at": datetime.utcnow(),
            "batch_id": file_data.get("batch_id", None)  # New field for batch association
        }
        await self.files.insert_one(file_doc)
        return file_doc["uuid"]

    async def get_file(self, uuid: str) -> Optional[Dict[str, Any]]:
        return await self.files.find_one({"uuid": uuid})

    async def increment_downloads(self, uuid: str) -> None:
        await self.files.update_one(
            {"uuid": uuid},
            {
                "$inc": {"downloads": 1},
                "$set": {"last_download": datetime.utcnow()}
            }
        )

    async def add_batch(self, batch_data: Dict[str, Any]) -> str:
        """Add a new batch of files"""
        batch_doc = {
            "batch_id": batch_data["batch_id"],
            "created_by": batch_data["created_by"],
            "total_files": batch_data["total_files"],
            "created_at": datetime.utcnow(),
            "downloads": 0,
            "description": batch_data.get("description", ""),
            "status": "active"
        }
        await self.batches.insert_one(batch_doc)
        return batch_doc["batch_id"]

    async def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch details and its associated files"""
        batch = await self.batches.find_one({"batch_id": batch_id})
        if batch:
            # Get all files associated with this batch
            files = await self.files.find({"batch_id": batch_id}).to_list(None)
            batch["files"] = files
        return batch

    async def get_batch_files(self, batch_id: str) -> List[Dict[str, Any]]:
        """Get all files in a batch"""
        return await self.files.find({"batch_id": batch_id}).to_list(None)

    async def increment_batch_downloads(self, batch_id: str) -> None:
        """Increment batch download counter"""
        await self.batches.update_one(
            {"batch_id": batch_id},
            {
                "$inc": {"downloads": 1},
                "$set": {"last_download": datetime.utcnow()}
            }
        )

    async def set_file_autodelete(self, uuid: str, delete_time: int) -> bool:
        result = await self.files.update_one(
            {"uuid": uuid},
            {
                "$set": {
                    "auto_delete": True,
                    "auto_delete_time": delete_time,
                    "delete_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    async def get_autodelete_files(self) -> List[Dict[str, Any]]:
        return await self.files.find({"auto_delete": True}).to_list(None)

    async def update_file_message_id(self, uuid: str, message_id: int, chat_id: int) -> None:
        await self.files.update_one(
            {"uuid": uuid},
            {
                "$push": {
                    "active_messages": {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "sent_at": datetime.utcnow()
                    }
                }
            }
        )

    async def remove_file_message(self, uuid: str, chat_id: int, message_id: int) -> None:
        await self.files.update_one(
            {"uuid": uuid},
            {
                "$pull": {
                    "active_messages": {
                        "chat_id": chat_id,
                        "message_id": message_id
                    }
                }
            }
        )

    async def get_stats(self) -> Dict[str, Any]:
        total_files = await self.files.count_documents({})
        total_users = await self.users.count_documents({})
        total_batches = await self.batches.count_documents({})

        total_size = 0
        total_downloads = 0
        batch_downloads = 0

        async for file in self.files.find({}):
            total_size += file.get("file_size", 0)
            total_downloads += file.get("downloads", 0)

        async for batch in self.batches.find({}):
            batch_downloads += batch.get("downloads", 0)

        return {
            "total_files": total_files,
            "total_users": total_users,
            "total_size": total_size,
            "total_downloads": total_downloads,
            "total_batches": total_batches,
            "batch_downloads": batch_downloads,
            "active_autodelete_files": await self.files.count_documents({"auto_delete": True})
        }

    async def add_user(self, user_id: int, username: str = None) -> None:
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username": username,
                    "joined_date": datetime.utcnow(),
                    "last_active": datetime.utcnow()
                }
            },
            upsert=True
        )

    async def update_user_activity(self, user_id: int) -> None:
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_active": datetime.utcnow()}}
        )

    async def get_all_users(self) -> List[Dict[str, Any]]:
        return await self.users.find({}).to_list(None)
