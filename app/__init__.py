from fastapi import FastAPI
from .main.controller import baby_controller
from app.main.model.baby import router as baby_router

def create_app():
    app = FastAPI(
        title='BABIES APP',
        version='1.0',
        description='FastAPI web service for babies and measurements'
    )

    app.include_router(baby_router)

    return app