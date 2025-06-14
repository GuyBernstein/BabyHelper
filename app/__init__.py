from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

    # Mount static files directory (this will serve all files in the pages directory)
    if Path("pages").exists():
        app.mount("/static", StaticFiles(directory="pages"), name="static")

    @app.get("/")
    async def root():
        """Root endpoint serving static HTML file"""
        # Construct the path to the HTML file
        html_file_path = Path("pages/html/index.html")

        # Check if file exists, if not return a 404 or fallback
        if not html_file_path.exists():
            return {"error": "HTML file not found at pages/html/index.html"}

        return FileResponse(html_file_path, media_type="text/html")

    @app.get("/onboarding")
    async def onboarding():
        """Root endpoint serving static HTML file"""
        # Construct the path to the HTML file
        html_file_path = Path("pages/html/onboarding.html")

        # Check if file exists, if not return a 404 or fallback
        if not html_file_path.exists():
            return {"error": "HTML file not found at pages/html/onboarding.html"}

        return FileResponse(html_file_path, media_type="text/html")

    return app