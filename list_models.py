import os
from dotenv import load_dotenv
from google import genai

load_dotenv(dotenv_path=".env", override=True)
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
for m in client.models.list():
    print(m.name)
