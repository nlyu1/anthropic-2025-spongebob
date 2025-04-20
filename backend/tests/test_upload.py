import requests
import os
import time # Import time for potential delays if needed

# --- Configuration ---
# Default URL for the FastAPI server
BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
UPLOAD_URL = f"{BASE_URL}/api/upload"

# Path to the test PDF file (relative to the backend/tests directory)
# Assumes the script is run from the backend directory.
TEST_DIR = os.path.dirname(__file__) # Gets the directory where the test script is located (tests)
PDF_FILE_PATH = os.path.join(TEST_DIR, "trial.pdf") # tests/trial.pdf
EXPECTED_PDF_NAME = "trial"

# Path where the file is expected to be uploaded by the server
# Assumes script is run from backend/ directory.
# Server saves to files_dir which defaults to ../files relative to backend/app,
# meaning it saves to backend/files/.
UPLOAD_DIR_RELATIVE_TO_BACKEND = "./files"
TARGET_PDF_FILENAME = "trial.pdf"
# Construct absolute path based on CWD (assumed to be backend/)
TARGET_PDF_PATH_ABS = os.path.abspath(
    os.path.join(
        UPLOAD_DIR_RELATIVE_TO_BACKEND, TARGET_PDF_FILENAME))

# Source PDF path relative to backend/ directory
SOURCE_PDF_PATH_REL = os.path.join("tests", "trial.pdf")
print(f"SOURCE_PDF_PATH_REL: {SOURCE_PDF_PATH_REL}")
print(f"TARGET_PDF_PATH_ABS: {TARGET_PDF_PATH_ABS}")
# ---------------------

def cleanup_target_file():
    """Removes the target uploaded file if it exists."""
    # Use the pre-calculated absolute path
    if os.path.exists(TARGET_PDF_PATH_ABS):
        try:
            os.remove(TARGET_PDF_PATH_ABS)
            print(f"Cleaned up existing target file: {TARGET_PDF_PATH_ABS}")
        except OSError as e:
            print(f"Warning: Could not remove target file {TARGET_PDF_PATH_ABS}: {e}")
    else:
        print(f"Target file {TARGET_PDF_PATH_ABS} does not exist, no pre-test cleanup needed.")

def test_upload_endpoint():
    print(f"Testing endpoint: POST {UPLOAD_URL}")
    # Show paths relative to expected CWD (backend/)
    print(f"Using source file: {SOURCE_PDF_PATH_REL}")
    print(f"Expecting upload to absolute path: {TARGET_PDF_PATH_ABS}")

    # --- Pre-test check and cleanup ---
    # Check source file relative to backend/
    if not os.path.exists(SOURCE_PDF_PATH_REL):
        print(f"Error: Test source file not found at {SOURCE_PDF_PATH_REL} (relative to backend/)")
        print("Ensure 'trial.pdf' is in the 'backend/tests' directory.")
        print("Test FAILED")
        return

    cleanup_target_file() # Remove target file before test
    # --- End Pre-test ---

    test_passed = False # Flag to track success for cleanup
    try:
        # Open source file using relative path
        with open(SOURCE_PDF_PATH_REL, 'rb') as f:
            # Send with the target filename
            files = {'file': (TARGET_PDF_FILENAME, f, 'application/pdf')}
            response = requests.post(UPLOAD_URL, files=files, timeout=60)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                response_json = response.json()
                print(f"Response JSON: {response_json}")
                expected_response = {"pdf_name": EXPECTED_PDF_NAME}
                if response_json == expected_response:
                    print("Response JSON matches expected output.")
                    # Verify file exists at the absolute target location
                    print(f"Checking for file at: {TARGET_PDF_PATH_ABS}")
                    # Give the filesystem a moment
                    time.sleep(1) 
                    if os.path.exists(TARGET_PDF_PATH_ABS):
                        print(f"Verified uploaded file exists at: {TARGET_PDF_PATH_ABS}")
                        print("Test PASSED")
                        test_passed = True # Mark test as passed for cleanup
                    else:
                        print(f"Error: Uploaded file NOT found at expected location: {TARGET_PDF_PATH_ABS}")
                        print("Test FAILED")
                else:
                    print(f"Error: Response JSON {response_json} does not match expected {expected_response}")
                    print("Test FAILED")
            except requests.exceptions.JSONDecodeError:
                print("Error: Failed to decode JSON response.")
                print(f"Response Text: {response.text[:200]}...") # Show beginning of text
                print("Test FAILED")
        else:
            print(f"Error: Received status code {response.status_code}")
            try:
                 # Try to print JSON error detail if available
                 error_detail = response.json()
                 print(f"Error Detail: {error_detail}")
            except requests.exceptions.JSONDecodeError:
                 print(f"Response Text: {response.text[:200]}...")
            print("Test FAILED")

    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        print("Test FAILED")
    except FileNotFoundError:
        # This refers to the source file
        print(f"Error: Could not open source file {SOURCE_PDF_PATH_REL}")
        print("Test FAILED")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("Test FAILED")
    finally:
        # --- Post-test cleanup ---
        if test_passed:
            print("Performing post-test cleanup...")
            cleanup_target_file() # Remove target file only if test passed
        else:
            print("Test failed, skipping post-test cleanup to allow inspection.")
        # --- End Post-test cleanup ---


if __name__ == "__main__":
    test_upload_endpoint()