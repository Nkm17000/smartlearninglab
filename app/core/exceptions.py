from fastapi import HTTPException

def not_found(resource: str):
    return HTTPException(status_code=404, detail=f"{resource} not found")

def bad_request(message: str):
    return HTTPException(status_code=400, detail=message)
