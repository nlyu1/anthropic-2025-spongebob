import os
from dotenv import load_dotenv

# Load environment variables from .env file in the backend directory
# Adjust the path if your .env file is located elsewhere relative to this settings.py file
# Assuming settings.py is in backend/app and .env is in backend/
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Access environment variables using os.getenv
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3210") # Default value if not set
files_dir = os.getenv("FILES_DIR", "../files") # Default relative path to files dir
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

# You can add validation or type casting here if needed
# Example:
# try:
#     some_port = int(os.getenv("PORT", "8000"))
# except ValueError:
#     raise ValueError("Invalid PORT environment variable")

# Ensure required variables are set
if not anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set.")

# No need for the Settings class anymore
