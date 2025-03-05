import os
import glob
import shutil
import logging
from typing import List

class DiskSpaceManager:
    """
    Manages disk space by enforcing storage limits for captured images.
    Automatically removes oldest images when storage limits are exceeded.
    """
    def __init__(self, image_dir: str, max_disk_usage_gb: float, logger=None):
        """
        Initialize the Disk Space Manager
        
        Args:
            image_dir: Path to the directory containing images
            max_disk_usage_gb: Maximum allowed disk usage in GB
            logger: Optional logger instance
        """
        self.image_dir = image_dir
        self.max_disk_usage_gb = max_disk_usage_gb
        self.logger = logger or logging.getLogger("SYSTEM")
        
    def cleanup_if_needed(self) -> bool:
        """
        Check current disk usage and delete oldest images if limit is exceeded
        
        Returns:
            bool: True if cleanup was performed, False otherwise
        """
        # Convert GB to bytes for comparison
        max_bytes = self.max_disk_usage_gb * 1024 * 1024 * 1024
        
        # Get current size
        dir_size = self._get_directory_size()
        
        # Check if cleanup needed
        if dir_size <= max_bytes:
            self.logger.debug(f"Disk usage ({dir_size / (1024**3):.2f} GB) is within limits ({self.max_disk_usage_gb} GB)")
            return False
        
        # Perform cleanup
        self.logger.info(f"Disk usage ({dir_size / (1024**3):.2f} GB) exceeds limit ({self.max_disk_usage_gb} GB), cleaning up...")
        
        # Calculate how much space to free up (remove enough to get to 90% of limit)
        target_size = max_bytes * 0.9
        bytes_to_remove = dir_size - target_size
        
        # Remove oldest files
        bytes_removed = self._remove_oldest_images(bytes_to_remove)
        
        self.logger.info(f"Cleanup complete: removed {bytes_removed / (1024**3):.2f} GB")
        return True
        
    def _get_directory_size(self) -> int:
        """
        Calculate total size of images directory in bytes
        
        Returns:
            int: Directory size in bytes
        """
        total_size = 0
        for dirpath, _, filenames in os.walk(self.image_dir):
            for f in filenames:
                try:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
                except (FileNotFoundError, PermissionError) as e:
                    self.logger.warning(f"Error getting size of {f}: {str(e)}")
        
        return total_size
        
    def _get_images_sorted_by_age(self) -> List[str]:
        """
        Get a list of image files sorted by creation time (oldest first)
        
        Returns:
            List[str]: Sorted list of image file paths
        """
        # Get all image files
        image_pattern = os.path.join(self.image_dir, "image_*.jpg")
        image_files = glob.glob(image_pattern)
        
        # Sort by creation time (oldest first)
        image_files.sort(key=lambda x: os.path.getctime(x))
        
        return image_files
    
    def _remove_oldest_images(self, bytes_to_remove: float) -> int:
        """
        Remove oldest images until the specified amount of space is freed
        
        Args:
            bytes_to_remove: Amount of space to free up in bytes
            
        Returns:
            int: Actual number of bytes removed
        """
        if bytes_to_remove <= 0:
            return 0
            
        bytes_removed = 0
        images = self._get_images_sorted_by_age()
        
        for image_path in images:
            if bytes_removed >= bytes_to_remove:
                break
                
            try:
                file_size = os.path.getsize(image_path)
                os.remove(image_path)
                bytes_removed += file_size
                
                self.logger.info(f"Removed {os.path.basename(image_path)} ({file_size / (1024**2):.2f} MB)")
                
            except (FileNotFoundError, PermissionError) as e:
                self.logger.error(f"Failed to remove {image_path}: {str(e)}")
        
        return bytes_removed
