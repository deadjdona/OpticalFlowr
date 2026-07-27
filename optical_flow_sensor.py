"""
Optical Flow Sensor Interface for Raspberry Pi Zero
Supports PMW3901 and Caddx Infra 256 optical flow sensors for position tracking
"""

import time
import spidev
from typing import Tuple, Optional, Union
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Caddx Infra 256
try:
    from caddx_infra256 import CaddxInfra256
    CADDX_AVAILABLE = True
except ImportError:
    CADDX_AVAILABLE = False
    # Create a dummy class for type hinting if not available
    class CaddxInfra256:
        pass
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
    Supports high altitude operation (30+ meters) with adaptive filtering
    Uses visual coordinate system (camera frame of reference)
    """
    
    def __init__(self, sensor: Union[PMW3901, CaddxInfra256], scale_factor: float = 0.001, height_m: float = 0.5,
                 max_altitude: float = 50.0, altitude_source=None, use_visual_coords: bool = True):
        """
        Initialize optical flow tracker
        
        Args:
            sensor: PMW3901 or CaddxInfra256 sensor instance
            scale_factor: Conversion factor from sensor units to meters
            height_m: Height above ground in meters (affects scale)
            max_altitude: Maximum supported altitude in meters
            altitude_source: Optional altitude source for dynamic height updates
            use_visual_coords: Use visual coordinate system (camera frame) vs world frame
        """
        self.sensor = sensor
        self.scale_factor = scale_factor
        self.height_m = height_m
        self.max_altitude = max_altitude
        self.altitude_source = altitude_source
        self.use_visual_coords = use_visual_coords
        
        # Position tracking
        self.pos_x = 0.0
        self.pos_y = 0.0
        
        # Velocity tracking
        self.vel_x = 0.0
        self.vel_y = 0.0
        
        self.last_update_time = time.time()
        
        # Adaptive filtering for noise reduction
        # Filter window increases with altitude for better noise rejection
        self.velocity_history_x = []
        self.velocity_history_y = []
        self.base_filter_window = 5
        self.filter_window = self.base_filter_window
        
        # High altitude parameters
        self.altitude_scale_compensation = 1.0
        self.quality_threshold_low_altitude = 50
        self.quality_threshold_high_altitude = 30  # More lenient at high altitude
        
        # Tracking quality and confidence
        self.tracking_confidence = 1.0  # 0.0 to 1.0
        self.last_quality_check = time.time()
        
        # Barometer velocity (from flight controller)
        self.barometer_velocity_z = 0.0  # m/s vertical velocity
        self.use_barometer_velocity = False
        
        self.height_filter_alpha = 0.2
        logger.info(f"OpticalFlowTracker initialized (visual_coords: {use_visual_coords})")
    
    def update(self) -> Tuple[float, float]:
        """
        Update position estimate based on optical flow with altitude adaptation
        
        Returns:
            Current estimated position (x, y) in meters
        """
        current_time = time.time()
        dt = current_time - self.last_update_time
        
        if dt < 0.001:  # Avoid division by zero
            return (self.pos_x, self.pos_y)
        
        # Update altitude from external source if available
        if self.altitude_source:
            new_altitude = self.altitude_source.get_altitude()
            if new_altitude is not None and new_altitude > 0:
                self.height_m = new_altitude
        
        # Adapt filter parameters based on altitude
        self._adapt_to_altitude()
        
        # Allow sensors with onboard height estimates to adjust scale in real-time
        self._update_height_from_sensor()

        # Get raw motion from sensor
        delta_x, delta_y = self.sensor.get_motion()
        
        # Get surface quality for confidence estimation
        quality = self.get_surface_quality()
        
        # Update tracking confidence based on altitude and quality
        self._update_tracking_confidence(quality)
        
        # Convert to velocity (m/s) accounting for height
        # Optical flow scales linearly with height above ground
        # At higher altitudes, apply compensation for reduced sensor sensitivity
        scale = self.scale_factor * self.height_m * self.altitude_scale_compensation
        
        # Apply confidence scaling to velocities
        self.vel_x = (delta_x * scale) / dt * self.tracking_confidence
        self.vel_y = (delta_y * scale) / dt * self.tracking_confidence
        
        # Apply adaptive moving average filter
        self.velocity_history_x.append(self.vel_x)
        self.velocity_history_y.append(self.vel_y)
        
        if len(self.velocity_history_x) > self.filter_window:
            self.velocity_history_x.pop(0)
            self.velocity_history_y.pop(0)
        
        # Use weighted average for high altitude (more weight on recent samples)
        if self.height_m > 10.0:
            filtered_vel_x = self._weighted_average(self.velocity_history_x)
            filtered_vel_y = self._weighted_average(self.velocity_history_y)
        else:
            filtered_vel_x = sum(self.velocity_history_x) / len(self.velocity_history_x)
            filtered_vel_y = sum(self.velocity_history_y) / len(self.velocity_history_y)
        
        # Integrate velocity to get position
        self.pos_x += filtered_vel_x * dt
        self.pos_y += filtered_vel_y * dt
        
        self.last_update_time = current_time
        
        return (self.pos_x, self.pos_y)
    
    def _adapt_to_altitude(self):
        """
        Adapt filter parameters and scaling based on current altitude
        High altitude requires more filtering and scale compensation
        """
        if self.height_m <= 5.0:
            # Low altitude: minimal filtering, optimal sensor performance
            self.filter_window = self.base_filter_window
            self.altitude_scale_compensation = 1.0
        elif self.height_m <= 15.0:
            # Medium altitude: slight increase in filtering
            self.filter_window = self.base_filter_window + 2
            self.altitude_scale_compensation = 1.05
        elif self.height_m <= 30.0:
            # High altitude: significant filtering increase
            self.filter_window = self.base_filter_window + 5
            self.altitude_scale_compensation = 1.15
        else:
            # Very high altitude (30m+): maximum filtering
            self.filter_window = self.base_filter_window + 10
            # Compensate for reduced effective resolution at high altitude
            self.altitude_scale_compensation = 1.20 + (self.height_m - 30.0) * 0.01
            
            # Warn if approaching max altitude
            if self.height_m > self.max_altitude * 0.9:
                logger.warning(f"Altitude {self.height_m:.1f}m approaching maximum {self.max_altitude}m")
    
    def _update_tracking_confidence(self, quality: int):
        """
        Update tracking confidence based on sensor quality and altitude
        Confidence decreases at high altitude due to reduced sensor effectiveness
        """
        # Base confidence from sensor quality
        if self.height_m <= 5.0:
            quality_threshold = self.quality_threshold_low_altitude
        else:
            # Interpolate threshold based on altitude
            quality_threshold = self.quality_threshold_low_altitude - (
                (self.height_m / 30.0) * 
                (self.quality_threshold_low_altitude - self.quality_threshold_high_altitude)
            )
        
        # Calculate quality-based confidence
        if quality >= quality_threshold:
            quality_confidence = 1.0
        else:
            quality_confidence = max(0.3, quality / quality_threshold)
        
        # Altitude-based confidence degradation
        if self.height_m <= 5.0:
            altitude_confidence = 1.0
        elif self.height_m <= 15.0:
            altitude_confidence = 0.95
        elif self.height_m <= 30.0:
            altitude_confidence = 0.85
        else:
            # Confidence degrades above 30m
            altitude_confidence = max(0.5, 0.85 - (self.height_m - 30.0) * 0.01)
        
        # Combined confidence
        self.tracking_confidence = quality_confidence * altitude_confidence
        
        # Log warnings for low confidence
        if (current_time := time.time()) > self.last_quality_check + 5.0:
            if self.tracking_confidence < 0.6:
                logger.warning(
                    f"Low tracking confidence: {self.tracking_confidence:.2f} "
                    f"(altitude: {self.height_m:.1f}m, quality: {quality})"
                )
            self.last_quality_check = current_time
    
    def _weighted_average(self, values: list) -> float:
        """
        Calculate weighted average with more weight on recent values
        Useful for high altitude where sensor data is noisier
        """
        if not values:
            return 0.0
        
        weights = [i + 1 for i in range(len(values))]  # Linear increasing weights
        weighted_sum = sum(v * w for v, w in zip(values, weights))
        weight_sum = sum(weights)
        
        return weighted_sum / weight_sum
    
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
        """
        Update height above ground for accurate scaling
        
        Args:
            height_m: Current altitude in meters
        """
        if height_m > self.max_altitude:
            logger.warning(
                f"Altitude {height_m:.1f}m exceeds maximum {self.max_altitude}m. "
                f"Tracking accuracy may be degraded."
            )
        
        self.height_m = height_m
        logger.debug(f"Altitude updated to {height_m:.1f}m")

    def _update_height_from_sensor(self):
        """Pull height estimate from sensor if supported (e.g. AI Box)."""
        height_reader = getattr(self.sensor, 'get_height_estimate', None)
        if not callable(height_reader):
            return

        try:
            new_height = height_reader()
        except Exception as exc:
            logger.debug(f"Height estimate read failed: {exc}")
            return

        if new_height is None:
            return

        try:
            new_height = float(new_height)
        except (ValueError, TypeError):
            return

        if new_height <= 0.05:
            return

        if self.height_m <= 0:
            self.height_m = new_height
            return

        alpha = self.height_filter_alpha
        self.height_m = (1 - alpha) * self.height_m + alpha * new_height

    def get_surface_quality(self) -> int:
        """Get surface quality from sensor"""
        return self.sensor.get_surface_quality()
    
    def get_tracking_confidence(self) -> float:
        """
        Get current tracking confidence (0.0 to 1.0)
        Indicates reliability of position estimate
        """
        return self.tracking_confidence
    
    def get_altitude(self) -> float:
        """Get current altitude in meters"""
        return self.height_m
    
    def is_altitude_valid(self) -> bool:
        """Check if current altitude is within valid tracking range"""
        return 0.1 <= self.height_m <= self.max_altitude
    
    def set_barometer_velocity(self, velocity_z: float):
        """
        Set vertical velocity from flight controller barometer
        
        Args:
            velocity_z: Vertical velocity in m/s (positive = ascending)
        """
        self.barometer_velocity_z = velocity_z
        self.use_barometer_velocity = True
    
    def get_barometer_velocity(self) -> float:
        """Get vertical velocity from barometer (m/s)"""
        return self.barometer_velocity_z
    
    def is_using_visual_coordinates(self) -> bool:
        """Check if using visual coordinate system"""
        return self.use_visual_coords
