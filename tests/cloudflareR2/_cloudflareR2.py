# Tests for Cloudflare R2

import unittest
import os
from r2_config import r2_client
from pdf2image import convert_from_path
from PIL import Image

class TestCloudflareR2(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        print("\n=== Setting up test ===")
        self.bucket_name = 'test'
        self.test_file_path = 'test_files/sample.txt'
        self.test_content = b'Hello, R2!'
        self.object_key = 'test/sample.txt'
        
        print(f"Using bucket: {self.bucket_name}")
        print(f"Creating test file at: {self.test_file_path}")
        
        # Create test file
        try:
            os.makedirs('test_files', exist_ok=True)
            with open(self.test_file_path, 'wb') as f:
                f.write(self.test_content)
            print("Test file created successfully")
            
            # Upload test file that we'll use for subsequent tests
            with open(self.test_file_path, 'rb') as file:
                r2_client.upload_fileobj(file, self.bucket_name, self.object_key)
            print("Test file uploaded to R2 successfully")
        except Exception as e:
            print(f"Error in setUp: {str(e)}")
            raise

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Try to clean up R2 object if it exists
        try:
            r2_client.delete_object(Bucket=self.bucket_name, Key=self.object_key)
        except:
            pass
        
        # Remove local test files
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
        
        # Clean up test_files directory and its contents
        if os.path.exists('test_files'):
            for file in os.listdir('test_files'):
                file_path = os.path.join('test_files', file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error removing file {file_path}: {e}")
            try:
                os.rmdir('test_files')
            except Exception as e:
                print(f"Error removing test_files directory: {e}")

    def test_upload_file(self):
        """Test uploading a file to R2."""
        object_key = 'test/sample.txt'
        
        # Upload file
        with open(self.test_file_path, 'rb') as file:
            r2_client.upload_fileobj(file, self.bucket_name, object_key)
        
        # Verify upload
        response = r2_client.get_object(Bucket=self.bucket_name, Key=object_key)
        self.assertEqual(response['Body'].read(), self.test_content)

    def test_download_file(self):
        """Test downloading a file from R2."""
        object_key = 'test/sample.txt'
        download_path = 'test_files/downloaded.txt'
        
        # Download file
        r2_client.download_file(self.bucket_name, object_key, download_path)
        
        # Verify download
        with open(download_path, 'rb') as file:
            self.assertEqual(file.read(), self.test_content)

    def test_list_objects(self):
        """Test listing objects in a bucket."""
        try:
            response = r2_client.list_objects_v2(Bucket=self.bucket_name)
            print(f"Response from R2: {response}")
            self.assertIn('Contents', response)
        except Exception as e:
            print(f"Failed to list objects: {str(e)}")
            raise

    def test_delete_object(self):
        """Test deleting an object from R2."""
        # First verify the object exists
        try:
            r2_client.head_object(Bucket=self.bucket_name, Key=self.object_key)
        except:
            self.fail("Test object doesn't exist before deletion")
        
        # Delete object
        r2_client.delete_object(Bucket=self.bucket_name, Key=self.object_key)
        
        # Verify deletion
        with self.assertRaises(Exception):
            r2_client.head_object(Bucket=self.bucket_name, Key=self.object_key)

    def test_upload_and_get_url(self):
        """Test uploading a file and getting a presigned URL to access it."""
        try:
            # Upload file
            with open(self.test_file_path, 'rb') as file:
                r2_client.upload_fileobj(file, self.bucket_name, self.object_key)
            print(f"File uploaded successfully to {self.object_key}")
            
            # Generate presigned URL (default expiration is 3600 seconds / 1 hour)
            url = r2_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': self.object_key
                },
                ExpiresIn=3600  # URL expires in 1 hour
            )
            
            print(f"Presigned URL: {url}")
            self.assertTrue(url.startswith('https://'))
            
            # Optional: Actually try to download the file using the URL
            import requests
            response = requests.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, self.test_content)
            
        except Exception as e:
            print(f"Error in test_upload_and_get_url: {str(e)}")
            raise
         
        
    def test_upload_and_view_pdf(self):
        """Test uploading a PDF file and getting a viewable URL."""
        try:
            # Define the PDF file path and object key
            pdf_path = "tests/cloudflareR2/Aberrant Meat Wing.pdf"
            pdf_object_key = "pdfs/Aberrant Meat Wing.pdf"
            
            # Upload PDF with content type specified
            with open(pdf_path, 'rb') as file:
                r2_client.upload_fileobj(
                    file, 
                    self.bucket_name, 
                    pdf_object_key,
                    ExtraArgs={'ContentType': 'application/pdf'}  # Specify PDF content type
                )
            print(f"PDF uploaded successfully to {pdf_object_key}")
            
            # Generate presigned URL with longer expiration for testing
            url = r2_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': pdf_object_key
                },
                ExpiresIn=86400  # URL expires in 1 hour
            )
            
            print(f"PDF Viewable URL: {url}")
            
            # Verify the URL works
            import requests
            response = requests.head(url)  # Use HEAD request to check URL without downloading
            
        except Exception as e:
            print(f"Error in test_upload_and_view_pdf: {str(e)}")
            raise

    def test_convert_pdf_to_single_image(self):
        """Test converting a PDF to a single long image."""
        # Convert PDF pages to images
        images = convert_from_path("tests/cloudflareR2/ButtholesButtholes.pdf")
        
        # Get dimensions for the combined image
        width = images[0].width
        total_height = sum(img.height for img in images)
        
        # Create a new blank image with the combined height
        combined_image = Image.new('RGB', (width, total_height), 'white')
        
        # Paste each page image at the appropriate vertical position
        current_height = 0
        for img in images:
            combined_image.paste(img, (0, current_height))
            current_height += img.height
        
        # Save the combined image
        output_path = "tests/cloudflareR2/combined_pages.jpg"
        combined_image.save(output_path, "JPEG", quality=95)
        print(f"Created single combined image at: {output_path}")

if __name__ == '__main__':
    unittest.main()
