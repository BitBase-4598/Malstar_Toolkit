from fastapi import APIRouter

from db_engine import ping
from webutil import respond

router = APIRouter()


@router.get("/api/health")
def health():
    try:
        ping()
    except Exception:
        return respond({
            "success": False,
            "message": "MALSTAR_Toolkit API cannot reach the database.",
        }, 503)
    return respond({"success": True, "message": "MALSTAR_Toolkit API is running"})
