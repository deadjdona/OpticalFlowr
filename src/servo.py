"""
Servo controller for gimbal/stabilization control
Supports GPIO PWM and I2C PWM controllers (PCA9685)
"""

import time
import logging
import numpy as np
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import hardware libraries
try:
    import pigpio
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False
    logger.warning("pigpio not available, servo control will be simulated")

try:
    from adafruit_pca9685 import PCA9685
    import board
    import busio
    PCA9685_AVAILABLE = True
except ImportError:
    PCA9685_AVAILABLE = False
    logger.info("PCA9685 library not available")


@dataclass
class ServoConfig:
    """Servo configuration parameters"""
    min_pulse_ms: float = 0.5  # Minimum pulse width in ms
    max_pulse_ms: float = 2.5  # Maximum pulse width in ms
    min_angle: float = -90.0   # Minimum angle in degrees
    max_angle: float = 90.0    # Maximum angle in degrees
    center_angle: float = 0.0  # Center/neutral angle
    inverted: bool = False      # Invert servo direction
    smoothing: float = 0.3      # Position smoothing factor (0-1)


class ServoController:
    """
    Generic servo controller supporting multiple backends
    """
    
    def __init__(self, pan_pin: int = 17, tilt_pin: int = 18,
                 pan_config: Optional[ServoConfig] = None,
                 tilt_config: Optional[ServoConfig] = None,
                 use_pca9685: bool = False,
                 i2c_address: int = 0x40):
        """
        Initialize servo controller
        
        Args:
            pan_pin: GPIO pin or PCA9685 channel for pan servo
            tilt_pin: GPIO pin or PCA9685 channel for tilt servo
            pan_config: Configuration for pan servo
            tilt_config: Configuration for tilt servo
            use_pca9685: Use PCA9685 PWM controller instead of GPIO
            i2c_address: I2C address of PCA9685
        """
        self.pan_pin = pan_pin
        self.tilt_pin = tilt_pin
        self.pan_config = pan_config or ServoConfig()
        self.tilt_config = tilt_config or ServoConfig()
        self.use_pca9685 = use_pca9685
        
        # Current positions
        self.pan_angle = 0.0
        self.tilt_angle = 0.0
        self.pan_target = 0.0
        self.tilt_target = 0.0
        
        # Initialize hardware
        self.pi = None
        self.pca = None
        self._initialize_hardware()
        
        # Safety limits
        self.limits_enabled = True
        self.pan_speed_limit = 180.0  # degrees per second
        self.tilt_speed_limit = 180.0
        self.last_update_time = time.time()
        
    def _initialize_hardware(self):
        """Initialize hardware interfaces"""
        if self.use_pca9685 and PCA9685_AVAILABLE:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.pca = PCA9685(i2c)
                self.pca.frequency = 50  # 50Hz for servos
                logger.info("PCA9685 PWM controller initialized")
                return
            except Exception as e:
                logger.error(f"PCA9685 initialization failed: {e}")
                
        if PIGPIO_AVAILABLE:
            try:
                self.pi = pigpio.pi()
                if self.pi.connected:
                    # Set PWM frequency for servos (50Hz)
                    self.pi.set_PWM_frequency(self.pan_pin, 50)
                    self.pi.set_PWM_frequency(self.tilt_pin, 50)
                    logger.info("pigpio PWM initialized")
                    return
            except Exception as e:
                logger.error(f"pigpio initialization failed: {e}")
                
        logger.warning("No hardware PWM available, running in simulation mode")
        
    def set_angle(self, pan: Optional[float] = None, tilt: Optional[float] = None):
        """
        Set servo angles
        
        Args:
            pan: Pan angle in degrees (None to keep current)
            tilt: Tilt angle in degrees (None to keep current)
        """
        current_time = time.time()
        dt = current_time - self.last_update_time
        
        # Update targets
        if pan is not None:
            self.pan_target = self._constrain_angle(pan, self.pan_config)
        if tilt is not None:
            self.tilt_target = self._constrain_angle(tilt, self.tilt_config)
            
        # Apply smoothing and speed limiting
        if self.pan_config.smoothing > 0:
            self.pan_angle = self._smooth_position(
                self.pan_angle, self.pan_target, 
                self.pan_config.smoothing, self.pan_speed_limit, dt
            )
        else:
            self.pan_angle = self.pan_target
            
        if self.tilt_config.smoothing > 0:
            self.tilt_angle = self._smooth_position(
                self.tilt_angle, self.tilt_target,
                self.tilt_config.smoothing, self.tilt_speed_limit, dt
            )
        else:
            self.tilt_angle = self.tilt_target
            
        # Apply to hardware
        self._set_servo_pwm(self.pan_pin, self.pan_angle, self.pan_config)
        self._set_servo_pwm(self.tilt_pin, self.tilt_angle, self.tilt_config)
        
        self.last_update_time = current_time
        
    def _constrain_angle(self, angle: float, config: ServoConfig) -> float:
        """Constrain angle to servo limits"""
        if config.inverted:
            angle = -angle
        return np.clip(angle, config.min_angle, config.max_angle)
        
    def _smooth_position(self, current: float, target: float, 
                        smoothing: float, speed_limit: float, dt: float) -> float:
        """Apply smoothing and speed limiting to position changes"""
        # Calculate desired change
        delta = target - current
        
        # Apply speed limit
        if self.limits_enabled and dt > 0:
            max_delta = speed_limit * dt
            delta = np.clip(delta, -max_delta, max_delta)
            
        # Apply smoothing
        return current + delta * (1 - smoothing)
        
    def _set_servo_pwm(self, pin: int, angle: float, config: ServoConfig):
        """Set PWM signal for servo"""
        # Calculate pulse width for angle
        pulse_ms = self._angle_to_pulse(angle, config)
        
        if self.pca and PCA9685_AVAILABLE:
            # PCA9685 uses 12-bit resolution (0-4095)
            # At 50Hz, each cycle is 20ms
            pulse_ticks = int((pulse_ms / 20.0) * 4095)
            self.pca.channels[pin].duty_cycle = pulse_ticks
            
        elif self.pi and PIGPIO_AVAILABLE and self.pi.connected:
            # pigpio uses microseconds
            pulse_us = int(pulse_ms * 1000)
            self.pi.set_servo_pulsewidth(pin, pulse_us)
            
        else:
            # Simulation mode
            logger.debug(f"Servo {pin}: angle={angle:.1f}°, pulse={pulse_ms:.2f}ms")
            
    def _angle_to_pulse(self, angle: float, config: ServoConfig) -> float:
        """Convert angle to pulse width in milliseconds"""
        # Map angle to pulse width
        angle_range = config.max_angle - config.min_angle
        pulse_range = config.max_pulse_ms - config.min_pulse_ms
        
        normalized = (angle - config.min_angle) / angle_range
        pulse_ms = config.min_pulse_ms + normalized * pulse_range
        
        return pulse_ms
        
    def get_position(self) -> Tuple[float, float]:
        """Get current servo positions"""
        return (self.pan_angle, self.tilt_angle)
        
    def center(self):
        """Center both servos"""
        self.set_angle(self.pan_config.center_angle, self.tilt_config.center_angle)
        logger.info("Servos centered")
        
    def disable(self):
        """Disable servo PWM (servos will go limp)"""
        if self.pi and PIGPIO_AVAILABLE and self.pi.connected:
            self.pi.set_servo_pulsewidth(self.pan_pin, 0)
            self.pi.set_servo_pulsewidth(self.tilt_pin, 0)
        elif self.pca and PCA9685_AVAILABLE:
            self.pca.channels[self.pan_pin].duty_cycle = 0
            self.pca.channels[self.tilt_pin].duty_cycle = 0
        logger.info("Servos disabled")
        
    def enable_limits(self, enable: bool = True):
        """Enable/disable safety limits"""
        self.limits_enabled = enable
        logger.info(f"Servo limits {'enabled' if enable else 'disabled'}")
        
    def set_speed_limits(self, pan_speed: float, tilt_speed: float):
        """Set maximum servo speeds in degrees per second"""
        self.pan_speed_limit = pan_speed
        self.tilt_speed_limit = tilt_speed
        
    def calibrate_servo(self, servo: str = 'pan') -> Dict[str, float]:
        """
        Interactive servo calibration
        
        Args:
            servo: 'pan' or 'tilt'
            
        Returns:
            Dictionary with calibration values
        """
        pin = self.pan_pin if servo == 'pan' else self.tilt_pin
        config = self.pan_config if servo == 'pan' else self.tilt_config
        
        calibration = {}
        
        # Test center position
        self._set_servo_pwm(pin, 0, config)
        time.sleep(1)
        calibration['center_pulse'] = self._angle_to_pulse(0, config)
        
        # Test min position
        self._set_servo_pwm(pin, config.min_angle, config)
        time.sleep(1)
        calibration['min_pulse'] = self._angle_to_pulse(config.min_angle, config)
        
        # Test max position
        self._set_servo_pwm(pin, config.max_angle, config)
        time.sleep(1)
        calibration['max_pulse'] = self._angle_to_pulse(config.max_angle, config)
        
        # Return to center
        self._set_servo_pwm(pin, 0, config)
        
        logger.info(f"Calibration for {servo}: {calibration}")
        return calibration
        
    def sweep_test(self, servo: str = 'both', duration: float = 5.0):
        """
        Perform a sweep test of servos
        
        Args:
            servo: 'pan', 'tilt', or 'both'
            duration: Duration of sweep in seconds
        """
        logger.info(f"Starting sweep test for {servo}")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            t = (time.time() - start_time) / duration
            angle = 45 * np.sin(2 * np.pi * t)
            
            if servo == 'pan' or servo == 'both':
                self.set_angle(pan=angle)
            if servo == 'tilt' or servo == 'both':
                self.set_angle(tilt=angle)
                
            time.sleep(0.02)  # 50Hz update rate
            
        self.center()
        logger.info("Sweep test complete")
        
    def cleanup(self):
        """Cleanup hardware resources"""
        self.disable()
        
        if self.pi and PIGPIO_AVAILABLE and self.pi.connected:
            self.pi.stop()
            
        if self.pca and PCA9685_AVAILABLE:
            self.pca.deinit()
            
        logger.info("Servo controller cleanup complete")
        
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.cleanup()
        except:
            pass