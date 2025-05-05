import asyncio
import logging
import sys

import uvicorn
from dotenv import load_dotenv

from core import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Set more detailed logging for telemetry components
logging.getLogger('core.telemetry').setLevel(logging.DEBUG)
logging.getLogger('langfuse').setLevel(logging.DEBUG)

load_dotenv()

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Log deployment mode status
    if settings.MODE == "deployment":
        logger.info(
            "Running in DEPLOYMENT mode. This mode is for deploying pre-built agents only."
            " No LLM API keys are required in this mode."
        )
    else:
        logger.info(
            "Running in normal mode. LLM API keys will be required for agent operation."
            " To run in deployment-only mode (for pre-built agents), set MODE=deployment"
            " in your .env file."
        )
    
    # Set Compatible event loop policy on Windows Systems.
    # On Windows systems, the default ProactorEventLoop can cause issues with
    # certain async database drivers like psycopg (PostgreSQL driver).
    # The WindowsSelectorEventLoopPolicy provides better compatibility and prevents
    # "RuntimeError: Event loop is closed" errors when working with database connections.
    # This needs to be set before running the application server.
    # Refer to the documentation for more information.
    # https://www.psycopg.org/psycopg3/docs/advanced/async.html#asynchronous-operations
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run("service:app", host=settings.HOST, port=settings.PORT, reload=settings.is_dev())
