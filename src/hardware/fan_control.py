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
CHIP_NAME = "gpiochip0"  # Change to your specific chip
PWM_LINE = 13  # GPIO13 for PWM control
TACH_PIN = 6   # GPIO6 for tach reading
PWM_FREQUENCY = 10000  # 10 kHz
TEMPERATURE_CHECK_INTERVAL = 60  # seconds
TACH_CHECK_INTERVAL = 900  # 15 minutes in seconds

# Set GPIO mode for tachometer reading - only set mode once
GPIO.setwarnings(False)  # Disable warnings that might occur when re-initializing pins
GPIO.setmode(GPIO.BCM)   # Use BCM pin numbering

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
    
    def __init__(self, logger=None, debug_mode=False):
        """Initialize the fan controller"""
        self.logger = logger or logging.getLogger("FAN")
        self.pwm = None
        self.running = False
        self.debug_mode = debug_mode
        self.fan_settings = config.get_config('system_settings')['fan_control']
        self.logger.info(f"Fan controller initialized with settings: {self.fan_settings}")
        
        # Set up debug logging if requested
        if self.debug_mode:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug("Debug mode enabled")
        
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
        elif temp < 40:
            return 10
        elif temp < 45:
            return 20
        elif temp < 50:
            return 30
        elif temp < 55:
            return 50
        elif temp < 60:
            return 70
        else:
            return 100

    def read_tach(self, duration=2):
        """
        Read tachometer pulses to calculate fan RPM using a direct polling approach
        
        This method works by directly measuring the time between tach pulses
        rather than trying to count them over a fixed time window.
        """
        try:
            # Clean up any existing event detection
            try:
                GPIO.remove_event_detect(TACH_PIN)
            except:
                pass
                
            # Configure tach pin - try both pull-up and pull-down
            # Some fans need pull-up and others need pull-down
            GPIO.setup(TACH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Wait for pin to stabilize
            time.sleep(0.01)
            
            # Debug: Check initial state
            initial_state = GPIO.input(TACH_PIN)
            self.logger.debug(f"Tach pin initial state: {initial_state}")
            
            # Start time measurement
            start_time = time.time()
            pulse_count = 0
            last_state = initial_state
            
            # Use direct polling
            max_duration = duration  # Maximum time to wait for pulses
            
            while time.time() - start_time < max_duration:
                current_state = GPIO.input(TACH_PIN)
                
                # Count rising edges (change from 0 to 1)
                if current_state == 1 and last_state == 0:
                    pulse_count += 1
                    # Log first few pulses for debugging
                    if pulse_count <= 5:
                        self.logger.debug(f"Tach pulse detected: {pulse_count}")
                
                last_state = current_state
                # Very short sleep to prevent CPU overuse but still catch fast pulses
                time.sleep(0.0001)
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            
            # Debug info
            self.logger.debug(f"Tach read: {pulse_count} pulses in {elapsed_time:.2f} seconds")
            
            # If no pulses, try again with pull-down resistor
            if pulse_count == 0 and GPIO.input(TACH_PIN) == initial_state:
                self.logger.debug("No pulses detected with pull-up, trying pull-down")
                GPIO.setup(TACH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                time.sleep(0.01)
                
                # Try again with pull-down
                start_time = time.time()
                last_state = GPIO.input(TACH_PIN)
                while time.time() - start_time < max_duration / 2:  # Half duration for retry
                    current_state = GPIO.input(TACH_PIN)
                    if current_state == 1 and last_state == 0:
                        pulse_count += 1
                    last_state = current_state
                    time.sleep(0.0001)
                
                # Recalculate elapsed time
                elapsed_time = time.time() - start_time + (max_duration / 2)
                self.logger.debug(f"Retry with pull-down: {pulse_count} pulses in {elapsed_time:.2f} seconds")
            
            # If still no pulses, try one more time with both edges
            if pulse_count == 0:
                self.logger.debug("No pulses detected, trying to detect any pin changes")
                GPIO.setup(TACH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                time.sleep(0.01)
                
                # Try again detecting any change
                start_time = time.time()
                last_state = GPIO.input(TACH_PIN)
                while time.time() - start_time < max_duration / 2:  # Half duration for retry
                    current_state = GPIO.input(TACH_PIN)
                    if current_state != last_state:  # Any change
                        pulse_count += 1
                        self.logger.debug(f"Pin change detected: {last_state} -> {current_state}")
                    last_state = current_state
                    time.sleep(0.0001)
                
                # Recalculate elapsed time
                elapsed_time = time.time() - start_time + max_duration
            
            # Calculate RPM
            if pulse_count == 0 or elapsed_time == 0:
                self.logger.debug("No tach pulses detected at all")
                return 0
            
            # Standard calculation for 2 pulses per revolution (most PC fans)
            pulses_per_revolution = 2
            rpm = (pulse_count * 60) / (pulses_per_revolution * elapsed_time)
            
            self.logger.debug(f"Calculated RPM: {rpm:.1f} from {pulse_count} pulses")
            return rpm
            
        except Exception as e:
            self.logger.error(f"Error reading tachometer: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return 0

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
        warning_reported = False
        while self.running:
            try:
                rpm = self.read_tach(duration=2)  # Longer measurement for more accuracy
                
                # Get current duty cycle for context
                temp = self.get_cpu_temperature()
                current_duty_cycle = self.get_duty_cycle(temp)
                
                # Check for potential fan failure
                if current_duty_cycle > 20 and rpm < 100:
                    # Only report fan failure if the duty cycle is high enough to expect movement
                    if not warning_reported:
                        self.logger.warning(f"Possible fan failure detected! Duty Cycle: {current_duty_cycle}%, but RPM: {rpm:.0f}")
                        warning_reported = True
                else:
                    # Reset warning flag if RPMs are detected again
                    if warning_reported and rpm >= 100:
                        self.logger.info(f"Fan operation restored. Current RPM: {rpm:.0f}")
                        warning_reported = False
                        
                time.sleep(TACH_CHECK_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error in tach check loop: {e}")
                time.sleep(60)  # Wait before retrying

    def start(self):
        """Start the fan controller"""
        self.logger.info("Starting fan control service")
        
        try:
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
            
        # Clean up GPIO pins individually
        try:
            # Clean up tach pin
            try:
                GPIO.remove_event_detect(TACH_PIN)
            except:
                pass
            GPIO.cleanup(TACH_PIN)
            
            # Clean up PWM pin
            GPIO.cleanup(PWM_LINE)
        except:
            pass
            
        self.logger.info("Fan control service stopped")


def run_fan_control(debug_mode=False):
    """
    Main function to run the fan control service
    
    Args:
        debug_mode: Enable debug logging for more verbose output
    """
    # Configure logging
    logger = setup_logger('fan')
    logger.info("Initializing fan control service")
    
    if debug_mode:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Create fan controller with debug mode if requested
    controller = FanController(logger=logger, debug_mode=debug_mode)
    
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


if __name__ == "__main__":
    # Check for debug flag in arguments
    debug_mode = "--debug" in sys.argv or "-d" in sys.argv
    
    # Run the fan controller
    run_fan_control(debug_mode=debug_mode)
