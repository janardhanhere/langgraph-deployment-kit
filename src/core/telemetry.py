from typing import Optional
import os
import logging
from langfuse.callback import CallbackHandler
from core import settings
from pydantic import SecretStr

logger = logging.getLogger(__name__)

def get_langfuse_callback(user_id: Optional[str] = None, session_id: Optional[str] = None) -> Optional[CallbackHandler]:
    """
    Creates and returns a Langfuse callback handler if credentials are configured.
    Returns None if credentials are not found.
    
    Args:
        user_id: Optional user ID to associate with traces
        session_id: Optional session ID to associate with traces (typically the thread_id)
    """
    # In deployment mode, we still want to enable telemetry if credentials are available
    # Get Langfuse credentials from environment variables or settings
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY") or getattr(settings, "LANGFUSE_PUBLIC_KEY", None)
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY") or getattr(settings, "LANGFUSE_SECRET_KEY", None)
    host = os.environ.get("LANGFUSE_HOST") or getattr(settings, "LANGFUSE_HOST", None) or "https://cloud.langfuse.com"
    
    # Check if credentials are available
    if not public_key or not secret_key:
        return None
    
    # Handle SecretStr type
    if isinstance(public_key, SecretStr):
        public_key = public_key.get_secret_value()
    if isinstance(secret_key, SecretStr):
        secret_key = secret_key.get_secret_value()
    
    # Create the handler with necessary parameters
    try:
        handler_args = {
            "public_key": public_key,
            "secret_key": secret_key,
            "host": host
        }
        
        # Add user_id if provided
        if user_id:
            handler_args["user_id"] = user_id
        
        # Add session_id if provided
        if session_id:
            handler_args["session_id"] = session_id
        
        return CallbackHandler(**handler_args)
    except Exception as e:
        logger.error(f"Error creating Langfuse callback handler: {e}")
        return None