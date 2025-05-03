import json
from typing import Dict

from fastapi import HTTPException, status, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.user import User
from app.main.service.user_service import get_user_by_google_id, create_user

# Load the client secret file
with open('client_secret.json', 'r') as f:
    client_config = json.load(f)['web']

CLIENT_ID = client_config['client_id']
CLIENT_SECRET = client_config['client_secret']
# Use the first redirect URI from the config, but ensure it points to our callback route
BASE_URI = "http://127.0.0.1:8000"  # Use 127.0.0.1 instead of localhost for consistency
REDIRECT_URI = f"{BASE_URI}/auth/callback"

# Setup security for bearer token
security = HTTPBearer()


def verify_google_token(token: str) -> Dict:
    """Verify the Google ID token"""
    try:
        # Specify the CLIENT_ID of the app that accesses the backend
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)

        # Verify issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        # ID token is valid
        return idinfo
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Security(security),
        db: Session = Depends(get_db)
) -> User:
    """Dependency to get the current authenticated user from token"""
    try:
        token = credentials.credentials

        # Verify the token and get user info
        idinfo = verify_google_token(token)

        # Get or create user based on Google ID
        user = get_user_by_google_id(db, idinfo['sub'])

        if not user:
            # Create new user from Google data
            user_data = {
                'email': idinfo['email'],
                'name': idinfo.get('name'),
                'picture': idinfo.get('picture'),
                'google_id': idinfo['sub']
            }
            user = create_user(db, user_data)

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact an administrator."
            )

        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def is_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency to check if the current user is an admin"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user