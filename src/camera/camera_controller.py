import os
import subprocess
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from .camera_settings import CameraSettings
from .image_processor import BasicProcessor

class CameraController:
    """
    Controls the camera hardware and captures images
    
    This class is responsible for:
    - Building and executing libcamera commands
    - Capturing images with the appropriate settings
    - Processing captured images using the configured processor
    """
    def __init__(self, image_dir: str, logger=None):
        """
        Initialize the camera controller
        
        Args:
            image_dir: Directory where images will be stored
            logger: Optional logger instance
        """
        self.image_dir = image_dir
        self.logger = logger or logging.getLogger("CAMERA")
        self.settings = CameraSettings(logger=self.logger)
        self.processor = BasicProcessor(logger=self.logger)
        self.last_capture_time = 0
        self.capture_interval = 60  # seconds

    def ensure_directory_exists(self):
        """Ensure that the image directory exists"""
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)
            self.logger.info(f"Created directory: {self.image_dir}")

    def build_libcamera_command(self, filepath: str, settings: Dict[str, Any]) -> List[str]:
        """Build the libcamera command with all relevant parameters"""
        cmd = [
            "libcamera-still",
            "-o", filepath,
            "--width", "4056",
            "--height", "3040"
        ]
    
        # Handle shutter speed
        if settings.get("shutter_speed", 0) > 0:
            cmd.extend(["--shutter", str(settings["shutter_speed"])])
    
        # Changed to use analoggain instead of gain
        if settings.get("gain", 0) > 0:
            cmd.extend(["--analoggain", str(settings["gain"])])
    
        # Only add brightness if is </> 0 and is not None
        brightness = settings.get("brightness")
        if brightness is not None and brightness != 0:
            cmd.extend(["--brightness", str(brightness)])
    
        # Only add contrast if it exists and is greater than 0
        if settings.get("contrast", 0) > 0:
            cmd.extend(["--contrast", str(settings["contrast"])])
    
        # Add AWB gains if they exist
        if "awbgains" in settings and settings["awbgains"]:
            # Handle both array format [2.5, 2.0] and string format "2.5,2.0"
            if isinstance(settings["awbgains"], list):
                red_gain, blue_gain = settings["awbgains"]
                awb_value = f"{red_gain},{blue_gain}"
            else:
                awb_value = str(settings["awbgains"])
            cmd.extend(["--awbgains", awb_value])
    
        # Add immediate flag if specified
        if settings.get("immediate", False):
            cmd.append("--immediate")
    
        return cmd

    def capture_image(self) -> Optional[str]:
        """
        Capture an image using current settings
        
        Returns:
            Optional[str]: Path to the captured image, or None if capture failed
        """
        try:
            # Log start of capture process
            self.logger.info("=" * 50)
            self.logger.info("Starting new image capture")

            # Force update of camera profile and settings before capture
            self.settings.update_profile_from_sun_phase()
            
            # Get current settings and log them
            current_settings = self.settings.get_current_settings()
            self.logger.info("Current camera settings:")
            for setting, value in current_settings.items():
                self.logger.info(f"  {setting}: {value}")
            
            # Create filename and build command
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.jpg"
            filepath = os.path.join(self.image_dir, filename)
            
            # Build and log command
            cmd = self.build_libcamera_command(filepath, current_settings)
            cmd_str = " ".join(cmd)
            self.logger.info(f"Executing libcamera command: {cmd_str}")
            
            # Execute capture with timing
            start_time = time.time()
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            capture_duration = time.time() - start_time
            
            # Log capture results
            self.logger.info(f"Image captured successfully: {filename}")
            self.logger.info(f"Capture duration: {capture_duration:.2f} seconds")
            
            if result.stdout:
                self.logger.info(f"libcamera output: {result.stdout}")
            
            # Process image
            processed_path = self.processor.process(filepath)
            self.logger.info(f"Image processing complete: {processed_path}")
            self.logger.info("=" * 50)
            
            return processed_path
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to capture image: {e}")
            if e.stderr:
                self.logger.error(f"libcamera error output: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during capture: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """
        Update camera settings
        
        Args:
            new_settings: New settings to apply to the current profile
        """
        self.settings.update_profile(self.settings.current_profile, new_settings)

    def set_capture_interval(self, interval: int) -> None:
        """
        Set the interval between captures in seconds
        
        Args:
            interval: Time between captures in seconds (minimum 1)
        """
        self.capture_interval = max(1, interval)
