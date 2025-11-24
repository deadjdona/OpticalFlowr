"""
Optical Flow Sensor Interface for Raspberry Pi Zero
Supports PMW3901 and Caddx Infra 256 optical flow sensors for position tracking
"""

import time
import spidev
from typing import Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Caddx Infra 256
try:
    from caddx_infra256 import CaddxInfra256
    CADDX_AVAILABLE = True
except ImportError:
    CADDX_AVAILABLE = False
    logger.warning("Caddx Infra 256 support not available")


class PMW3901:
    """
    Interface for PMW3901 optical flow sensor
    Uses SPI communication protocol
    """
    
    # Register addresses
    REG_PRODUCT_ID = 0x00
    REG_MOTION = 0x02
    REG_DELTA_X_L = 0x03
    REG_DELTA_X_H = 0x04
    REG_DELTA_Y_L = 0x05
    REG_DELTA_Y_H = 0x06
    REG_SQUAL = 0x07
    REG_POWER_UP_RESET = 0x3A
    REG_SHUTDOWN = 0x3B
    
    PRODUCT_ID = 0x49
    
    def __init__(self, spi_bus=0, spi_device=0, rotation=0):
        """
        Initialize the PMW3901 optical flow sensor
        
        Args:
            spi_bus: SPI bus number (default 0)
            spi_device: SPI device number (default 0)
            rotation: Sensor rotation in degrees (0, 90, 180, 270)
        """
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = 2000000
        self.spi.mode = 3
        self.rotation = rotation
        
        self._reset()
        self._init_sensor()
        
        # Verify product ID
        product_id = self._read_register(self.REG_PRODUCT_ID)
        if product_id != self.PRODUCT_ID:
            logger.warning(f"Unexpected product ID: {hex(product_id)}")
        else:
            logger.info("PMW3901 initialized successfully")
    
    def _read_register(self, register: int) -> int:
        """Read a single register value"""
        result = self.spi.xfer2([register & 0x7F, 0x00])
        time.sleep(0.00001)  # 10 microseconds delay
        return result[1]
    
    def _write_register(self, register: int, value: int):
        """Write a value to a register"""
        self.spi.xfer2([register | 0x80, value])
        time.sleep(0.00001)  # 10 microseconds delay
    
    def _reset(self):
        """Perform a soft reset of the sensor"""
        self._write_register(self.REG_POWER_UP_RESET, 0x5A)
        time.sleep(0.005)  # 5ms delay after reset
    
    def _init_sensor(self):
        """Initialize sensor with recommended settings"""
        # Initialization sequence based on datasheet
        init_sequence = [
            (0x7F, 0x00),
            (0x55, 0x01),
            (0x50, 0x07),
            (0x7F, 0x0E),
            (0x43, 0x10),
        ]
        
        for reg, val in init_sequence:
            self._write_register(reg, val)
            time.sleep(0.001)
        
        time.sleep(0.01)  # Wait for sensor to stabilize
    
    def get_motion(self) -> Tuple[int, int]:
        """
        Read motion data (delta X and Y) from the sensor
        
        Returns:
            Tuple of (delta_x, delta_y) in sensor units
        """
        # Check if motion data is available
        motion = self._read_register(self.REG_MOTION)
        
        if not (motion & 0x80):
            # No motion detected
            return (0, 0)
        
        # Read delta values (16-bit signed integers)
        delta_x_l = self._read_register(self.REG_DELTA_X_L)
        delta_x_h = self._read_register(self.REG_DELTA_X_H)
        delta_y_l = self._read_register(self.REG_DELTA_Y_L)
        delta_y_h = self._read_register(self.REG_DELTA_Y_H)
        
        # Combine bytes into signed 16-bit integers
        delta_x = self._to_signed_16bit((delta_x_h << 8) | delta_x_l)
        delta_y = self._to_signed_16bit((delta_y_h << 8) | delta_y_l)
        
        # Apply rotation correction
        delta_x, delta_y = self._apply_rotation(delta_x, delta_y)
        
        return (delta_x, delta_y)
    
    def _to_signed_16bit(self, value: int) -> int:
        """Convert unsigned 16-bit to signed"""
        if value > 32767:
            return value - 65536
        return value
    
    def _apply_rotation(self, x: int, y: int) -> Tuple[int, int]:
        """Apply rotation correction based on sensor orientation"""
        if self.rotation == 0:
            return (x, y)
        elif self.rotation == 90:
            return (y, -x)
        elif self.rotation == 180:
            return (-x, -y)
        elif self.rotation == 270:
            return (-y, x)
        return (x, y)
    
    def get_surface_quality(self) -> int:
        """
        Get surface quality measure (0-255)
        Higher values indicate better surface tracking
        """
        return self._read_register(self.REG_SQUAL)
    
    def shutdown(self):
        """Put sensor into low power mode"""
        self._write_register(self.REG_SHUTDOWN, 0xB6)
        self.spi.close()
        logger.info("PMW3901 shutdown")


