import os
from datetime import datetime
from flask import Flask, jsonify, Response
import logging

from src.config import config
from src.camera import CameraSettings

def register_image_routes(app: Flask):
    """
    Register image-related API routes
    
    Args:
        app: Flask application instance
    """
    logger = logging.getLogger("FLASK")
    camera_settings = CameraSettings(logger=logger)
    
    @app.route('/api/latest-image', methods=['GET'])
    def get_latest_image() -> Response:
        """Get the latest captured image"""
        image_dir = config.get_image_dir()
        logger.info(f"Latest-image API called, checking directory: {image_dir}")
        
        try:
            # Define valid image extensions
            valid_extensions = {'.jpg', '.jpeg', '.png'}
            
            # Use a generator to avoid loading all files into memory
            def get_image_files():
                with os.scandir(image_dir) as entries:
                    for entry in entries:
                        if entry.is_file():
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in valid_extensions:
                                yield entry

            # Find latest image
            latest_entry = None
            latest_time = 0
            
            for entry in get_image_files():
                try:
                    entry_time = entry.stat().st_ctime
                    if entry_time > latest_time:
                        latest_time = entry_time
                        latest_entry = entry
                except OSError as e:
                    logger.warning(f"Error accessing file {entry.name}: {e}")
                    continue
            
            if not latest_entry:
                logger.error(f"No valid images found in {image_dir}")
                return jsonify({'error': 'No images found'}), 404
                
            # Verify file is readable
            if not os.access(latest_entry.path, os.R_OK):
                logger.error(f"File not readable: {latest_entry.path}")
                return jsonify({'error': 'Image file not accessible'}), 403
                
            # Get file timestamp
            timestamp = latest_time
        
            # Force fresh read of camera profiles
            camera_profiles = config.get_config('camera_profiles')

            # Update camera settings to ensure we're returning current sun phase
            camera_settings.update_profile_from_sun_phase()
            current_profile = camera_settings.current_profile

            # Get settings directly from freshly read config
            current_settings = camera_profiles[current_profile]
            
            response_data = {
                'path': f'/images/{latest_entry.name}',
                'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                'sun_phase': camera_settings.get_sun_phase(),
                'camera_profile': current_profile,
                'camera_settings': current_settings
            }
            
            logger.debug(f"Returning response: {response_data}")
            return jsonify(response_data), 200
            
        except Exception as e:
            logger.exception("Error in get_latest_image")
            return jsonify({'error': str(e)}), 500
