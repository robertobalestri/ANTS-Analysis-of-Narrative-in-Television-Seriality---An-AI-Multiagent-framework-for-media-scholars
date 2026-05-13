from fastapi import APIRouter, HTTPException
from typing import List, Dict
from pydantic import BaseModel
import os
import logging
from app.core.config import REQUIRED_ENV_VARS, save_env_vars

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

class EnvVarResponse(BaseModel):
    name: str
    value: str
    description: str
    required: bool

class EnvUpdateSchema(BaseModel):
    settings: Dict[str, str]

@router.get("/env", response_model=List[EnvVarResponse])
async def get_env_settings():
    """Get the current environment variables and their specifications."""
    try:
        logger.info(f"Fetching env settings. Found {len(REQUIRED_ENV_VARS)} total specs.")
        response = []
        for spec in REQUIRED_ENV_VARS:
            # Skip hidden variables
            if not spec.visible:
                continue
                
            raw_value = os.getenv(spec.name, spec.default or "")
            response.append(EnvVarResponse(
                name=spec.name,
                value=raw_value,
                description=spec.description,
                required=spec.required
            ))
        return response
    except Exception as e:
        logger.error(f"Error fetching env settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/env")
async def update_env_settings(update_data: EnvUpdateSchema):
    """Update the .env file with new values."""
    try:
        success = save_env_vars(update_data.settings)
        if success:
            return {"message": "Settings updated successfully. You may need to restart the server for some changes to take effect."}
        else:
            raise HTTPException(status_code=500, detail="Failed to save settings")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
