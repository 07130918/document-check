"""Hello endpoint router."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/hello")
async def get_hello():
    """
    Returns a hello message.
    
    Returns:
        dict: A dictionary containing the hello message.
    """
    return {"message": "Hello API"}