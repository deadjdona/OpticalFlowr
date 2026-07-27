"""
Thermal camera module for Caddx Infra 256CA
Supports 256x192 resolution LWIR thermal imaging
"""

import time
import threading
import numpy as np
import cv2
import serial
import struct
import logging
from queue import Queue
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ThermalColormap(Enum):
    """Available thermal colormaps"""
    WHITEHOT = 'whitehot'
    BLACKHOT = 'blackhot'
    RAINBOW = 'rainbow'
    IRONBOW = 'ironbow'
    LAVA = 'lava'
    ARCTIC = 'arctic'
    GRADED_FIRE = 'graded_fire'
    HOT_METAL = 'hot_metal'


@dataclass
class ThermalConfig:
    """Configuration for Caddx Infra 256CA"""
    resolution: Tuple[int, int] = (256, 192)
    framerate: int = 25
    port: str = '/dev/ttyUSB0'  # USB serial port or /dev/ttyAMA0 for UART
    baudrate: int = 115200
    emissivity: float = 0.95  # Object emissivity (0.95 for most objects)
    temperature_range: Tuple[float, float] = (20.0, 40.0)  # Min/max temp in Celsius
    colormap: ThermalColormap = ThermalColormap.IRONBOW
    denoise: bool = True
    edge_enhancement: bool = False
    auto_gain: bool = True
    frame_skip: int = 0  # Skip frames for lower CPU usage


