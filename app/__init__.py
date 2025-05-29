from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse


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

                    <h2>Co-Parenting Features</h2>
                    <ul>
                        <li>Add babies to your profile as the primary parent</li>
                        <li>Invite other users to be co-parents for your babies</li>
                        <li>Accept or reject co-parent invitations</li>
                        <li>View and manage notifications</li>
                    </ul>

                    <h2>Tracking Features</h2>
                    <ul>
                        <li>Feeding: Track breastfeeding, bottle feeding, and solid foods</li>
                        <li>Sleep: Record sleep patterns and quality</li>
                        <li>Diaper: Monitor diaper changes and content</li>
                        <li>Health: Track temperature, symptoms, and medications</li>
                    </ul>
                </div>
            </body>
        </html>
        """

    return app