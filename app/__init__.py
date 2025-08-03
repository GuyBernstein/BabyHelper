from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from fastapi.exceptions import RequestValidationError


from .main import get_db
from .main.controller import (
    baby_controller, feeding_controller, sleep_controller, diaper_controller, health_controller,
    doctor_visit_controller, growth_controller, medication_controller, milestone_controller, pumping_controller,
    photo_controller, dashboard_controller, tool_controller, query_controller
)

from .main.controller.coparent_controller import router as coparent_router
from .main.controller.notification_controller import router as notification_router
from .main.controller.auth_controller import router as auth_router
from .main.model.baby import router as baby_router
from .main.model.user import router as user_router
from .main.model.feeding import router as feeding_router
from .main.model.sleep import router as sleep_router
from .main.model.diaper import router as diaper_router
from .main.model.health import router as health_router
from .main.model.growth import router as growth_router
from .main.model.milestone import router as milestone_router
from .main.model.doctor_visit import router as doctor_visit_router
from .main.model.medication import router as medication_router
from .main.model.pumping import router as pumping_router
from .main.model.photo import router as photo_router
from .main.model.dashboard import router as dashboard_router
from .main.model.tool import router as tool_router
from .main.model.query import router as query_router


def create_app():
    app = FastAPI(
        title='BABIES APP',
        version='1.0',
        description='FastAPI web service for babies and measurements with Google OAuth authentication and co-parenting features'
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust this in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files BEFORE defining routes
    # This is important for proper resolution
    if Path("pages").exists():
        # Mount the entire pages directory at root for assets
        app.mount("/pages", StaticFiles(directory="pages"), name="pages")

        # Also mount at /static for backward compatibility
        app.mount("/static", StaticFiles(directory="pages"), name="static")

    # Include routers
    app.include_router(baby_router)
    app.include_router(user_router)
    app.include_router(auth_router)
    app.include_router(coparent_router)
    app.include_router(notification_router)
    app.include_router(feeding_router)
    app.include_router(sleep_router)
    app.include_router(diaper_router)
    app.include_router(health_router)
    app.include_router(growth_router)
    app.include_router(milestone_router)
    app.include_router(doctor_visit_router)
    app.include_router(medication_router)
    app.include_router(pumping_router)
    app.include_router(photo_router)
    app.include_router(dashboard_router)
    app.include_router(tool_router)
    app.include_router(query_router)

    # Helper function to generate error HTML
    def generate_error_html(title: str, message: str, suggestion: str = None) -> str:
        suggestion_html = f'<p class="suggestion">{suggestion}</p>' if suggestion else ''
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                h1 {{
                    color: #333;
                    margin-bottom: 20px;
                }}
                .error {{
                    color: #e74c3c;
                    font-size: 72px;
                    margin: 0;
                    font-weight: bold;
                }}
                .message {{
                    color: #666;
                    margin: 20px 0;
                    font-size: 18px;
                }}
                .suggestion {{
                    color: #888;
                    font-size: 14px;
                    margin: 15px 0;
                }}
                .actions {{
                    margin-top: 30px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 12px 24px;
                    margin: 0 10px;
                    background-color: #4285f4;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    transition: background-color 0.3s;
                }}
                .btn:hover {{
                    background-color: #357ae8;
                }}
                .btn-secondary {{
                    background-color: #f8f9fa;
                    color: #333;
                    border: 1px solid #ddd;
                }}
                .btn-secondary:hover {{
                    background-color: #e9ecef;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <p class="error">{title}</p>
                <p class="message">{message}</p>
                {suggestion_html}
                <div class="actions">
                    <a href="/" class="btn">Go to Home</a>
                    <a href="javascript:history.back()" class="btn btn-secondary">Go Back</a>
                </div>
            </div>
        </body>
        </html>
        """

    # Helper function to check authentication from sessionStorage
    def generate_auth_check_html(redirect_to: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Checking Authentication...</title>
            <script>
                // Check if user is authenticated by looking for token in sessionStorage
                const token = sessionStorage.getItem('idToken');

                if (!token) {{
                    // No token found, redirect to login
                    window.location.href = '/auth/login';
                }} else {{
                    // Token exists, but we need to verify it's still valid
                    // This is a client-side check, server will do the real validation
                    window.location.href = '{redirect_to}';
                }}
            </script>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }}
                .container {{
                    text-align: center;
                    padding: 40px;
                    background: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .spinner {{
                    border: 3px solid #f3f3f3;
                    border-top: 3px solid #4285f4;
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
                <h2>Checking Authentication...</h2>
                <div class="spinner"></div>
                <p>Please wait while we verify your access.</p>
            </div>
        </body>
        </html>
        """

    @app.get("/")
    async def root():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/index.html", media_type="text/html")

    @app.get("/onboarding")
    async def onboarding():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/onboarding.html", media_type="text/html")

    @app.get("/dashboard")
    async def dashboard():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/dashboard.html", media_type="text/html")

    @app.get("/diaper-tracker")
    async def diaper_tracker():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/diaper_tracker.html", media_type="text/html")

    @app.get("/doctor-tracker")
    async def doctor_tracker():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/doctor_tracker.html", media_type="text/html")

    @app.get("/feeding-tracker")
    async def feeding_tracker():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/feeding_tracker.html", media_type="text/html")

    @app.get("/growth-tracker")
    async def growth_tracker():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/growth_tracker.html", media_type="text/html")

    @app.get("/medicine-tracker")
    async def medicine_tracker():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/medicine_tracker.html", media_type="text/html")

    @app.get("/milestone-tracker")
    async def milestone_tracker():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/milestone_tracker.html", media_type="text/html")

    @app.get("/sleep-tracker")
    async def sleep_tracker():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/sleep_tracker.html", media_type="text/html")

    @app.get("/settings")
    async def settings():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/settings.html", media_type="text/html")

    @app.get("/insights-analysis")
    async def insights_analysis():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/insights_analysis.html", media_type="text/html")

    @app.get("/ai-assistant")
    async def ai_assistant():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/ai_assistant.html", media_type="text/html")

    @app.get("/baby-profile")
    async def baby_profile():
        """Redirect to static HTML file to maintain relative paths"""
        return FileResponse("pages/html/baby.html", media_type="text/html")

    @app.get("/system-architecture.png")
    async def serve_architecture_image():
        """Serve the architecture image directly"""
        return FileResponse("pages/media/system-architecture.png", media_type="image/png")

    @app.get("/js/auth.js")
    async def serve_auth_script():
        """Serve the auth JavaScript file"""
        return FileResponse("pages/js/auth.js", media_type="application/javascript")

    # Custom 404 handler
    @app.exception_handler(404)
    async def custom_404_handler(request: Request, exc):
        return HTMLResponse(
            content=generate_error_html(
                "404",
                "Page not found",
                f"The page '{request.url.path}' doesn't exist."
            ),
            status_code=404
        )

    # Custom 401 handler for authentication errors
    @app.exception_handler(401)
    async def custom_401_handler(request: Request, exc):
        return HTMLResponse(
            content=generate_error_html(
                "401",
                "Authentication Required",
                "You need to sign in to access this page."
            ),
            status_code=401
        )

    # Custom 403 handler for forbidden/not authenticated errors
    @app.exception_handler(403)
    async def custom_403_handler(request: Request, exc):
        return HTMLResponse(
            content=generate_error_html(
                "403",
                "Authentication Required",
                "You need to sign in to access this page."
            ),
            status_code=403
        )

    # Custom 405 handler for forbidden/not authenticated errors for trying to use methods
    @app.exception_handler(405)
    async def custom_405_handler(request: Request, exc):
        return HTMLResponse(
            content=generate_error_html(
                "405",
                "Authentication Required to use this method.",
                "You need to sign in to access this method."
            ),
            status_code=405
        )

    # Custom 500 handler
    @app.exception_handler(500)
    async def custom_500_handler(request: Request, exc):
        return HTMLResponse(
            content=generate_error_html(
                "500",
                "Internal Server Error",
                "Go back to Safety"
            ),
            status_code=500
        )

    # Custom 422 handler for validation errors
    @app.exception_handler(RequestValidationError)
    async def custom_422_handler(request: Request, exc: RequestValidationError):
        # Print request info for debugging
        body = await request.body()
        print(f"422 Error - Request path: {request.url.path}")
        print(f"Request body: {body.decode('utf-8')}")
        print(f"Validation errors: {exc.errors()}")

        return HTMLResponse(
            content=generate_error_html(
                "422",
                "Unprocessable Entity",
                "The request data was invalid. Check your input and try again."
            ),
            status_code=422
        )

    return app