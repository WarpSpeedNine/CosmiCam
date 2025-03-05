import math
import logging
from datetime import datetime
import pytz
import suncalc
from typing import Dict, Any, Optional

# Import the config singleton
from src.config import config

class CameraSettings:
    """
    Manages camera settings and profiles based on sun position
    
    This class handles:
    - Loading and applying camera profiles
    - Calculating sun position to determine appropriate profile
    - Updating geographic coordinates
    """
    def __init__(self, logger=None):
        self.current_profile = "default"
        self.logger = logger or logging.getLogger("CAMERA")
        
        try:
            self.logger.info("Loading camera profiles from config...")
            self.profiles = config.get_config('camera_profiles')
            self.logger.info(f"Loaded profiles: {list(self.profiles.keys())}")
            
            self.logger.info("Loading coordinates from config...")
            self.coordinates = config.get_config('coordinates')
            self.logger.info(f"Loaded coordinates: {self.coordinates}")
        except Exception as e:
            self.logger.error(f"Error during initialization: {e}")
            # Set default values but log the error
            self.profiles = {
                "default": {"shutter_speed": 0, "gain": 0, "brightness": 0, "contrast": 1.0}
            }
            self.coordinates = {"latitude": 32.7, "longitude": -97.3}
            self.logger.error(f"Falling back to default values: {self.coordinates}")

    def get_sun_phase(self) -> str:
        """
        Calculate the current sun phase based on sun position
        
        Returns:
            str: The current sun phase (day, civil_twilight, nautical_twilight, 
                 astronomical_twilight, or night)
        """
        try:
            # Get current coordinates from config - reload to ensure fresh values
            latest_coords = config.get_config('coordinates')
            self.logger.info(f"Reloaded coordinates for phase calculation: {latest_coords}")
            
            latitude = latest_coords['latitude']
            longitude = latest_coords['longitude']
            
            # Create timezone-aware datetime
            local_tz = pytz.timezone('America/Chicago')
            now = datetime.now(local_tz)
            self.logger.info(f"Calculating sun position for time: {now}")
            
            position = suncalc.get_position(now, longitude, latitude)
            altitude = math.degrees(position['altitude'])
            
            self.logger.info(f"Raw sun position data: {position}")
            self.logger.info(f"Calculated altitude: {altitude}°")
            
            # Detailed phase determination with logging
            phase = None
            if altitude <= -18:
                phase = "night"
                self.logger.info(f"altitude {altitude}° <= -18° -> night")
            elif altitude <= -12:
                phase = "astronomical_twilight"
                self.logger.info(f"-18° < altitude {altitude}° <= -12° -> astronomical_twilight")
            elif altitude <= -6:
                phase = "nautical_twilight"
                self.logger.info(f"-12° < altitude {altitude}° <= -6° -> nautical_twilight")
            elif altitude <= -0.833:
                phase = "civil_twilight"
                self.logger.info(f"-6° < altitude {altitude}° <= -0.833° -> civil_twilight")
            else:
                phase = "day"
                self.logger.info(f"altitude {altitude}° > -0.833° -> day")
                
            self.logger.info(f"Final determined phase: {phase}")
            return phase
                
        except Exception as e:
            self.logger.error(f"Error calculating sun phase: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return "day"  # Default to day mode if calculation fails
        
    def update_profile_from_sun_phase(self) -> None:
        """Update the current profile based on sun phase"""
        old_profile = self.current_profile
        phase = self.get_sun_phase()
        if phase in self.profiles:
            self.current_profile = phase
            if old_profile != self.current_profile:
                self.logger.info(f"Profile changed: {old_profile} -> {self.current_profile}")
                self.logger.info(f"New settings: {self.profiles[self.current_profile]}")
        else:
            self.logger.warning(f"No profile found for phase {phase}, keeping current profile: {self.current_profile}")

    def get_current_settings(self) -> Dict[str, Any]:
        """Get current camera settings"""
        # Reload profiles from config to ensure we have the latest
        self.profiles = config.get_config('camera_profiles')
        return self.profiles[self.current_profile].copy()

    def update_profile(self, profile_name: str, settings: Dict[str, Any]) -> None:
        """
        Update or create a camera profile
        
        Args:
            profile_name: Name of the profile to update
            settings: New settings to apply to the profile
        """
        if profile_name in self.profiles:
            self.profiles[profile_name].update(settings)
        else:
            self.profiles[profile_name] = settings
        
        # Update config file
        config.update_config('camera_profiles', self.profiles)

    def switch_profile(self, profile_name: str) -> bool:
        """
        Switch to a different profile
        
        Args:
            profile_name: Name of the profile to switch to
            
        Returns:
            bool: True if switch was successful, False if profile not found
        """
        if profile_name in self.profiles:
            self.current_profile = profile_name
            return True
        return False
    
    def update_coordinates(self, latitude: float, longitude: float) -> bool:
        """
        Update the geographic coordinates
        
        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            self.coordinates = {'latitude': latitude, 'longitude': longitude}
            return config.update_config('coordinates', self.coordinates)
        except Exception as e:
            self.logger.error(f"Error updating coordinates: {e}")
            return False
