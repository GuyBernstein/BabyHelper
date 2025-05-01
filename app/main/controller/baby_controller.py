from fastapi import APIRouter
from ..model.baby import router

@router.get('/')
async def get_baby():
    """Hello world"""
    return "Hello world"