# CosmiCam
<!-- 
This README provides an overview of the CosmiCam project.
Key sections: Overview, Features, Installation, Architecture, Configuration, Usage
-->


A Raspberry Pi-based platform designed to continuously monitor and photograph the sky, with automatic adjustment for day and night conditions.

## Overview

CosmiCam is an automated sky observation system built for the Raspberry Pi that:

- Captures high-quality sky images at regular intervals
- Automatically adjusts camera settings based on sun position
- Provides a web interface to view the latest images
- Manages disk space by automatically removing oldest images
- Controls system temperature with responsive fan management

The system intelligently transitions between different capture profiles (day, civil twilight, nautical twilight, astronomical twilight, and night) by calculating the sun's position based on geographic coordinates.

<!-- ![CosmiCam Interface Mockup](https://via.placeholder.com/800x450?text=CosmiCam+Interface) -->

## Features

### Smart Capture Profiles

CosmiCam automatically selects the optimal camera settings for the current lighting conditions:

- **Day**: Standard settings for bright daylight
- **Civil Twilight**: Adjusted for the period after sunset but before dark
- **Nautical Twilight**: Enhanced sensitivity for dusk conditions
- **Astronomical Twilight**: High-sensitivity settings for faint light
- **Night**: Maximum sensitivity for night sky observation

### Web Interface

Access your sky observations from any device on your local network:

- Real-time display of the latest captured image
- Information on current sun phase and camera settings
- Responsive design that works on mobile and desktop

### System Architecture

- **Flask API**: RESTful backend that serves image data and system status
- **NGINX**: Efficient static file serving and API proxying
- **Systemd Services**: Robust service management for all components
- **Configuration Management**: YAML-based configuration with sensible defaults

### Hardware Management

- **Temperature Control**: PWM-based fan control to maintain optimal system temperature
- **Disk Space Management**: Automatic cleanup of old images to prevent storage issues
- **Camera Control**: Direct interface with Raspberry Pi camera using libcamera

## Technologies Used

- **Python 3**: Core application logic and camera control
- **Flask**: API backend
- **NGINX**: Web server and reverse proxy
- **HTML/CSS/JavaScript**: Frontend interface
- **systemd**: Service management
- **libcamera**: Camera interface
- **GPIO**: Hardware control for fan management

## Installation

### Prerequisites

- Raspberry Pi 5 with Raspberry Pi OS
- Raspberry Pi Camera Module
- Fan with PWM control capability (optional)
- Python 3.9+

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/WarpSpeedNine/CosmiCam.git
   cd CosmiCam
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create required directories:
   ```bash
   mkdir -p config images
   ```

5. Install systemd services:
   ```bash
   sudo cp systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

<!-- Adding NGINX installation instructions -->
6. Install NGINX (if not already installed):
   ```bash
   sudo apt update
   sudo apt install -y nginx
   sudo systemctl enable nginx
   sudo systemctl start nginx
   
   # Verify installation
   sudo systemctl status nginx
   ```

7. Configure NGINX:
   ```bash
   # Copy main NGINX configuration
   sudo cp nginx/nginx.conf /etc/nginx/nginx.conf
   
   # Copy site configuration
   sudo cp nginx/sites/cosmicam.conf /etc/nginx/sites-available/
   sudo ln -s /etc/nginx/sites-available/cosmicam.conf /etc/nginx/sites-enabled/
   
   # Remove default site (optional)
   sudo rm /etc/nginx/sites-enabled/default
   
   # Test configuration
   sudo nginx -t
   
   # Restart nginx
   sudo systemctl restart nginx
   ```

<!-- Updated service start command with explicit service initialization -->
8. Enable and start all services:
   ```bash
   # Enable services to start on boot
   sudo systemctl enable flask_api.service
   sudo systemctl enable image_capture.service
   sudo systemctl enable fan_control.service
   
   # Start services
   sudo systemctl start flask_api.service
   sudo systemctl start image_capture.service
   sudo systemctl start fan_control.service
   
   # Verify services are running properly
   sudo systemctl status flask_api.service
   sudo systemctl status image_capture.service
   sudo systemctl status fan_control.service
   ```

## Architecture

CosmiCam follows a modular architecture with several key components:

1. **Image Capture Service**: Controls the camera and captures images at configured intervals
2. **Flask API**: Provides RESTful endpoints for accessing images and system status
3. **Web Interface**: Frontend for viewing images and system information
4. **Configuration Manager**: Centralizes all system settings
5. **Hardware Controllers**: Manages physical components like the camera and cooling fan

The system is designed to be robust, with automatic error recovery and comprehensive logging.

<!-- Configuration section with detailed explanation of the YAML files -->
## Configuration

Configuration files are stored in YAML format in the `config` directory:
<!-- These configuration files control all aspects of CosmiCam's behavior -->

- `camera_profiles.yaml`: Settings for different lighting conditions
- `coordinates.yaml`: Geographic coordinates for sun position calculation
- `system_settings.yaml`: General system settings like capture interval

Example configuration for geographic coordinates:
```yaml
# Default geographic coordinates
latitude: 32.75
longitude: -97.33
```

## Code Structure

```
CosmiCam/
├── images/                  # Storage for captured images
├── nginx/                   # Web server configuration
├── src/
│   ├── api/                 # Flask API implementation
│   ├── camera/              # Camera control and image processing
│   ├── config/              # Configuration management
│   ├── hardware/            # Hardware control (fan, GPIO)
│   ├── utils/               # Utility functions
│   └── web/                 # Frontend assets
└── systemd/                 # Service definitions
```

## Usage

Once installed, CosmiCam runs automatically as a background service. To view the latest sky image, simply navigate to:

```
http://<raspberry-pi-ip>/
```

API endpoints are available at:
- `/api/latest-image`: Used to retrieve the path and metadata for the most recent image
- `/api/camera/profile`: Get current camera settings
- `/api/coordinates`: Get or update geographic coordinates
