import os
import sys
import gpiod
import RPi.GPIO as GPIO
import time
import threading
import subprocess
import logging

from src.config import config
from src.utils import setup_logger

class PWM:
    """
    PWM controller for fan speed control
    
    Implements software PWM using threading for GPIO control
    """
    def __init__(self, chip, line, frequency=10000):
        """
        Initialize the PWM controller
        
        Args:
            chip: GPIO chip object
            line: GPIO line object
            frequency: PWM frequency in Hz (default: 10kHz)
        """
        self.chip = chip
        self.line = line
        self.set_frequency(frequency)
        self.duty_cycle = 0
        self.running = False
        self.thread = None

    def start(self):
        """Start the PWM controller"""
        self.running = True
        self.thread = threading.Thread(target=self._pwm_loop)
        self.thread.start()

    def stop(self):
        """Stop the PWM controller"""
        self.running = False
        if self.thread:
            self.thread.join()

    def set_duty_cycle(self, duty_cycle):
        """
        Set the PWM duty cycle
        
        Args:
            duty_cycle: Duty cycle percentage (0-100)
        """
        self.duty_cycle = max(0, min(100, duty_cycle))

    def set_frequency(self, frequency):
        """
        Set the PWM frequency
        
        Args:
            frequency: Frequency in Hz
        """
        self.frequency = frequency
        self.period = 1 / frequency

    def _pwm_loop(self):
        """Internal PWM loop - runs in a separate thread"""
        while self.running:
            if self.duty_cycle == 0:
                self.line.set_value(0)
                time.sleep(self.period)
            elif self.duty_cycle == 100:
                self.line.set_value(1)
                time.sleep(self.period)
            else:
                self.line.set_value(1)
                time.sleep(self.period * self.duty_cycle / 100)
                self.line.set_value(0)
                time.sleep(self.period * (100 - self.duty_cycle) / 100)

class FanController:
    """
    Controller for fan speed based on CPU temperature
    
    Features:
    - PWM-based speed control
    - Temperature-based speed adjustment
    - Tachometer monitoring for RPM measurement
    """
    def __init__(self, logger=None):
        """
        Initialize the fan controller
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("FAN")
        
        # GPIO configuration
        self.chip_name = "gpiochip4"
        self.pwm_line = 13  # GPIO13 for PWM control
        self.tach_pin = 6   # GPIO6 for tach reading
        self.pwm_frequency = 10000  # 10 kHz
        
        # Temperature check intervals
        self.temp_check_interval = 60  # seconds
        self.tach_check_interval = 900  # 15 minutes
        
        # Fan settings from config
        system_settings = config.get_config('system_settings')
        self.fan_settings = system_settings.get('fan_control', {
            'log_interval': 300,
            'min_temp': 40,
            'max_temp': 80
        })
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Initialize PWM
        self.chip = None
        self.line = None
        self.pwm = None
        
        # Thread control
        self.running = False
        self.fan_thread = None
        self.tach_thread = None

    def get_cpu_temperature(self):
        """
        Get the current CPU temperature
        
        Returns:
            float: CPU temperature in degrees Celsius, or None if unavailable
        """
        try:
            output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
            temp = float(output.split('=')[1].split("'")[0])
            return temp
        except:
            self.logger.error("Failed to get CPU temperature")
            return None

    def get_duty_cycle(self, temp):
        """
        Calculate duty cycle based on temperature
        
        Args:
            temp: CPU temperature in degrees Celsius
            
        Returns:
            int: PWM duty cycle percentage (0-100)
        """
        if temp is None:
            return 50  # Default to 50% if temperature reading fails
        elif temp < 40:
            return 0
        elif temp < 45:
            return 10
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
        Read the fan tachometer to determine RPM
        
        Args:
            duration: Measurement duration in seconds
            
        Returns:
            float: Fan speed in RPM
        """
        pulse_count = 0
        start_time = time.time()
        
        def count_pulse(channel):
            nonlocal pulse_count
            pulse_count += 1
        
        GPIO.setup(self.tach_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(self.tach_pin, GPIO.FALLING, callback=count_pulse)
        
        time.sleep(duration)
        
        GPIO.remove_event_detect(self.tach_pin)
        
        elapsed_time = time.time() - start_time
        rpm = (pulse_count * 60) / (2 * elapsed_time)  # Assuming 2 pulses per revolution
        return rpm

    def _fan_control_loop(self):
        """Internal loop for temperature-based fan control"""
        last_log_time = 0
        
        while self.running:
            # Get temperature and set fan speed
            temp = self.get_cpu_temperature()
            duty_cycle = self.get_duty_cycle(temp)
            self.pwm.set_duty_cycle(duty_cycle)
            
            # Log periodically
            current_time = time.time()
            if current_time - last_log_time >= self.fan_settings['log_interval']:
                rpm = self.read_tach()
                self.logger.info(f"Temperature: {temp}°C, Duty Cycle: {duty_cycle}%, Fan Speed: {rpm:.0f} RPM")
                last_log_time = current_time
            
            # Wait for next check
            time.sleep(self.temp_check_interval)

    def _tach_check_loop(self):
        """Internal loop for monitoring fan operation"""
        while self.running:
            rpm = self.read_tach()
            if rpm < 100:  # Adjust this threshold as needed
                self.logger.error(f"Fan failure detected! RPM: {rpm:.0f}")
                # Add your shutdown or alert logic here
            time.sleep(self.tach_check_interval)

    def start(self):
        """Start the fan controller"""
        if self.running:
            return
            
        self.logger.info("Starting fan control service")
        
        # Initialize GPIO
        try:
            self.chip = gpiod.Chip(self.chip_name)
            self.line = self.chip.get_line(self.pwm_line)
            self.line.request(consumer="fan_control", type=gpiod.LINE_REQ_DIR_OUT)
            
            # Create and start PWM
            self.pwm = PWM(self.chip, self.line, self.pwm_frequency)
            self.pwm.start()
            
            # Start control threads
            self.running = True
            self.fan_thread = threading.Thread(target=self._fan_control_loop)
            self.tach_thread = threading.Thread(target=self._tach_check_loop)
            
            self.fan_thread.start()
            self.tach_thread.start()
            
            self.logger.info("Fan control service started")
            
        except Exception as e:
            self.logger.error(f"Failed to start fan control: {e}")
            self.stop()

    def stop(self):
        """Stop the fan controller"""
        self.running = False
        
        # Stop PWM
        if self.pwm:
            self.pwm.stop()
            self.pwm = None
        
        # Wait for threads to finish
        if self.fan_thread:
            self.fan_thread.join()
            self.fan_thread = None
            
        if self.tach_thread:
            self.tach_thread.join()
            self.tach_thread = None
        
        # Clean up GPIO
        if self.line:
            self.line.release()
            self.line = None
            
        if self.chip:
            self.chip.close()
            self.chip = None
        
        GPIO.cleanup()
        self.logger.info("Fan control service stopped")


def run_fan_control():
    """
    Run the fan control service
    
    This function is the entry point for the systemd service.
    """
    # Set up logging
    logger = setup_logger('fan')
    
    # Create and run fan controller
    controller = FanController(logger=logger)
    
    try:
        controller.start()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Fan control stopped by user")
    finally:
        controller.stop()


if __name__ == "__main__":
    run_fan_control()
