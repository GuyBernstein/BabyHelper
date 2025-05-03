import json
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
import requests

from app.main import get_db
from app.main.model.user import UserResponse, User
from app.main.service.user_service import create_user
from app.main.util.oauth import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, get_current_user, verify_google_token

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={401: {"description": "Unauthorized"}}
)


@router.get("/login", response_model=Dict[str, str])
async def login_route():
    """Get Google OAuth login URL (open this URL in your browser)"""
    auth_url = f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid email profile&access_type=offline"
    return {
        "message": "Open this URL in your browser to login with Google",
        "login_url": auth_url
    }


@router.get("/callback")
async def callback(code: str, db: Session = Depends(get_db)):
    """Handle OAuth callback and create user if not exists"""
    # Exchange authorization code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    token_response = requests.post(token_url, data=token_payload)
    if token_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to retrieve access token"
        )

    token_data = token_response.json()
    id_token = token_data.get("id_token")

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No ID token found in the response"
        )

    try:
        # Verify the ID token and get user info
        user_info = verify_google_token(id_token)

        # Create or update user
        user_data = {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "google_id": user_info.get("sub")
        }

        user = create_user(db, user_data)

        # Return a success page with the ID token for testing
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                textarea {{ width: 100%; font-family: monospace; }}
                .container {{ border: 1px solid #ccc; padding: 20px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Authentication Successful</h1>
                <p>You are now logged in as <strong>{user.email}</strong></p>
                <p>Your ID Token (use this as Bearer token in /docs):</p>
                <textarea rows="8" cols="80" onclick="this.select()">{id_token}</textarea>
                <p>To use this token in the Swagger UI:</p>
                <ol>
                    <li>Click the "Authorize" button at the top right of the <a href="/docs" target="_blank">Swagger UI</a></li>
                    <li>In the "bearerAuth (HTTPBearer)" field, enter the token above (without quotes)</li>
                    <li>Click "Authorize" and close the dialog</li>
                    <li>Now you can use the protected endpoints</li>
                </ol>
            </div>
        </body>
        </html>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user (requires authentication)"""
    return current_user