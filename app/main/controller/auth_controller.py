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


def generate_login_html(auth_url: str) -> str:
    """Generate login page HTML"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sign In - Baby Tracker</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}

            .login-container {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 50px;
                max-width: 450px;
                width: 100%;
                text-align: center;
                animation: slideIn 0.5s ease-out;
            }}

            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(30px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}

            .logo {{
                font-size: 48px;
                margin-bottom: 20px;
                animation: bounce 1s ease-in-out;
            }}

            @keyframes bounce {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-10px); }}
            }}

            h1 {{
                color: #333;
                margin-bottom: 10px;
                font-size: 28px;
            }}

            .subtitle {{
                color: #666;
                margin-bottom: 40px;
                font-size: 16px;
            }}

            .google-btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background-color: #4285f4;
                color: white;
                text-decoration: none;
                padding: 14px 24px;
                border-radius: 8px;
                font-weight: 500;
                font-size: 16px;
                transition: all 0.3s ease;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                width: 100%;
                gap: 12px;
            }}

            .google-btn:hover {{
                background-color: #357ae8;
                box-shadow: 0 4px 12px rgba(66, 133, 244, 0.3);
                transform: translateY(-1px);
            }}

            .google-icon {{
                width: 20px;
                height: 20px;
                background: white;
                border-radius: 2px;
                padding: 2px;
            }}

            .features {{
                margin-top: 50px;
                padding-top: 30px;
                border-top: 1px solid #eee;
            }}

            .features-title {{
                color: #666;
                font-size: 14px;
                margin-bottom: 20px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}

            .feature-list {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }}

            .feature {{
                text-align: center;
            }}

            .feature-icon {{
                font-size: 32px;
                margin-bottom: 8px;
            }}

            .feature-text {{
                font-size: 14px;
                color: #666;
            }}

            .privacy-note {{
                margin-top: 30px;
                font-size: 12px;
                color: #999;
                line-height: 1.5;
            }}

            .privacy-note a {{
                color: #4285f4;
                text-decoration: none;
            }}

            .privacy-note a:hover {{
                text-decoration: underline;
            }}

            /* Responsive design */
            @media (max-width: 480px) {{
                .login-container {{
                    padding: 30px;
                }}

                h1 {{
                    font-size: 24px;
                }}

                .feature-list {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">👶</div>
            <h1>Welcome to Baby Tracker</h1>
            <p class="subtitle">Track your baby's daily activities and milestones</p>

            <a href="{auth_url}" class="google-btn">
                <svg class="google-icon" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Sign in with Google
            </a>

            <div class="features">
                <p class="features-title">Track Everything</p>
                <div class="feature-list">
                    <div class="feature">
                        <div class="feature-icon">🍼</div>
                        <div class="feature-text">Feeding</div>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">😴</div>
                        <div class="feature-text">Sleep</div>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">👶</div>
                        <div class="feature-text">Diapers</div>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">📏</div>
                        <div class="feature-text">Growth</div>
                    </div>
                </div>
            </div>

            <p class="privacy-note">
                By signing in, you agree to our <a href="/terms">Terms of Service</a> and <a href="/privacy">Privacy Policy</a>.
                We use Google authentication to keep your data secure.
            </p>
        </div>

        <script>
            // Clear any existing authentication data when on login page
            sessionStorage.clear();

            // Add loading state when clicking sign in
            document.querySelector('.google-btn').addEventListener('click', function(e) {{
                this.innerHTML = '<span>Redirecting to Google...</span>';
                this.style.opacity = '0.7';
                this.style.pointerEvents = 'none';
            }});
        </script>
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


@router.get("/login")
async def login_route():
    """Display Google OAuth login page"""
    auth_url = f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid email profile&access_type=offline"

    # Return HTML login page instead of JSON
    return HTMLResponse(content=generate_login_html(auth_url))


@router.get("/login/json", response_model=Dict[str, str])
async def login_json_route():
    """Get Google OAuth login URL as JSON (for API clients)"""
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


@router.get("/logout")
async def logout():
    """Display logout confirmation page"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logged Out - Baby Tracker</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }

            .logout-container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 50px;
                max-width: 450px;
                width: 100%;
                text-align: center;
            }

            .check-icon {
                width: 80px;
                height: 80px;
                margin: 0 auto 20px;
                background: #4ade80;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 40px;
            }

            h1 {
                color: #333;
                margin-bottom: 10px;
            }

            p {
                color: #666;
                margin-bottom: 30px;
            }

            .btn {
                display: inline-block;
                padding: 14px 32px;
                background-color: #4285f4;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 500;
                transition: all 0.3s ease;
            }

            .btn:hover {
                background-color: #357ae8;
                transform: translateY(-1px);
            }
        </style>
        <script>
            // Clear all session storage on logout
            sessionStorage.clear();
        </script>
    </head>
    <body>
        <div class="logout-container">
            <div class="check-icon">✓</div>
            <h1>You've been logged out</h1>
            <p>Thanks for using Baby Tracker. Your session has been securely ended.</p>
            <a href="/" class="btn">Return to Home</a>
        </div>
    </body>
    </html>
    """)