#!/usr/bin/env python
import requests
import json
import os
import sys
import time

# Add the parent directory to sys.path to import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def main():
    base_url = "http://localhost:8000"
    
    # Step 1: Check if the server is running
    try:
        response = requests.get(f"{base_url}/check")
        if response.status_code != 200:
            print(f"Server check failed with status code {response.status_code}")
            return False
        print("✓ Server is running")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to server: {e}")
        print("Make sure the server is running with 'uvicorn app.main:app --reload --port 8000'")
        return False
    
    # Step 2: Check if models endpoint works
    try:
        response = requests.get(f"{base_url}/v1/models")
        if response.status_code != 200:
            print(f"Models endpoint failed with status code {response.status_code}")
            return False
        models = response.json()
        if not models.get("data"):
            print("No models returned from models endpoint")
            return False
        print(f"✓ Models endpoint working, found model: {models['data'][0]['id']}")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to models endpoint: {e}")
        return False
    
    # Step 3: Test chat endpoint without a file (should give guidance message)
    try:
        payload = {
            "model": "pdf-master",
            "messages": [{"role": "user", "content": "What's in this document?"}],
            "stream": False
        }
        response = requests.post(f"{base_url}/v1/chat/completions", json=payload)
        if response.status_code != 200:
            print(f"Chat endpoint failed with status code {response.status_code}")
            return False
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        print(f"✓ Chat endpoint working without files")
        print(f"  Response: {content}")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to chat endpoint: {e}")
        return False
    
    # Step 4: Check if there are PDF files in the files directory
    files_dir = os.getenv("FILES_DIR", "./files")
    pdf_files = [f for f in os.listdir(files_dir) if f.endswith('.pdf')]
    
    if not pdf_files:
        print("No PDF files found in the files directory. Upload one to test with files.")
        return True
    
    print(f"✓ Found PDF files: {pdf_files}")
    
    # Step 5: Test with a file
    # First, upload the file to get a file_id
    try:
        pdf_path = os.path.join(files_dir, pdf_files[0])
        with open(pdf_path, 'rb') as f:
            files = {'file': (pdf_files[0], f, 'application/pdf')}
            response = requests.post(f"{base_url}/api/v1/files/", files=files)
        
        if response.status_code != 200:
            print(f"File upload failed with status code {response.status_code}")
            return False
        
        file_response = response.json()
        file_id = file_response.get("id")
        
        if not file_id:
            print("No file_id returned from upload endpoint")
            return False
        
        print(f"✓ File upload successful with ID: {file_id}")
        
        # Now test chat with the file
        payload = {
            "model": "pdf-master",
            "messages": [{"role": "user", "content": "What is this document about?"}],
            "stream": False,
            "files": [{"type": "file", "id": file_id}]
        }
        
        print("Testing chat with file attachment...")
        response = requests.post(f"{base_url}/v1/chat/completions", json=payload)
        
        if response.status_code != 200:
            print(f"Chat with file failed with status code {response.status_code}")
            return False
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        print(f"✓ Chat with file successful")
        print(f"  Response: {content[:100]}..." if len(content) > 100 else f"  Response: {content}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error during file test: {e}")
        return False
    
    # Step 6: Test streaming mode
    try:
        print("\nTesting streaming mode...")
        payload = {
            "model": "pdf-master",
            "messages": [{"role": "user", "content": "Give me a brief summary"}],
            "stream": True,
            "files": [{"type": "file", "id": file_id}]
        }
        
        response = requests.post(f"{base_url}/v1/chat/completions", json=payload, stream=True)
        
        if response.status_code != 200:
            print(f"Streaming chat failed with status code {response.status_code}")
            return False
        
        print("Streaming response (first 3 chunks):")
        chunks_received = 0
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: ') and line != 'data: [DONE]':
                    data = line[6:]  # Remove 'data: ' prefix
                    try:
                        chunk = json.loads(data)
                        content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if content:
                            print(f"  Chunk: {content}")
                            chunks_received += 1
                            if chunks_received >= 3:
                                print("  ... (more chunks)")
                                break
                    except json.JSONDecodeError:
                        continue
        
        print(f"✓ Streaming mode working correctly")
        
    except requests.exceptions.RequestException as e:
        print(f"Error during streaming test: {e}")
        return False
    
    print("\nAll tests passed successfully!")
    return True

if __name__ == "__main__":
    main() 