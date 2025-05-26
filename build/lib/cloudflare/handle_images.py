import httpx
from fastapi import HTTPException
import os
from dotenv import load_dotenv
import logging
from typing import Union
from fastapi import UploadFile

load_dotenv(dotenv_path='../.env')

cloudflare_account_id = os.getenv('CLOUDFLARE_ACCOUNT_ID')
cloudflare_api_token = os.getenv('CLOUDFLARE_IMAGES_API_TOKEN')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def upload_image_to_cloudflare(image_input: Union[str, UploadFile]):
    logger.info("Uploading image to Cloudflare")
    url = f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_account_id}/images/v1"
    headers = {
        "Authorization": f"Bearer {cloudflare_api_token}",
    }
    
    # Check if input is a URL or UploadFile
    if isinstance(image_input, str):
        files = {
            'url': (None, image_input),
            'metadata': (None, '{"key":"value"}'),
            'requireSignedURLs': (None, 'false')
        }
    else:
        # Handle uploaded file
        file_content = await image_input.read()
        files = {
            'file': (image_input.filename, file_content, image_input.content_type),
            'metadata': (None, '{"key":"value"}'),
            'requireSignedURLs': (None, 'false')
        }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, files=files)
        
        if response.status_code != 200:
            error_text = response.text
            raise HTTPException(status_code=response.status_code, detail=f"Cloudflare API error: {error_text}")
        
        result = response.json()["result"]
        public_url = result.get("variants")[0]
        
        # Ensure URL ends with /public
        if not public_url.endswith('/public'):
            public_url = '/'.join(public_url.split('/')[:-1]) + '/public'
            
        logger.info(f"Image uploaded successfully. Public URL: {public_url}")
        return public_url