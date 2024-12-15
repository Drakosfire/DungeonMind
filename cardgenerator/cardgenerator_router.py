from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile, Form
from auth_router import get_current_user
import os
import json
import fal_client
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
def preview_and_generate_image(sd_prompt):   
    prompt = f"magnum opus, blank card, no text, blank textbox at top for title, mid for details and bottom for description, detailed high quality thematic borders, {sd_prompt}"

    handler = fal_client.submit(
        "fal-ai/flux/dev",
        arguments={
            "prompt": prompt,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,

        },
    )

    result = handler.get()
    return result['images'][0]['url']

@router.post('/generate-card-images')
async def generate_card_images(
    template: UploadFile = File(...),
    sdPrompt: str = Form(...),
    numImages: int = Form(...)
):
    try:
        # 1. Upload template to Cloudflare
        template_url = await upload_image_to_cloudflare(template)
        
        # 2. Generate images using the template and SD prompt
        generated_images = []
        for _ in range(numImages):
            image_url = preview_and_generate_image(sdPrompt)
            generated_images.append(image_url)
            
        return {
            "template_url": template_url,
            "images": generated_images
        }
    except Exception as e:
        logger.error("Error generating images: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post('/upload-image')
async def upload_image(file: UploadFile = File(...)):  # Note the File(...) specification
    url = await upload_image_to_cloudflare(file)
    print("url:", url)
    return {"url": url}