import os
import sys
import gpiod
import RPi.GPIO as GPIO
import time
import threading
import subprocess
import logging
from datetime import datetime

from src.config import config
from src.utils import setup_logger

# Configuration
CHIP_NAME = "gpiochip0"
PWM_LINE = 13  # GPIO13 for PWM control
TACH_PIN = 6   # GPIO6 for tach reading
PWM_FREQUENCY = 10000  # 10 kHz
TEMPERATURE_CHECK_INTERVAL = 60  # seconds
TACH_CHECK_INTERVAL = 60  # 15 minutes in seconds

# Set GPIO mode for tachometer reading
GPIO.setmode(GPIO.BCM)

class PWMController:
    """Software PWM implementation for Raspberry Pi using RPi.GPIO"""
    
    def __init__(self, pin, frequency=PWM_FREQUENCY, logger=None):
        """
        Initialize a software PWM controller using RPi.GPIO
        
        Args:
            pin: GPIO pin number to control
            frequency: PWM frequency in Hz
            logger: Logger instance
        """
        self.pin = pin
        self.frequency = frequency
        self.duty_cycle = 0
        self.running = False
        self.thread = None
        self.logger = logger or logging.getLogger("FAN")
        
        # Configure GPIO pin as output
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
        
        # Calculate period in seconds
        self.period = 1 / frequency

    def start(self):
        """Start the PWM controller"""
        self.running = True
        self.thread = threading.Thread(target=self._pwm_loop)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info(f"Started software PWM on pin {self.pin} at {self.frequency} Hz")

    def stop(self):
        """Stop the PWM controller"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        GPIO.output(self.pin, GPIO.LOW)  # Ensure pin is low on stop
        self.logger.info(f"Stopped software PWM on pin {self.pin}")

    def set_duty_cycle(self, duty_cycle):
        """Set the duty cycle (0-100)"""
        self.duty_cycle = max(0, min(100, duty_cycle))

    def _pwm_loop(self):
        """PWM control loop"""
        while self.running:
            try:
                if self.duty_cycle == 0:
                    # Set to low (inactive)
                    GPIO.output(self.pin, GPIO.LOW)
                    time.sleep(self.period)
                elif self.duty_cycle == 100:
                    # Set to high (active)
                    GPIO.output(self.pin, GPIO.HIGH)
                    time.sleep(self.period)
                else:
                    # PWM implementation
                    GPIO.output(self.pin, GPIO.HIGH)
                    time.sleep(self.period * self.duty_cycle / 100)
                    GPIO.output(self.pin, GPIO.LOW)
                    time.sleep(self.period * (100 - self.duty_cycle) / 100)
            except Exception as e:
                self.logger.error(f"PWM error: {e}")
                time.sleep(0.1)  # Prevent CPU thrashing on error

class FanController:
    """Controls the cooling fan based on CPU temperature"""
    
    def __init__(self, logger=None):
        """Initialize the fan controller"""
        self.logger = logger or logging.getLogger("FAN")
        self.pwm = None
        self.running = False
        self.fan_settings = config.get_config('system_settings')['fan_control']
        self.logger.info(f"Fan controller initialized with settings: {self.fan_settings}")
        
    def get_cpu_temperature(self):
        """Get CPU temperature using vcgencmd"""
        try:
            output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
            temp = float(output.split('=')[1].split("'")[0])
            return temp
        except Exception as e:
            self.logger.error(f"Failed to get CPU temperature: {e}")
            return None

    def get_duty_cycle(self, temp):
        """Calculate duty cycle based on temperature"""
        if temp is None:
            return 50  # Default to 50% if temperature reading fails
        elif temp < 30:
            return 0
        elif temp < 40:
            return 90
        elif temp < 50:
            return 30
        elif temp < 55:
            return 50
        elif temp < 60:
            return 70
        else:
            return 100

    def read_tach(self, duration=1):
        """
        Read tachometer pulses to calculate fan RPM
        Using RPi.GPIO for event detection
        """
        # Setup before pulse counting
        GPIO.cleanup(TACH_PIN)  # Clean up the pin first to avoid conflicts
        
        pulse_count = 0
        start_time = time.time()
        
        def count_pulse(channel):
            nonlocal pulse_count
            pulse_count += 1
        
        # Configure tach pin
        GPIO.setup(TACH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        try:
            GPIO.add_event_detect(TACH_PIN, GPIO.FALLING, callback=count_pulse)
            time.sleep(duration)
            GPIO.remove_event_detect(TACH_PIN)
        except RuntimeError as e:
            self.logger.error(f"Failed to setup edge detection: {e}")
            return 0  # Return 0 RPM on error
        
        elapsed_time = time.time() - start_time
        if elapsed_time > 0:
            rpm = (pulse_count * 60) / (2 * elapsed_time)  # Assuming 2 pulses per revolution
        else:
            rpm = 0
        
        return rpm

    def fan_control_loop(self):
        """Main loop for temperature-based fan control"""
        last_log_time = 0
        while self.running:
            try:
                # Get temperature and adjust fan speed
                temp = self.get_cpu_temperature()
                duty_cycle = self.get_duty_cycle(temp)
                if self.pwm:
                    self.pwm.set_duty_cycle(duty_cycle)
                
                # Log periodically
                current_time = time.time()
                if current_time - last_log_time >= self.fan_settings['log_interval']:
                    rpm = self.read_tach()
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.logger.info(f"[{timestamp}] Temperature: {temp}°C, Duty Cycle: {duty_cycle}%, Fan Speed: {rpm:.0f} RPM")
                    last_log_time = current_time
                
                # Wait for next cycle
                time.sleep(TEMPERATURE_CHECK_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error in fan control loop: {e}")
                time.sleep(10)  # Wait before retrying

    def tach_check_loop(self):
        """Separate loop for checking fan operation"""
        while self.running:
            try:
                rpm = self.read_tach()
                if rpm < 100 and rpm > 0:  # Threshold for fan failure detection
                    self.logger.error(f"Fan failure detected! RPM: {rpm:.0f}")
                    # Add alert or shutdown logic as needed
                time.sleep(TACH_CHECK_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error in tach check loop: {e}")
                time.sleep(60)  # Wait before retrying

    def start(self):
        """Start the fan controller"""
        self.logger.info("Starting fan control service")
        
        try:
            # Instead of using gpiod, we'll use RPi.GPIO directly since it's more straightforward
            # for PWM control on the Raspberry Pi
            self.pwm = PWMController(PWM_LINE, PWM_FREQUENCY, logger=self.logger)
            self.pwm.start()
            
            # Mark as running and start control threads
            self.running = True
            
            # Start control threads
            fan_control_thread = threading.Thread(target=self.fan_control_loop)
            fan_control_thread.daemon = True
            
            tach_check_thread = threading.Thread(target=self.tach_check_loop)
            tach_check_thread.daemon = True
            
            fan_control_thread.start()
            tach_check_thread.start()
            
            self.logger.info("Fan control service started successfully")
            
            # Return threads for the calling code to manage
            return fan_control_thread, tach_check_thread
            
        except Exception as e:
            self.logger.error(f"Error starting fan control service: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.stop()
            return None, None

    def stop(self):
        """Stop the fan controller"""
        self.logger.info("Stopping fan control service")
        self.running = False
        
        # Clean up resources
        if hasattr(self, 'pwm') and self.pwm:
            self.pwm.stop()
            self.pwm = None
            
        # Clean up GPIO
        GPIO.cleanup()
        self.logger.info("Fan control service stopped")


def run_fan_control():
    """Main function to run the fan control service"""
    # Configure logging
    logger = setup_logger('fan')
    logger.info("Initializing fan control service")
    
    # Create fan controller
    controller = FanController(logger=logger)
    
    try:
        # Start fan controller
        fan_thread, tach_thread = controller.start()
        
        # Keep main thread alive while threads are running
        if fan_thread and tach_thread:
            logger.info("Fan control threads started successfully")
            while fan_thread.is_alive() and tach_thread.is_alive():
                time.sleep(1)
                
            logger.error("One or more fan control threads has exited unexpectedly")
        else:
            logger.error("Failed to start fan control threads")
            
    except KeyboardInterrupt:
        logger.info("Fan control stopped by user")
    except Exception as e:
        logger.error(f"Error in fan control service: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        # Clean up
        controller.stop()
        logger.info("Fan control service stopped")


# This makes the module directly executable
if __name__ == "__main__":
    run_fan_control()