class OpticalFlowTracker:
    """
    Higher-level optical flow tracking with position estimation
    """
    
    def __init__(self, sensor: PMW3901, scale_factor: float = 0.001, height_m: float = 0.5):
        """
        Initialize optical flow tracker
        
        Args:
            sensor: PMW3901 sensor instance
            scale_factor: Conversion factor from sensor units to meters
            height_m: Height above ground in meters (affects scale)
        """
        self.sensor = sensor
        self.scale_factor = scale_factor
        self.height_m = height_m
        
        # Position tracking
        self.pos_x = 0.0
        self.pos_y = 0.0
        
        # Velocity tracking
        self.vel_x = 0.0
        self.vel_y = 0.0
        
        self.last_update_time = time.time()
        
        # Moving average filter for noise reduction
        self.velocity_history_x = []
        self.velocity_history_y = []
        self.filter_window = 5
    
    def update(self) -> Tuple[float, float]:
        """
        Update position estimate based on optical flow
        Optimized for performance and robustness
        
        Returns:
            Current estimated position (x, y) in meters
        """
        current_time = time.time()
        dt = current_time - self.last_update_time
        
        if dt < 0.001:  # Avoid division by zero
            return (self.pos_x, self.pos_y)
        
        try:
            # Get raw motion from sensor
            delta_x, delta_y = self.sensor.get_motion()
        except Exception as e:
            logger.warning(f"Failed to read sensor: {e}")
            return (self.pos_x, self.pos_y)
        
        # Convert to velocity (m/s) accounting for height
        # Optical flow scales with height above ground
        scale = self.scale_factor * self.height_m
        instant_vel_x = (delta_x * scale) / dt
        instant_vel_y = (delta_y * scale) / dt
        
        # Reject outliers (likely sensor errors)
        max_velocity = 10.0  # m/s (36 km/h - reasonable max for drone)
        if abs(instant_vel_x) > max_velocity or abs(instant_vel_y) > max_velocity:
            logger.debug(f"Velocity outlier rejected: ({instant_vel_x:.2f}, {instant_vel_y:.2f})")
            return (self.pos_x, self.pos_y)
        
        self.vel_x = instant_vel_x
        self.vel_y = instant_vel_y
        
        # Apply moving average filter using deque for efficiency
        self.velocity_history_x.append(self.vel_x)
        self.velocity_history_y.append(self.vel_y)
        
        if len(self.velocity_history_x) > self.filter_window:
            self.velocity_history_x.pop(0)
            self.velocity_history_y.pop(0)
        
        # Use sum() once instead of recalculating
        len_hist = len(self.velocity_history_x)
        filtered_vel_x = sum(self.velocity_history_x) / len_hist
        filtered_vel_y = sum(self.velocity_history_y) / len_hist
        
        # Integrate velocity to get position
        self.pos_x += filtered_vel_x * dt
        self.pos_y += filtered_vel_y * dt
        
        self.last_update_time = current_time
        
        return (self.pos_x, self.pos_y)
    
    def get_velocity(self) -> Tuple[float, float]:
        """Get current velocity estimate in m/s"""
        filtered_vel_x = sum(self.velocity_history_x) / max(len(self.velocity_history_x), 1)
        filtered_vel_y = sum(self.velocity_history_y) / max(len(self.velocity_history_y), 1)
        return (filtered_vel_x, filtered_vel_y)
    
    def reset_position(self):
        """Reset position to origin"""
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.velocity_history_x.clear()
        self.velocity_history_y.clear()
        logger.info("Position reset to origin")
    
    def set_height(self, height_m: float):
        """Update height above ground for accurate scaling"""
        self.height_m = height_m
    
    def get_surface_quality(self) -> int:
        """Get surface quality from sensor"""
        return self.sensor.get_surface_quality()
