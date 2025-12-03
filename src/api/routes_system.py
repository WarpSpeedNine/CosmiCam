from flask import Flask, jsonify, Response, request
import logging

from src.utils.auth import require_admin_access
from src.config import config


def register_system_routes(app: Flask):
    """
    Register system_settings related API endpoints
    
    Args: 
        app: Flask application instance
    """
    logger = logging.getLogger("FLASK")

    @app.route('/api/system/settings', methods=['PUT'])
    @require_admin_access
    def update_system_settings() -> Response:
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No Data Sent in Request"}), 400

            current_system_settings = config.get_config('system_settings')
            if not current_system_settings:
                return jsonify({"error": "Unable to retrieve current system settings"}), 500

            valid_top_level = ['capture_interval', 'max_disk_usage_gb', 'fan_control']
            valid_fan_control = ['log_interval', 'min_temp', 'max_temp']

            for setting_name, value in data.items():                
                if setting_name not in valid_top_level:
                    return jsonify({'error': f'Invalid setting: {setting_name}'}), 400

                if setting_name == 'fan_control':                    
                    if not isinstance(value, dict):
                        return jsonify({'error': 'fan_control must be an object'}), 400                    
                   
                    for fan_setting, fan_value in value.items():
                        if fan_setting not in valid_fan_control:
                            return jsonify({'error': f'Invalid fan_control setting: {fan_setting}'}), 400

                    if 'fan_control' not in current_system_settings:
                        current_system_settings['fan_control'] = {}
                    current_system_settings['fan_control'].update(value)
                
                else:                    
                    current_system_settings[setting_name] = value

            success = config.update_config('system_settings', current_system_settings)
            if success:
                return jsonify({'message': 'System settings updated successfully'}), 200
            else:
                return jsonify({'error': 'Failed to update system settings'}), 500

        except Exception as e:
            logger.exception("Error updating system settings")
            return jsonify({'error': str(e)}), 500