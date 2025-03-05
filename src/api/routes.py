from flask import Flask
import logging

from .routes_image import register_image_routes
from .routes_camera import register_camera_routes

def register_routes(app: Flask):
    """
    Register all API routes with the Flask application
    
    Args:
        app: Flask application instance
    """
    # Register route groups
    register_image_routes(app)
    register_camera_routes(app)
    
    # Register error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
        
    @app.errorhandler(500)
    def server_error(error):
        logger = logging.getLogger("FLASK")
        logger.error(f"Server error: {error}")
        return {'error': 'Internal server error'}, 500
