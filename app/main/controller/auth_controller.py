from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import requests

from app.main import get_db
from app.main.model.user import UserResponse, User, UserPreferenceUpdate
from app.main.service.user_service import (
    create_user,
    get_all_users,
    update_user_status,
    update_user_preference
)
from app.main.service.oauth_service import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    get_current_user,
    verify_google_token
)

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={401: {"description": "Unauthorized"}}
)


# HTML Template Functions
def generate_error_html(title: str, message: str, details: str = None) -> str:
    """Generate error HTML response"""
    details_section = f'<div class="details">{details}</div>' if details else ''

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .container {{ border: 1px solid #ccc; padding: 20px; border-radius: 5px; background-color: #f9f9f9; }}
            .error {{ color: #d9534f; }}
            .details {{ background-color: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="error">{title}</h1>
            <p>{message}</p>
            {details_section}
            <p><a href="/auth/login">Try again</a></p>
        </div>
    </body>
    </html>
    """


def generate_success_redirect_html(user: User, id_token: str) -> str:
    """Generate success redirect HTML"""
    # Determine redirect URL based on skip_onboarding preference
    redirect_url = '/dashboard' if user.skip_onboarding else '/onboarding'

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting...</title>
        <meta http-equiv="refresh" content="2; url={redirect_url}">
        <script>
            // Store the token and user info in sessionStorage for the app to use
            sessionStorage.setItem('idToken', '{id_token}');
            sessionStorage.setItem('userEmail', '{user.email}');
            sessionStorage.setItem('userName', '{user.name or ""}');
            sessionStorage.setItem('userPicture', '{user.picture or ""}');
            sessionStorage.setItem('isAdmin', '{str(user.is_admin).lower()}');
            sessionStorage.setItem('skipOnboarding', '{str(user.skip_onboarding).lower()}');

            // Redirect to appropriate page
            setTimeout(function() {{
                window.location.href = '{redirect_url}';
            }}, 1000);
        </script>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                max-width: 800px; 
                margin: 0 auto; 
                padding: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
            }}
            .container {{ 
                text-align: center;
                padding: 40px;
                border-radius: 10px;
                background: #f9f9f9;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .spinner {{
                border: 3px solid #f3f3f3;
                border-top: 3px solid #ff8c69;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Authentication Successful!</h2>
            <p>Welcome, <strong>{user.name or user.email}</strong></p>
            <div class="spinner"></div>
            <p>Redirecting to {'your dashboard' if user.skip_onboarding else 'complete your profile'}...</p>
        </div>
    </body>
    </html>
    """


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
    try:
        # Exchange authorization code for tokens
        token_response = await exchange_code_for_token(code)
        id_token = token_response.get("id_token")

        if not id_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No ID token found in the response"
            )

        # Verify the ID token and get user info
        user_info = verify_google_token(id_token)

        # Create or update user
        user = await handle_user_creation(db, user_info)

        # Check if user is active
        if not user.is_active:
            return HTMLResponse(
                content=generate_error_html(
                    "Account Inactive",
                    "Your account has been disabled. Please contact an administrator."
                ),
                status_code=403
            )

        # Return success redirect
        return HTMLResponse(content=generate_success_redirect_html(user, id_token))

    except HTTPException as e:
        raise e
    except Exception as e:

        return HTMLResponse(
            content=generate_error_html(
                "Authentication Failed",
                "There was a problem with the authentication process.",
                str(e)
            ),
            status_code=401
        )


async def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for tokens"""
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
        error_detail = "Failed to retrieve access token"
        try:
            error_data = token_response.json()
            if 'error_description' in error_data:
                error_detail += f": {error_data['error_description']}"
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail
        )

    return token_response.json()


async def handle_user_creation(db: Session, user_info: dict) -> User:
    """Handle user creation or update"""
    user_data = {
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "picture": user_info.get("picture"),
        "google_id": user_info.get("sub")
    }

    return create_user(db, user_data)


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user (requires authentication)"""
    return current_user


@router.put("/me/preferences", response_model=UserResponse)
async def update_my_preferences(
        preference_update: UserPreferenceUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update current user's preferences"""
    result = update_user_preference(
        db,
        current_user.id,
        preference_update.skip_onboarding
    )

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'User not found')
        )

    return result


@router.get("/users", response_model=List[UserResponse])
async def list_all_users(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get all users (requires admin access)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return get_all_users(db)


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_active_status(
        user_id: int,
        is_active: bool,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update a user's active status (requires admin access)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    result = update_user_status(db, user_id, is_active)

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'User not found')
        )

    return result