(function() {
    // Configuration
    const updateInterval = 30000; // 30 seconds
    let lastImagePath = '';

    // DOM elements
    const elements = {
        skyImage: document.getElementById('skyImage'),
        timestamp: document.getElementById('timestamp'),
        sunPhase: document.getElementById('sunPhase'),
        cameraProfile: document.getElementById('cameraProfile'),
        shutterSpeed: document.getElementById('shutterSpeed'),
        gain: document.getElementById('gain')
    };

    // Helper function to format camera settings
    function formatShutterSpeed(speed) {
        if (speed === 0) return 'Auto';
        if (speed < 1000) return `${speed} µs`;
        if (speed < 1000000) return `${(speed / 1000).toFixed(1)} ms`;
        return `${(speed / 1000000).toFixed(1)} s`;
    }

    function formatGain(gain) {
        if (gain === 0) return 'Auto';
        return gain.toFixed(1);
    }

    // Main update function
    function updateImage() {
        console.log('Fetching latest image...');
        fetch('/api/latest-image')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Received data:', data);
                
                // Update image if changed
                if (data.path !== lastImagePath) {
                    // Construct full URL with cache buster
                    const fullImageUrl = data.path + '?t=' + new Date().getTime();
                    console.log('Loading image from:', fullImageUrl);
                    
                    elements.skyImage.src = fullImageUrl;
                    elements.timestamp.textContent = new Date(data.timestamp).toLocaleString();
                    lastImagePath = data.path;
                }
                
                // Update camera status info
                elements.sunPhase.textContent = data.sun_phase || 'Unknown';
                elements.cameraProfile.textContent = data.camera_profile || 'Unknown';
                
                if (data.camera_settings) {
                    elements.shutterSpeed.textContent = formatShutterSpeed(data.camera_settings.shutter_speed);
                    elements.gain.textContent = formatGain(data.camera_settings.gain);
                }
            })
            .catch(error => {
                console.error('Error fetching latest image:', error);
                // Optionally show error to user
                elements.timestamp.textContent = 'Error loading image';
            });
    }

    // Initial update
    updateImage();

    // Set up periodic updates
    setInterval(updateImage, updateInterval);
})();
