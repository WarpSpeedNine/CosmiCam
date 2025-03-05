from abc import ABC, abstractmethod
import logging

class ImageProcessor(ABC):
    """
    Abstract base class for image processing
    
    This defines the interface for all image processors, which take
    a raw image and process it in some way.
    """
    @abstractmethod
    def process(self, image_path: str) -> str:
        """
        Process an image and return the path to the processed image
        
        Args:
            image_path: Path to the input image
            
        Returns:
            str: Path to the processed image
        """
        pass

class BasicProcessor(ImageProcessor):
    """
    Basic image processor (placeholder for future OpenCV implementation)
    
    Currently just returns the original image path. In the future, this
    can be extended to implement dark frame subtraction, etc.
    """
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("CAMERA")
    
    def process(self, image_path: str) -> str:
        """
        Currently just passes through the original image
        
        Args:
            image_path: Path to the input image
            
        Returns:
            str: Path to the "processed" image (same as input)
        """
        self.logger.debug(f"Basic processing applied to {image_path}")
        return image_path

# Future processors can be added as needed:
# class DarkFrameProcessor(ImageProcessor):
#     """Implements dark frame subtraction for low light images"""
#     pass
