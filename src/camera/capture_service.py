import os
import time
import logging
import sys
from typing import Optional

from src.config import config
from .camera_controller import CameraController

class ImageCaptureService:
    """
    Service that manages continuous image capture
    
    This class:
    - Initializes the camera controller
    - Runs a continuous loop to capture images at regular intervals
    - Manages error handling and logging
    """
    def __init__(self, logger=None):
        """
        Initialize the image capture service
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("CAMERA")
        self.logger.info("Initializing ImageCaptureService...")
        
        # Get app directories
        self.app_root = os.environ.get('COSMICAM_ROOT', 
                                       os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.logger.info(f"Application root: {self.app_root}")
        
        self.image_dir = config.get_image_dir()
        self.logger.info(f"Image directory: {self.image_dir}")
        
        # Get initial system settings
        self.system_settings = config.get_config('system_settings')
        self.logger.info(f"Loaded system settings: {self.system_settings}")
        
        # Initialize disk space manager
        # Imported below to avoid Python circular imports
        self.disk_manager = None
        
        # Initialize camera controller
        self.camera = CameraController(self.image_dir, logger=self.logger)
        self.running = False
        
        # Set initial capture interval
        capture_interval = self.system_settings.get('capture_interval', 60)
        self.camera.set_capture_interval(capture_interval)
        self.logger.info(f"Initial capture interval set to {capture_interval} seconds")

    def start(self):
        """Start the image capture service loop"""
        self.running = True
        self.camera.ensure_directory_exists()
        
        # Import and initialize disk manager 
        from src.utils.disk_manager import DiskSpaceManager
        max_disk_usage = self.system_settings.get('max_disk_usage_gb', 20)
        self.disk_manager = DiskSpaceManager(self.image_dir, max_disk_usage, self.logger)
        self.logger.info(f"Disk manager initialized with max usage: {max_disk_usage} GB")
        
        self.logger.info("Starting image capture service")
        
        while self.running:
            try:
                # Reload system settings to check for changes
                self.system_settings = config.get_config('system_settings')
                
                # Update capture interval if changed
                capture_interval = self.system_settings.get('capture_interval', 60)
                self.camera.set_capture_interval(capture_interval)
                
                # Update disk manager settings if changed
                if self.disk_manager:
                    max_disk_usage = self.system_settings.get('max_disk_usage_gb', 40)
                    self.disk_manager.max_disk_usage_gb = max_disk_usage
                
                # Update settings before each capture
                self.camera.settings.update_profile_from_sun_phase()
                
                # Perform image capture
                captured_image = self.camera.capture_image()
                if captured_image:
                    self.logger.info(f"Successfully captured image: {captured_image}")
                    self.logger.info(f"Current profile: {self.camera.settings.current_profile}")
                    
                    # Run disk space cleanup after successful capture
                    if self.disk_manager:
                        self.disk_manager.cleanup_if_needed()
                
                # Wait until next capture
                time.sleep(self.camera.capture_interval)
                
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                time.sleep(5)  # Wait before retrying

    def stop(self):
        """Stop the image capture service"""
        self.running = False
        self.logger.info("Stopping image capture service")


def main():
    """Main entry point for running the image capture service"""
    # Configure logging
    from src.utils.logging import setup_logger
    logger = setup_logger('camera')
    
    # Create and start the service
    service = ImageCaptureService(logger=logger)
    try:
        service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        service.stop()
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        service.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
