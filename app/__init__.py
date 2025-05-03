from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from .main.model.baby import router as baby_router
from .main.model.user import router as user_router
from .main.controller.auth_controller import router as auth_router
from .main.controller import baby_controller

def create_app():
    app = FastAPI(
        title='BABIES APP',
        version='1.0',
        description='FastAPI web service for babies and measurements with Google OAuth authentication'
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust this in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(baby_router)
    app.include_router(user_router)
    app.include_router(auth_router)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Root endpoint with OAuth login instructions"""
        return """
        <html>
            <head>
                <title>Babies App - Google OAuth</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                    .container { border: 1px solid #ccc; padding: 20px; border-radius: 5px; }
                    code { background-color: #f0f0f0; padding: 2px 4px; border-radius: 4px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Baby App with Google OAuth</h1>
                    <h2>Authentication Instructions</h2>
                    <ol>
                        <li>Go to <a href="/auth/login" target="_blank">/auth/login</a> endpoint</li>
                        <li>Copy the <code>login_url</code> from the response</li>
                        <li>Open that URL in your browser</li>
                        <li>Log in with your Google account</li>
                        <li>You'll be redirected back with an ID token</li>
                        <li>Use this token as a Bearer token in the <a href="/docs" target="_blank">Swagger UI</a></li>
                    </ol>
                    <p>
                        <a href="/docs" target="_blank">Go to Swagger UI</a>
                    </p>
                </div>
            </body>
        </html>
        """

    return app