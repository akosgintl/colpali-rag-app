import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sign in with email/password
response = client.auth.sign_in_with_password(
    {"email": "***.***@gmail.com", "password": "***"}
)

token = response.session.access_token
print(f"Bearer token: {token}")
