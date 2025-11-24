"""
Camera module for Raspberry Pi Camera
Optimized for low-latency capture on Pi Zero
"""

import time
import threading
import numpy as np
from queue import Queue
import logging

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


class Camera:
    """Optimized camera capture for Pi Zero"""
    
    def __init__(self, resolution=(320, 240), framerate=20, use_video_port=True):
        """
        Initialize camera with optimized settings for Pi Zero
        
        Args:
            resolution: Tuple of (width, height)
            framerate: Target framerate (will be limited by Pi Zero capabilities)
            use_video_port: Use video port for faster capture
        """
        self.resolution = resolution
        self.framerate = framerate
        self.use_video_port = use_video_port
        self.camera = None
        self.frame_queue = Queue(maxsize=2)  # Small buffer to prevent memory issues
        self.capture_thread = None
        self.running = False
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0
        
    def initialize(self):
        """Initialize camera hardware"""
        if PICAMERA2_AVAILABLE:
            try:
                self.camera = Picamera2()
                config = self.camera.create_preview_configuration(
                    main={"size": self.resolution, "format": "RGB888"},
                    buffer_count=2  # Minimize buffer for lower latency
                )
                self.camera.configure(config)
                self.camera.start()
                logger.info(f"PiCamera2 initialized at {self.resolution}")
                return True
            except Exception as e:
                logger.error(f"PiCamera2 initialization failed: {e}")
                
        if CV2_AVAILABLE:
            try:
                # Fallback to USB camera or CSI camera via V4L2
                self.camera = cv2.VideoCapture(0)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self.camera.set(cv2.CAP_PROP_FPS, self.framerate)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer
                logger.info(f"OpenCV camera initialized at {self.resolution}")
                return True
            except Exception as e:
                logger.error(f"OpenCV camera initialization failed: {e}")
                
        return False
        
    def start_capture(self):
        """Start continuous capture in background thread"""
        if not self.running:
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            logger.info("Camera capture started")
            
    def stop_capture(self):
        """Stop capture thread"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        logger.info("Camera capture stopped")
        
    def _capture_loop(self):
        """Background capture loop"""
        while self.running:
            try:
                frame = self._capture_frame()
                if frame is not None:
                    # Drop old frames if queue is full (prefer latest frame)
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except:
                            pass
                    self.frame_queue.put(frame)
                    self._update_fps()
            except Exception as e:
                logger.error(f"Capture error: {e}")
                time.sleep(0.1)
                
    def _capture_frame(self):
        """Capture single frame from camera"""
        if PICAMERA2_AVAILABLE and isinstance(self.camera, Picamera2):
            try:
                frame = self.camera.capture_array()
                return frame
            except Exception as e:
                logger.error(f"PiCamera2 capture error: {e}")
                return None
                
        elif CV2_AVAILABLE and self.camera is not None:
            try:
                ret, frame = self.camera.read()
                if ret:
                    # Convert BGR to RGB
                    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            except Exception as e:
                logger.error(f"OpenCV capture error: {e}")
                
        return None
        
    def get_frame(self, timeout=0.1):
        """
        Get latest frame from capture queue
        
        Args:
            timeout: Maximum time to wait for frame
            
        Returns:
            Numpy array of frame or None if timeout
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except:
            return None
            
    def _update_fps(self):
        """Calculate actual FPS"""
        self.frame_count += 1
        current_time = time.time()
        elapsed = current_time - self.last_fps_time
        
        if elapsed >= 1.0:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.last_fps_time = current_time
            
    def get_fps(self):
        """Get current actual FPS"""
        return self.current_fps
        
    def set_exposure(self, exposure_time_ms=None, iso=None):
        """
        Set manual exposure settings for consistent tracking
        
        Args:
            exposure_time_ms: Exposure time in milliseconds
            iso: ISO value (100-800 typical)
        """
        if PICAMERA2_AVAILABLE and isinstance(self.camera, Picamera2):
            controls = {}
            if exposure_time_ms:
                controls['ExposureTime'] = int(exposure_time_ms * 1000)  # Convert to microseconds
            if iso:
                controls['AnalogueGain'] = iso / 100.0
            if controls:
                self.camera.set_controls(controls)
                logger.info(f"Camera exposure set: {controls}")
                
    def set_white_balance(self, mode='auto', gains=None):
        """
        Set white balance mode
        
        Args:
            mode: 'auto' or 'manual'
            gains: Tuple of (red_gain, blue_gain) for manual mode
        """
        if PICAMERA2_AVAILABLE and isinstance(self.camera, Picamera2):
            if mode == 'auto':
                self.camera.set_controls({'AwbEnable': True})
            else:
                self.camera.set_controls({
                    'AwbEnable': False,
                    'ColourGains': gains if gains else (1.4, 1.5)
                })
                
    def capture_still(self, filename):
        """Capture high-resolution still image"""
        frame = self._capture_frame()
        if frame is not None and CV2_AVAILABLE:
            cv2.imwrite(filename, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            logger.info(f"Still image saved to {filename}")
            return True
        return False
        
    def release(self):
        """Release camera resources"""
        self.stop_capture()
        
        if PICAMERA2_AVAILABLE and isinstance(self.camera, Picamera2):
            self.camera.stop()
            self.camera.close()
        elif CV2_AVAILABLE and self.camera is not None:
            self.camera.release()
            
        logger.info("Camera released")
        
    def __del__(self):
        """Cleanup on deletion"""
        self.release()