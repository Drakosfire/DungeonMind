import os
from cloudflareR2.r2_config import get_r2_client
from pdf2image import convert_from_path
from PIL import Image
import uuid
import logging

logger = logging.getLogger(__name__)


# def convert_pdf_to_single_image(path_to_pdf):
#     """Test converting a PDF to a single long image."""
#     # Convert PDF pages to images
#     images = convert_from_path(path_to_pdf)
    
#     # Get dimensions for the combined image
#     width = images[0].width
#     total_height = sum(img.height for img in images)
    
#     # Create a new blank image with the combined height
#     combined_image = Image.new('RGB', (width, total_height), 'white')
    
#     # Paste each page image at the appropriate vertical position
#     current_height = 0
#     for img in images:
#         combined_image.paste(img, (0, current_height))
#         current_height += img.height
    
#     # Save the combined image
#     output_path = "tests/cloudflareR2/combined_pages.jpg"
#     combined_image.save(output_path, "JPEG", quality=95)
#     print(f"Created single combined image at: {output_path}")

def upload_html_and_get_url(html_content, bucket_name='store-generator'):
    html = html_content['html']
    """Upload HTML content and get a presigned URL to access it."""
    try:
        # Generate unique filename
        file_id = str(uuid.uuid4())
        object_key = f"shared-stores/{file_id}.html"
        
        # Upload HTML content directly
        r2_client = get_r2_client()
        r2_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=html.encode('utf-8'),
            ContentType='text/html'
        )
        # print(f"File uploaded successfully to {object_key}")
        
        # Generate presigned URL (1 week expiration)
        url = r2_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=3600 * 24 * 7  # URL expires in 7 days
        )
        
        # print(f"Presigned URL: {url}")
        return url
        
    except Exception as e:
        print(f"Error in upload_file_and_get_url: {str(e)}")
        raise

async def upload_temp_file_and_get_url(file_path, expiration_days=1, bucket_name='temp-images'):
    """
    Upload a temporary file to R2 and get a presigned URL to access it.
    
    Args:
        file_path (str): Path to the local file to upload
        expiration_days (int): Number of days until URL expires (default 7)
        bucket_name (str): Name of R2 bucket to upload to (default 'temp-images')
        
    Returns:
        str: Presigned URL to access the uploaded file
        
    Raises:
        Exception: If upload fails
    """
    try:
        # Generate unique filename while preserving extension
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file_path)[1]
        object_key = f"temp/{file_id}{file_extension}"
        
        # Upload file
        r2_client = get_r2_client()
        with open(file_path, 'rb') as file:
            r2_client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=file,
                ContentType='image/png'  # Assuming PNG files for now
            )
        
        # Generate presigned URL
        url = r2_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=3600 * 24 * expiration_days  # Convert days to seconds
        )
        
        return url
        
    except Exception as e:
        print(f"Error uploading temp file to R2: {str(e)}")
        raise

