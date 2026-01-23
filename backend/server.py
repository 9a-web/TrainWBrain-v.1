from fastapi import FastAPI, APIRouter
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import httpx


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks


@api_router.get("/telegram/avatar/{user_id}")
async def get_telegram_avatar(user_id: int):
    """
    Получить аватарку пользователя Telegram через Bot API
    Проксируем изображение чтобы избежать CORS
    """
    from fastapi.responses import Response
    
    if not TELEGRAM_BOT_TOKEN:
        return RedirectResponse(
            url=f"https://ui-avatars.com/api/?name=U&background=FF6B00&color=fff&size=80"
        )
    
    try:
        async with httpx.AsyncClient() as http_client:
            # Получаем фото профиля пользователя
            photos_response = await http_client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUserProfilePhotos",
                params={"user_id": user_id, "limit": 1}
            )
            photos_data = photos_response.json()
            
            if not photos_data.get("ok") or not photos_data.get("result", {}).get("photos"):
                # Нет фото - возвращаем placeholder
                return RedirectResponse(
                    url=f"https://ui-avatars.com/api/?name=U&background=FF6B00&color=fff&size=80"
                )
            
            # Берём самое большое фото (последнее в массиве)
            file_id = photos_data["result"]["photos"][0][-1]["file_id"]
            
            # Получаем путь к файлу
            file_response = await http_client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
                params={"file_id": file_id}
            )
            file_data = file_response.json()
            
            if not file_data.get("ok"):
                return RedirectResponse(
                    url=f"https://ui-avatars.com/api/?name=U&background=FF6B00&color=fff&size=80"
                )
            
            file_path = file_data["result"]["file_path"]
            
            # Скачиваем изображение и возвращаем его напрямую
            image_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            image_response = await http_client.get(image_url)
            
            if image_response.status_code == 200:
                return Response(
                    content=image_response.content,
                    media_type="image/jpeg",
                    headers={
                        "Cache-Control": "public, max-age=3600"
                    }
                )
            else:
                return RedirectResponse(
                    url=f"https://ui-avatars.com/api/?name=U&background=FF6B00&color=fff&size=80"
                )
            
    except Exception as e:
        logger.error(f"Error fetching Telegram avatar: {e}")
        return RedirectResponse(
            url=f"https://ui-avatars.com/api/?name=U&background=FF6B00&color=fff&size=80"
        )

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()