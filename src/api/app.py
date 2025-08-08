from flask import Flask
import logging
from dotenv import load_dotenv

from src.config import config
from src.utils import setup_logger
from .routes import register_routes

load_dotenv()

def create_app():
    """
    Create and configure the Flask application
    
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Set up logging
    logger = setup_logger('flask')
    
    # Register routes
    register_routes(app)
    
    return app
