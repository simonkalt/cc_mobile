"""
Logging configuration
"""
import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure application logging
    
    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Override any existing configuration
    )
    
    # Set logger levels
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    
    # Configure uvicorn loggers
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)

