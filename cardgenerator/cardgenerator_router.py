from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile, Form
from auth_router import get_current_user
import os
import io
import json
import fal_client
import requests
from PIL import Image
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
def preview_and_generate_image(sd_prompt, num_images, url):   
    prompt = f"magnum opus, blank card, no text, blank textbox at top for title, mid for details and bottom for description, detailed high quality thematic borders, {sd_prompt}"

    handler = fal_client.submit(
            "fal-ai/flux-lora/image-to-image",
            arguments={
                "num_inference_steps": 35,
                "prompt": sd_prompt,
                "num_images": num_images,
                "image_url": url,
                "strength": 0.85
            }
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
        result = preview_and_generate_image(sdPrompt, numImages, template_url)
        
        logger.info(f"Type of result: {type(result)}")
        logger.info(f"Content of result: {json.dumps(result, indent=2)}")
        
        # Extract the image URLs from the result
        image_urls = [img['url'] for img in result.get('images', [])]
        
        logger.info(f"Extracted image URLs: {image_urls}")
        
        if not image_urls:
            logger.warning("No images were generated.")
            return []
            
        # Download and process the images
        images = []
        for i, url in enumerate(image_urls):
            try:
                response = requests.get(url)
                response.raise_for_status()  # Raises an HTTPError for bad responses
                img = Image.open(io.BytesIO(response.content))
                images.append((img, f"Generated Image {i+1}"))  # Add a tuple with image and caption
                logger.info(f"Successfully downloaded and processed image {i+1}")
            except Exception as e:
                logger.error(f"Error processing image {i+1} from URL {url}: {str(e)}")
        
        if not images:
            logger.warning("No images could be downloaded and processed.")
            return []
        
        logger.info(f"Returning {len(images)} processed images")
        return images
    except Exception as e:
        logger.error("Error generating images: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post('/upload-image')
async def upload_image(file: UploadFile = File(...)):  # Note the File(...) specification
    url = await upload_image_to_cloudflare(file)
    print("url:", url)
    return {"url": url}