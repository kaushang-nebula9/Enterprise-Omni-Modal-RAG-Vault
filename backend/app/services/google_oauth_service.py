import httpx
from google.auth import jwt
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests
from fastapi import HTTPException, status
from urllib.parse import urlencode
from app.core.config import settings
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

def get_google_auth_url() -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent"
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

async def exchange_code_for_user_info(code: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            # 1. Exchange authorization code for tokens
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
            token_response = await client.post(token_url, data=data)
            if token_response.status_code != 200:
                raise ValueError("Token exchange failed")
                
            token_json = token_response.json()
            id_token = token_json.get("id_token")
            if not id_token:
                raise ValueError("id_token not found in response")

            # 2. Verify and decode the ID token
            decoded = google_id_token.verify_oauth2_token(
                id_token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            # 4. Extract profile fields
            google_id = decoded.get("sub")
            email = decoded.get("email")
            full_name = decoded.get("name") or decoded.get("email")
            avatar_url = decoded.get("picture")

            if not google_id or not email:
                raise ValueError("Missing essential claims in decoded token")

            return {
                "google_id": google_id,
                "email": email,
                "full_name": full_name,
                "avatar_url": avatar_url
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate with Google"
        )

def create_google_setup_token(email: str, full_name: str, google_id: str, avatar_url: str | None) -> str:
    payload = {
        "email": email,
        "full_name": full_name,
        "google_id": google_id,
        "avatar_url": avatar_url
    }
    return serializer.dumps(payload)

def verify_google_setup_token(token: str) -> dict:
    try:
        return serializer.loads(token, max_age=600)
    except (SignatureExpired, BadSignature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup session expired. Please try signing in with Google again."
        )
