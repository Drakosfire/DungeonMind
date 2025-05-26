import boto3
from botocore.config import Config
from dotenv import load_dotenv
import logging
import os

# Add debug logging to see if .env file is being loaded
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Try to load the .env file and check if it succeeded
result = load_dotenv(dotenv_path='/media/drakosfire/Shared1/DungeonMind/DungeonMindServer/.env.development')
# logger.debug(f".env file loaded: {result}")

# Get and log each environment variable
ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')
ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
BUCKET_NAME = os.getenv('R2_BUCKET_NAME')

# logger.info(f"ACCOUNT_ID: {ACCOUNT_ID}")
# logger.info(f"ACCESS_KEY_ID: {ACCESS_KEY_ID}")
# logger.info(f"SECRET_ACCESS_KEY: {SECRET_ACCESS_KEY}")
# logger.info(f"BUCKET_NAME: {BUCKET_NAME}")

# logger.debug(f"ACCOUNT_ID: {'set' if ACCOUNT_ID else 'not set'}")
# logger.debug(f"ACCESS_KEY_ID: {'set' if ACCESS_KEY_ID else 'not set'}")
# logger.debug(f"SECRET_ACCESS_KEY: {'set' if SECRET_ACCESS_KEY else 'not set'}")
# logger.debug(f"BUCKET_NAME: {'set' if BUCKET_NAME else 'not set'}")

# Verify the .env file exists
env_path = '/media/drakosfire/Shared1/DungeonMind/DungeonMindServer/.env.development'
logger.debug(f".env file exists: {os.path.exists(env_path)}")

def get_r2_client():
    """Creates and returns a Cloudflare R2 client using boto3."""
    return boto3.client('s3',
        endpoint_url = f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id = ACCESS_KEY_ID,
        aws_secret_access_key = SECRET_ACCESS_KEY,
        config = Config(
            signature_version = 's3v4',
            region_name = 'auto'
        )
    )

# R2 client instance
r2_client = get_r2_client() 