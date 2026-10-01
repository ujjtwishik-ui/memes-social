# test_cloudinary_simple.py
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

print("Cloud name:", cloudinary.config().cloud_name)

# Тест БЕЗ папки
res = cloudinary.uploader.upload(
    "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg"
)
print("OK:", res["secure_url"])