class CaddxInfra256CA:
    """
    Driver for Caddx Infra 256CA thermal camera
    Handles serial communication and frame decoding
    """
    
    # Frame constants for Caddx Infra 256CA
    FRAME_HEADER = b'\xAA\x55'
    FRAME_SIZE = 256 * 192 * 2  # 16-bit per pixel
    TOTAL_PACKET_SIZE = FRAME_SIZE + 4  # Header + data + checksum
    
    def __init__(self, config: Optional[ThermalConfig] = None):
        """
        Initialize Caddx Infra 256CA thermal camera
        
        Args:
            config: Thermal camera configuration
        """
        self.config = config or ThermalConfig()
        self.serial_port = None
        self.capture_thread = None
        self.running = False
        
        # Frame buffers
        self.frame_queue = Queue(maxsize=3)
        self.last_frame = None
        self.frame_count = 0
        self.error_count = 0
        
        # Temperature calibration
        self.temp_offset = 0.0
        self.temp_scale = 1.0
        
        # Statistics
        self.fps = 0
        self.last_fps_time = time.time()
        self.fps_counter = 0
        
        # Colormap lookup tables
        self.colormaps = self._create_colormaps()
        
    def _create_colormaps(self) -> dict:
        """Create colormap lookup tables for thermal visualization"""
        colormaps = {}
        
        # White hot (grayscale)
        colormaps[ThermalColormap.WHITEHOT] = cv2.applyColorMap(
            np.arange(256, dtype=np.uint8), cv2.COLORMAP_BONE
        )
        
        # Black hot (inverted grayscale)
        colormaps[ThermalColormap.BLACKHOT] = cv2.applyColorMap(
            255 - np.arange(256, dtype=np.uint8), cv2.COLORMAP_BONE
        )
        
        # Rainbow
        colormaps[ThermalColormap.RAINBOW] = cv2.applyColorMap(
            np.arange(256, dtype=np.uint8), cv2.COLORMAP_RAINBOW
        )
        
        # Ironbow (custom thermal colormap)
        ironbow = np.zeros((256, 3), dtype=np.uint8)
        for i in range(256):
            if i < 64:
                # Black to blue
                ironbow[i] = [i * 4, 0, 0]
            elif i < 128:
                # Blue to red
                ironbow[i] = [255, 0, (i - 64) * 4]
            elif i < 192:
                # Red to yellow
                ironbow[i] = [255, (i - 128) * 4, 255]
            else:
                # Yellow to white
                ironbow[i] = [255, 255, 255]
        colormaps[ThermalColormap.IRONBOW] = ironbow
        
        # Lava
        colormaps[ThermalColormap.LAVA] = cv2.applyColorMap(
            np.arange(256, dtype=np.uint8), cv2.COLORMAP_HOT
        )
        
        # Arctic (cold colors)
        arctic = np.zeros((256, 3), dtype=np.uint8)
        for i in range(256):
            arctic[i] = [255 - i, 255 - i//2, 255]
        colormaps[ThermalColormap.ARCTIC] = arctic
        
        # Graded fire
        fire = np.zeros((256, 3), dtype=np.uint8)
        for i in range(256):
            if i < 96:
                fire[i] = [0, 0, i * 255 // 96]
            elif i < 192:
                fire[i] = [0, (i - 96) * 255 // 96, 255]
            else:
                fire[i] = [(i - 192) * 255 // 64, 255, 255]
        colormaps[ThermalColormap.GRADED_FIRE] = fire
        
        # Hot metal
        colormaps[ThermalColormap.HOT_METAL] = cv2.applyColorMap(
            np.arange(256, dtype=np.uint8), cv2.COLORMAP_JET
        )
        
        return colormaps
        
    def initialize(self) -> bool:
        """Initialize serial connection to thermal camera"""
        try:
            # Open serial port
            self.serial_port = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # Clear input buffer
            self.serial_port.flushInput()
            
            # Send initialization commands
            self._send_command(b'\x01')  # Start streaming
            time.sleep(0.1)
            
            # Test read
            if self._read_frame_raw() is not None:
                logger.info(f"Caddx Infra 256CA initialized on {self.config.port}")
                return True
            else:
                logger.error("Failed to read test frame from thermal camera")
                return False
                
        except serial.SerialException as e:
            logger.error(f"Failed to open serial port {self.config.port}: {e}")
            return False
        except Exception as e:
            logger.error(f"Thermal camera initialization error: {e}")
            return False
            
    def start_capture(self):
        """Start continuous capture thread"""
        if not self.running:
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            logger.info("Thermal capture started")
            
    def stop_capture(self):
        """Stop capture thread"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        logger.info("Thermal capture stopped")
        
    def _send_command(self, command: bytes):
        """Send command to thermal camera"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.write(command)
            
    def _read_frame_raw(self) -> Optional[np.ndarray]:
        """
        Read raw thermal frame from serial port
        
        Returns:
            Raw 16-bit thermal data or None if failed
        """
        if not self.serial_port or not self.serial_port.is_open:
            return None
            
        try:
            # Look for frame header
            header = self.serial_port.read(2)
            while header != self.FRAME_HEADER and len(header) == 2:
                # Shift by one byte and try again
                header = header[1:] + self.serial_port.read(1)
                
            if header != self.FRAME_HEADER:
                return None
                
            # Read frame data
            data = self.serial_port.read(self.FRAME_SIZE)
            if len(data) != self.FRAME_SIZE:
                logger.warning(f"Incomplete frame: {len(data)} bytes")
                return None
                
            # Read checksum
            checksum_bytes = self.serial_port.read(2)
            if len(checksum_bytes) != 2:
                return None
                
            # Verify checksum (simple sum of all bytes)
            checksum = struct.unpack('<H', checksum_bytes)[0]
            calculated_checksum = sum(data) & 0xFFFF
            
            if checksum != calculated_checksum:
                logger.warning(f"Checksum mismatch: {checksum} != {calculated_checksum}")
                self.error_count += 1
                return None
                
            # Convert to numpy array (16-bit thermal values)
            frame = np.frombuffer(data, dtype=np.uint16).reshape(
                self.config.resolution[1], self.config.resolution[0]
            )
            
            return frame
            
        except Exception as e:
            logger.error(f"Error reading thermal frame: {e}")
            self.error_count += 1
            return None
            
    def _capture_loop(self):
        """Background capture loop"""
        skip_counter = 0
        
        while self.running:
            try:
                # Read raw frame
                raw_frame = self._read_frame_raw()
                
                if raw_frame is not None:
                    # Skip frames if configured
                    if skip_counter < self.config.frame_skip:
                        skip_counter += 1
                        continue
                    skip_counter = 0
                    
                    # Process frame
                    processed_frame = self._process_thermal_frame(raw_frame)
                    
                    # Store frame
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except:
                            pass
                    self.frame_queue.put(processed_frame)
                    self.last_frame = processed_frame
                    
                    # Update statistics
                    self.frame_count += 1
                    self._update_fps()
                    
            except Exception as e:
                logger.error(f"Capture loop error: {e}")
                time.sleep(0.1)
                
    def _process_thermal_frame(self, raw_frame: np.ndarray) -> dict:
        """
        Process raw thermal data into usable format
        
        Args:
            raw_frame: Raw 16-bit thermal data
            
        Returns:
            Dictionary with processed thermal data
        """
        # Convert to temperature (approximate formula for Caddx Infra)
        # Raw values are typically in 0.01K units
        temperature_kelvin = raw_frame * 0.01
        temperature_celsius = temperature_kelvin - 273.15
        
        # Apply calibration
        temperature_celsius = temperature_celsius * self.temp_scale + self.temp_offset
        
        # Calculate statistics
        min_temp = np.min(temperature_celsius)
        max_temp = np.max(temperature_celsius)
        mean_temp = np.mean(temperature_celsius)
        
        # Normalize for visualization (0-255)
        if self.config.auto_gain:
            # Auto scale based on scene
            norm_min, norm_max = min_temp, max_temp
        else:
            # Use fixed temperature range
            norm_min, norm_max = self.config.temperature_range
            
        if norm_max > norm_min:
            normalized = (temperature_celsius - norm_min) / (norm_max - norm_min)
            normalized = np.clip(normalized * 255, 0, 255).astype(np.uint8)
        else:
            normalized = np.full_like(temperature_celsius, 128, dtype=np.uint8)
            
        # Apply denoising if enabled
        if self.config.denoise:
            normalized = cv2.fastNlMeansDenoising(normalized, None, 10, 7, 21)
            
        # Apply edge enhancement if enabled
        if self.config.edge_enhancement:
            edges = cv2.Canny(normalized, 50, 150)
            normalized = cv2.addWeighted(normalized, 0.8, edges, 0.2, 0)
            
        # Apply colormap
        colorized = self.apply_colormap(normalized)
        
        return {
            'raw': raw_frame,
            'temperature': temperature_celsius,
            'normalized': normalized,
            'colorized': colorized,
            'min_temp': min_temp,
            'max_temp': max_temp,
            'mean_temp': mean_temp,
            'timestamp': time.time()
        }
        
    def apply_colormap(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply thermal colormap to grayscale frame
        
        Args:
            frame: Normalized grayscale frame (0-255)
            
        Returns:
            Colorized RGB frame
        """
        colormap = self.colormaps.get(self.config.colormap)
        if colormap is None:
            colormap = self.colormaps[ThermalColormap.IRONBOW]
            
        # Apply colormap
        if len(colormap.shape) == 2:
            # Grayscale colormap
            colored = cv2.applyColorMap(frame, cv2.COLORMAP_JET)
        else:
            # Custom colormap LUT
            colored = colormap[frame]
            
        return colored
        
    def get_frame(self, timeout: float = 0.1) -> Optional[dict]:
        """
        Get latest thermal frame
        
        Args:
            timeout: Maximum time to wait for frame
            
        Returns:
            Dictionary with thermal data or None
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except:
            return self.last_frame
            
    def get_temperature_at(self, x: int, y: int) -> Optional[float]:
        """
        Get temperature at specific pixel
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Temperature in Celsius or None
        """
        if self.last_frame and 'temperature' in self.last_frame:
            temp_array = self.last_frame['temperature']
            if 0 <= y < temp_array.shape[0] and 0 <= x < temp_array.shape[1]:
                return float(temp_array[y, x])
        return None
        
    def find_hotspots(self, threshold_percentile: float = 95) -> List[Tuple[int, int, float]]:
        """
        Find hotspot locations in thermal image
        
        Args:
            threshold_percentile: Percentile threshold for hotspot detection
            
        Returns:
            List of (x, y, temperature) tuples
        """
        if not self.last_frame or 'temperature' not in self.last_frame:
            return []
            
        temp_array = self.last_frame['temperature']
        threshold = np.percentile(temp_array, threshold_percentile)
        
        # Find pixels above threshold
        hotspot_mask = temp_array > threshold
        
        # Find connected components
        num_labels, labels = cv2.connectedComponents(hotspot_mask.astype(np.uint8))
        
        hotspots = []
        for label in range(1, num_labels):
            mask = labels == label
            y_coords, x_coords = np.where(mask)
            
            # Get centroid and max temperature
            if len(x_coords) > 0:
                cx = int(np.mean(x_coords))
                cy = int(np.mean(y_coords))
                max_temp = np.max(temp_array[mask])
                hotspots.append((cx, cy, float(max_temp)))
                
        # Sort by temperature (hottest first)
        hotspots.sort(key=lambda x: x[2], reverse=True)
        
        return hotspots
        
    def calibrate_temperature(self, reference_temp: float, roi: Optional[Tuple[int, int, int, int]] = None):
        """
        Calibrate temperature readings using reference
        
        Args:
            reference_temp: Known temperature of reference object
            roi: Optional region of interest (x, y, width, height)
        """
        if not self.last_frame or 'temperature' not in self.last_frame:
            logger.warning("No frame available for calibration")
            return
            
        temp_array = self.last_frame['temperature']
        
        if roi:
            x, y, w, h = roi
            measured_temp = np.mean(temp_array[y:y+h, x:x+w])
        else:
            measured_temp = np.mean(temp_array)
            
        # Calculate offset
        self.temp_offset = reference_temp - measured_temp
        logger.info(f"Temperature calibration offset: {self.temp_offset:.2f}°C")
        
    def set_emissivity(self, emissivity: float):
        """
        Set object emissivity for temperature calculation
        
        Args:
            emissivity: Emissivity value (0.0 to 1.0)
        """
        self.config.emissivity = np.clip(emissivity, 0.1, 1.0)
        # Adjust temperature scale based on emissivity
        self.temp_scale = self.config.emissivity
        
    def set_colormap(self, colormap: ThermalColormap):
        """Change thermal colormap"""
        self.config.colormap = colormap
        
    def _update_fps(self):
        """Update FPS counter"""
        self.fps_counter += 1
        current_time = time.time()
        elapsed = current_time - self.last_fps_time
        
        if elapsed >= 1.0:
            self.fps = self.fps_counter / elapsed
            self.fps_counter = 0
            self.last_fps_time = current_time
            
    def get_fps(self) -> float:
        """Get current capture FPS"""
        return self.fps
        
    def get_statistics(self) -> dict:
        """Get camera statistics"""
        return {
            'fps': self.fps,
            'frame_count': self.frame_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / max(1, self.frame_count),
            'resolution': self.config.resolution,
            'colormap': self.config.colormap.value
        }
        
    def save_thermal_image(self, filename: str, include_data: bool = False):
        """
        Save thermal image to file
        
        Args:
            filename: Output filename
            include_data: Include temperature data in metadata
        """
        if not self.last_frame:
            return False
            
        try:
            # Save colorized image
            cv2.imwrite(filename, cv2.cvtColor(self.last_frame['colorized'], cv2.COLOR_RGB2BGR))
            
            # Save temperature data if requested
            if include_data:
                data_filename = filename.rsplit('.', 1)[0] + '_thermal.npy'
                np.save(data_filename, self.last_frame['temperature'])
                logger.info(f"Thermal data saved to {data_filename}")
                
            logger.info(f"Thermal image saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save thermal image: {e}")
            return False
            
    def release(self):
        """Release camera resources"""
        self.stop_capture()
        
        if self.serial_port and self.serial_port.is_open:
            # Send stop command
            self._send_command(b'\x00')
            self.serial_port.close()
            
        logger.info("Thermal camera released")
        
    def __del__(self):
        """Cleanup on deletion"""
        self.release()