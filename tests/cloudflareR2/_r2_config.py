import pytest
from r2_config import get_r2_client, r2_client
import boto3
import os
from dotenv import load_dotenv

result = load_dotenv(dotenv_path='/media/drakosfire/Shared1/DungeonMind/DungeonMindServer/.env.development')


def test_r2_client_creation():
    """Test that the R2 client is created successfully"""
    client = get_r2_client()
    # Check if it has the expected S3 client attributes
    assert hasattr(client, 'list_buckets')
    assert hasattr(client, 'get_object')
    assert hasattr(client, 'put_object')

def test_r2_credentials():
    """Test that all required environment variables are set"""
    required_vars = [
        'CLOUDFLARE_ACCOUNT_ID',
        'R2_ACCESS_KEY_ID',
        'R2_SECRET_ACCESS_KEY',
        'R2_BUCKET_NAME'
    ]
    for var in required_vars:
        assert os.getenv(var) is not None, f"Missing environment variable: {var}"

def test_r2_connection():
    """Test that we can actually connect to R2 and perform a basic operation"""
    try:
        # List buckets is one of the simplest operations we can perform
        response = r2_client.list_buckets()
        assert 'Buckets' in response
        print(f"Successfully connected to R2. Found buckets: {response['Buckets']}")
    except Exception as e:
        pytest.fail(f"Failed to connect to R2: {str(e)}")

def test_specific_bucket_access():
    """Test that we can access a specific bucket if it exists"""
    # Replace 'your-bucket-name' with your actual bucket name
    bucket_name = 'test'
    try:
        response = r2_client.head_bucket(Bucket=bucket_name)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200
    except r2_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            pytest.skip(f"Bucket {bucket_name} does not exist")
        else:
            pytest.fail(f"Error accessing bucket: {str(e)}") 