from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile, Form
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
from cloudflareR2.cloudflareR2_utils import upload_temp_file_and_get_url
from typing import List, Tuple

from openai import OpenAI
from cardgenerator.prompts import prompt_instructions
from cardgenerator.card_generator import render_text_on_card

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

# Define Pydantic models for structured output
class ItemProperties(BaseModel):
    Name: str
    Type: str
    Rarity: str
    Value: str
    Properties: List[str]
    Damage: Tuple[str, str]  # Changed to match frontend format
    Weight: str
    Description: str
    Quote: str
    SD_Prompt: str  # Changed to match frontend 'SD Prompt'

# Define the request model for rendering card text
class RenderCardRequest(BaseModel):
    image_url: str
    item_details: dict
router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def preview_and_generate_image(sd_prompt, num_images, url):   
    prompt = f"magnum opus, blank card, no text, blank textbox at top for title, mid for details and bottom for description, detailed high quality thematic borders, {sd_prompt} in on a background of appropriate setting or location"

    handler = fal_client.submit(
            "fal-ai/flux-lora/image-to-image",
            arguments={
                "num_inference_steps": 35,
                "prompt": prompt,
                "num_images": num_images,
                "image_url": url,
                "strength": 0.85,
                "image_size": {
                    "width": 768,
                    "height": 1024
                }   
            }
        )

    result = handler.get()
    logger.info(f"Type of result: {type(result)}")
    logger.info(f"Content of result: {json.dumps(result, indent=2)}")
    
    # Extract the image URLs from the result
    image_urls = [img['url'] for img in result.get('images', [])]
    
    logger.info(f"Extracted image URLs: {image_urls}")
    
    if not image_urls:
        logger.warning("No images were generated.")
        return []
    return result

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
        image_urls = preview_and_generate_image(sdPrompt, numImages, template_url)      
        
        return image_urls
    except Exception as e:
        logger.error("Error generating images: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post('/upload-image')
async def upload_image(file: UploadFile = File(...)):  # Note the File(...) specification
    url = await upload_image_to_cloudflare(file)
    print("url:", url)
    return {"url": url}


client = OpenAI()

# Define the JSON schema
ITEM_SCHEMA = {
    "name": "item",
    "schema": {
    "type": "object",
    "properties": {
        "Name": {
            "type": "string",
            "description": "The name of the magical item."
        },
        "Type": {
            "type": "string",
            "description": "The type or category of the magical item."
        },
        "Rarity": {
            "type": "string",
            "description": "The rarity classification of the item.",
            "enum": [
                "Common",
                "Uncommon",
                "Rare",
                "Very Rare",
                "Legendary"
            ]
        },
        "Value": {
            "type": "string",
            "description": "The monetary value of the item."
        },
        "Properties": {
            "type": "array",
            "description": "Unique properties or abilities of the magical item.",
            "items": {
                "type": "string"
            }
        },
        "Damage Formula": {
            "type": "string",
            "description": "The formula used to calculate the damage of the item."
        },
        "Damage Type": {
            "type": "string",
            "description": "The type of damage the item inflicts."
        },
        "Weight": {
            "type": "string",
            "description": "The weight of the item."
        },
        "Description": {
            "type": "string",
            "description": "A detailed description of the item, including its design and features."
        },
        "Quote": {
            "type": "string",
            "description": "A memorable quote associated with the item."
        },
        "SD Prompt": {
            "type": "string",
            "description": "A description used for visual or artistic representation of the item."
        }
    },
    "required": [
        "Name",
        "Type",
        "Rarity",
        "Value",
        "Properties",
        "Weight",
        "Description",
        "Quote",
        "SD Prompt"
    ],
        "additionalProperties": False
    }
}

@router.post('/generate-item-dict')
async def generate_item_dict(user_idea: dict):
    try:
        # Construct the prompt from user input
        prompt = f"{user_idea['userIdea']}"
        
        # Make the API call
        response = client.beta.chat.completions.parse(
            model="gpt-4o",  # Ensure the model is supported
            messages=[
                {
                    "role": "system",
                    "content": f"{prompt_instructions}"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": ITEM_SCHEMA,  # Ensure ITEM_SCHEMA is correctly defined
            }
        )
        
        # Log the full response for debugging
        logging.debug(f"Full response: {response}")
        
        # Safely extract and parse the structured data
        parsed_data = response.choices[0].message.parsed if response.choices else None
        if not parsed_data:
            print("Parsed data is missing from the response trying content.")
            parsed_data = response.choices[0].message.content
            print(parsed_data)
            

        # Test if parsed data is a string and jsonify it
        if isinstance(parsed_data, str):
            parsed_data = json.loads(parsed_data)
        
        # Ensure the parsed data contains the required fields
        if "Name" not in parsed_data:
            raise ValueError("Parsed data does not contain the 'Name' field.")
        
        # Format the structured response for the frontend
        formatted_response = {parsed_data["Name"]: parsed_data}
        
        # Return the structured item data
        return formatted_response

    except Exception as e:
        # Log detailed error for debugging
        logging.error(f"Error generating item dictionary: {str(e)}", exc_info=True)
        
        # Raise an HTTP exception with details
        raise HTTPException(status_code=500, detail=f"Failed to generate item: {str(e)}")
    
@router.post('/render-card-text')
async def render_card_text(request: RenderCardRequest):
    # Open the recieved PIL image object
    image_object = render_text_on_card(request.image_url, request.item_details) 
    print("type of image_object:", type(image_object))
    # Save the image to a temporary file
    temp_file_path = f"temp_card_{request.item_details['Name']}.png"
    image_object.save(temp_file_path)
    # Check for temp file
    if not os.path.exists(temp_file_path):
        raise HTTPException(status_code=500, detail="Failed to save image to temporary file")
    # Upload the image to Cloudflare and await the response
    url = await upload_temp_file_and_get_url(temp_file_path)
    # Delete the temporary file
    os.remove(temp_file_path)

    # Format the structured response for the frontend
    formatted_response = {"url": url}

    return formatted_response