from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile, Form
from auth_router import get_current_user
import os
import json
from pydantic import BaseModel
import firestore.firestore_utils as firestore_utils
import logging
from cloudflare.handle_images import upload_image_to_cloudflare
from cloudflareR2.cloudflareR2_utils import upload_html_and_get_url
# Cloudflare credentials
cloudflare_account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID')
cloudflare_api_token = os.environ.get('CLOUDFLARE_IMAGES_API_TOKEN')

# Define the request models
class DescriptionRequest(BaseModel):
    user_input: str

class GenerateImageRequest(BaseModel):
    sd_prompt: str

class SaveJsonRequest(BaseModel):
    filename: str
    jsonData: dict

class ImageUploadRequest(BaseModel):
    image_url: str

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# @router.post('/generate-image')
# async def generate_image(data: GenerateImageRequest):
#     sd_prompt = data.sd_prompt
#     if not sd_prompt:
#         raise HTTPException(status_code=400, detail="Missing sd_prompt")
#     try:
#         image_url = sd.preview_and_generate_image(sd_prompt)
#         # logger.info("Generated image URL: %s", image_url)
#         # uploaded_image = await upload_image_to_cloudflare(image_url)
#         # logger.info("Uploaded image: %s", uploaded_image)
#         return {"image_url": image_url}
#     except Exception as e:
#         # logger.error("Error generating image: %s", str(e))
#         raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post('/upload-image')
async def upload_image(file: UploadFile = File(...)):  # Note the File(...) specification
    url = await upload_image_to_cloudflare(file)
    print("url:", url)
    return {"url": url}