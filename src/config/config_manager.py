# src/config/config_manager.py
import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """
    Centralized configuration management for CosmiCam
    
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, 'initialized'):
            return
            
        # Base directory paths
        self.app_root = os.environ.get('COSMICAM_ROOT', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        # Configuration directories
        self.config_dir = os.path.join(self.app_root, 'src', 'config')
        self.log_dir = '/var/log/cosmicam'
        
        # Default configurations
        self.defaults = {
            'coordinates': {
                'latitude': 32.7,  # DFW
                'longitude': -97.3
            },
            'camera_profiles': {
                'default': {
                    'shutter_speed': 0,
                    'gain': 0,
                    'brightness': 0,
                    'contrast': 1.0
                },
                'day': {
                    'shutter_speed': 0,
                    'gain': 0,
                    'brightness': 0,
                    'contrast': 1.0
                },
                'civil_twilight': {
                    'shutter_speed': 100000,
                    'gain': 1.5,
                    'brightness': 0.2,
                    'contrast': 1.1
                },
                'nautical_twilight': {
                    'shutter_speed': 1000000,
                    'gain': 1.8,
                    'brightness': 0.3,
                    'contrast': 1.2
                },
                'astronomical_twilight': {
                    'shutter_speed': 3000000,
                    'gain': 2.0,
                    'brightness': 0.4,
                    'contrast': 1.3
                },
                'night': {
                    'shutter_speed': 6000000,
                    'gain': 2.0,
                    'brightness': 0.5,
                    'contrast': 1.4
                }
            },
            'system_settings': {
                'capture_interval': 60,
                'max_disk_usage_gb': 20,
                'fan_control': {
                    'log_interval': 300,
                    'min_temp': 40,
                    'max_temp': 80
                }
            }
        }
        
        # Set up basic logging until the logging module is initialized
        self._setup_logging()
        
        self.logger.info(f"Initializing ConfigManager with app root: {self.app_root}")
        self.logger.info(f"Config directory: {self.config_dir}")
        
        # Ensure the config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Configuration file paths (support both YAML and JSON)
        self.config_files = {
            'coordinates': os.path.join(self.config_dir, 'coordinates.yaml'),
            'camera_profiles': os.path.join(self.config_dir, 'camera_profiles.yaml'),
            'system_settings': os.path.join(self.config_dir, 'system_settings.yaml')
        }
        
        # JSON fallbacks for backward compatibility
        self.json_fallbacks = {
            'coordinates': os.path.join(self.config_dir, 'coordinates.json'),
            'camera_profiles': os.path.join(self.config_dir, 'camera_profiles.json'),
            'system_settings': os.path.join(self.config_dir, 'system_settings.json')
        }
        
        # Initialize configuration files if they don't exist
        self._init_config_files()
        
        self.initialized = True

    def _setup_logging(self) -> None:
        """Configure basic logging for the configuration manager"""
        os.makedirs(self.log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(self.log_dir, 'cosmicam.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("CONFIG")

    def _init_config_files(self) -> None:
        """Initialize configuration files with default values if they don't exist"""
        for config_name, filepath in self.config_files.items():
            # Check if YAML file exists
            if not os.path.exists(filepath):
                # Check if JSON fallback exists
                json_path = self.json_fallbacks[config_name]
                if os.path.exists(json_path):
                    # Convert JSON to YAML
                    try:
                        with open(json_path, 'r') as f:
                            config_data = json.load(f)
                        
                        # Write as YAML
                        with open(filepath, 'w') as f:
                            yaml.dump(config_data, f, default_flow_style=False)
                        
                        self.logger.info(f"Converted JSON to YAML: {json_path} -> {filepath}")
                    except Exception as e:
                        self.logger.error(f"Failed to convert JSON to YAML: {e}")
                        # Fall back to creating default YAML
                        with open(filepath, 'w') as f:
                            yaml.dump(self.defaults[config_name], f, default_flow_style=False)
                else:
                    # Create default YAML file
                    self.logger.info(f"Creating default configuration file: {filepath}")
                    with open(filepath, 'w') as f:
                        yaml.dump(self.defaults[config_name], f, default_flow_style=False)
            else:
                # Verify file is valid YAML
                try:
                    with open(filepath, 'r') as f:
                        yaml.safe_load(f)
                except yaml.YAMLError:
                    self.logger.error(f"Invalid YAML in {filepath}, restoring defaults")
                    with open(filepath, 'w') as f:
                        yaml.dump(self.defaults[config_name], f, default_flow_style=False)
    
    def get_config(self, config_name: str) -> Dict[str, Any]:
        """
        Read configuration from specified config file
        
        Args:
            config_name: Name of the configuration to retrieve
            
        Returns:
            Dict containing the configuration data
            
        Raises:
            ValueError: If the config_name is unknown
        """
        if config_name not in self.config_files:
            raise ValueError(f"Unknown configuration: {config_name}")
            
        try:
            # Try loading YAML first
            yaml_path = self.config_files[config_name]
            if os.path.exists(yaml_path):
                with open(yaml_path, 'r') as f:
                    return yaml.safe_load(f)
            
            # Fall back to JSON if it exists
            json_path = self.json_fallbacks[config_name]
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    return json.load(f)
                    
        except Exception as e:
            self.logger.error(f"Error reading {config_name} configuration: {e}")
            
        # Return defaults if loading failed
        self.logger.info(f"Using default configuration for {config_name}")
        return self.defaults[config_name]
            
    def update_config(self, config_name: str, data: Dict[str, Any]) -> bool:
        """
        Update specified configuration file
        
        Args:
            config_name: Name of the configuration to update
            data: New configuration data to merge with existing data
            
        Returns:
            bool: True if update was successful, False otherwise
            
        Raises:
            ValueError: If the config_name is unknown
        """
        if config_name not in self.config_files:
            raise ValueError(f"Unknown configuration: {config_name}")
            
        try:
            filepath = self.config_files[config_name]
            
            # Read existing config (YAML)
            current_config = self.get_config(config_name)
            
            # Update with new data
            current_config.update(data)
            
            # Write back to YAML file
            with open(filepath, 'w') as f:
                yaml.dump(current_config, f, default_flow_style=False)
            
            self.logger.info(f"Updated {config_name} configuration")
            return True
        except Exception as e:
            self.logger.error(f"Error updating {config_name} configuration: {e}")
            return False

    def get_image_dir(self) -> str:
        """Get the path to the image storage directory"""
        return os.path.join(self.app_root, 'images')
