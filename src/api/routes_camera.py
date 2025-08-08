from flask import Flask, jsonify, Response, request
import logging

from src.utils.auth import require_admin_access
from src.config import config
from src.camera import CameraSettings

def register_camera_routes(app: Flask):
    """
    Register camera-related API routes
    
    Args:
        app: Flask application instance
    """
    logger = logging.getLogger("FLASK")
    camera_settings = CameraSettings(logger=logger)
    
    @app.route('/api/coordinates', methods=['GET', 'POST'])
    @require_admin_access
    def handle_coordinates() -> Response:
        """Get or update geographic coordinates"""
        try:
            if request.method == 'GET':
                coords = config.get_config('coordinates')
                return jsonify(coords), 200
                
            elif request.method == 'POST':
                data = request.get_json()
                if not data or 'latitude' not in data or 'longitude' not in data:
                    return jsonify({'error': 'Missing coordinates'}), 400
                    
                success = camera_settings.update_coordinates(
                    float(data['latitude']),
                    float(data['longitude'])
                )
                
                if success:
                    camera_settings.update_profile_from_sun_phase()
                    return jsonify({'message': 'Coordinates updated successfully'}), 200
                else:
                    return jsonify({'error': 'Failed to update coordinates'}), 500
                    
        except Exception as e:
            logger.exception("Error handling coordinates")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/camera/profile', methods=['GET'])
    def get_camera_profile() -> Response:
        """Get current camera profile and settings"""
        try:
            # First update the profile based on sun phase
            camera_settings.update_profile_from_sun_phase()
            logger.info(f"Updated profile based on sun phase: {camera_settings.current_profile}")
            
            # Then get the current settings and sun phase
            current_settings = camera_settings.get_current_settings()
            sun_phase = camera_settings.get_sun_phase()
            
            response_data = {
                'current_profile': camera_settings.current_profile,
                'settings': current_settings,
                'sun_phase': sun_phase
            }
            
            logger.debug(f"Returning camera profile data: {response_data}")
            return jsonify(response_data), 200
            
        except Exception as e:
            logger.exception("Error getting camera profile")
            return jsonify({'error': str(e)}), 500
