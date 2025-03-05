import os
import logging
from typing import Optional

from src.config import config

def setup_logger(component: str, log_dir: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger for a specific component
    
    Args:
        component: Name of the component ('camera', 'flask', 'system', etc.)
        log_dir: Optional custom log directory
        
    Returns:
        logging.Logger: Configured logger instance
        
    Raises:
        ValueError: If component is unknown
    """
    # Use the log directory from config if not specified
    log_dir = log_dir or config.log_dir
    os.makedirs(log_dir, exist_ok=True)
    
    # Define standard log files
    log_files = {
        'system': 'cosmicam.log',       # General system logs
        'fan': 'fan_control.log',       # Fan control specific logs
        'camera': 'image_capture.log',  # Image capture logs
        'flask': 'flask.log',           # Flask backend logs
        'config': 'config.log'          # Configuration changes
    }
    
    # Normalize component name
    component = component.lower()
    if component not in log_files:
        raise ValueError(f"Unknown component: {component}")

    # Create logger
    logger = logging.getLogger(component.upper())
    logger.setLevel(logging.INFO)

    # Clear any existing handlers
    logger.handlers = []

    # Create file handler
    file_handler = logging.FileHandler(
        os.path.join(log_dir, log_files[component])
    )
    file_handler.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(message)s'
    )

    # Add formatter to handlers
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
