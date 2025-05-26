
import pytest 
from fastapi import APIRouter, HTTPException
import httpx
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from storegenerator.sd_generator import preview_and_generate_image
load_dotenv(dotenv_path='../.env')

# Cloudflare credentials
cloudflare_account_id = os.getenv('CLOUDFLARE_ACCOUNT_ID')
cloudflare_api_token = os.getenv('CLOUDFLARE_IMAGES_API_TOKEN')

def generate_image(prompt: str):
    return preview_and_generate_image(prompt)

async def upload_image_to_cloudflare(image_url: str):
    url = f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_account_id}/images/v1"
    headers = {
        "Authorization": f"Bearer {cloudflare_api_token}",
    }
    
    # Use 'files' to send multipart form data
    files = {
        'url': (None, image_url),
        'metadata': (None, '{"key":"value"}'),  # Example metadata
        'requireSignedURLs': (None, 'false')
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, files=files)
        
        if response.status_code != 200:
            error_text = response.text
            raise HTTPException(status_code=response.status_code, detail=f"Cloudflare API error: {error_text}")
        
        return response.json()

# @pytest.mark.asyncio
async def test_upload_image_to_cloudflare():
    # Use a valid image URL for testing
    test_image_url = generate_image("A penguin")
    
    try:
        response_data = await upload_image_to_cloudflare(test_image_url)
        print("Upload successful:", response_data)
        
        # Add assertions based on expected response structure
        assert "result" in response_data
        assert response_data["success"] is True
        # store uploaded key, variant url, index 0 
        uploaded_key = response_data["result"]["id"]
        variant_url = response_data["result"]["variants"][0]
        print("Upload successful:", uploaded_key, variant_url)
    except HTTPException as e:
        print("Upload failed:", e.detail)
        pytest.fail(f"Cloudflare upload failed with status code {e.status_code}")


