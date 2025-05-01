from fastapi import FastAPI
from .main.model.baby import router as baby_router
from .main.controller import baby_controller

def create_app():
    app = FastAPI(
        title='BABIES APP',
        version='1.0',
        description='FastAPI web service for babies and measurements'
    )

    app.include_router(baby_router)

    return app