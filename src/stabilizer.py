"""
Main stabilization system integrating camera, tracker, PID controller, and servos
"""

import time
import threading
import logging
import json
import numpy as np
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from queue import Queue
import signal
import sys

from .camera import Camera
from .tracker import OpticalTracker
from .controller import DualAxisPIDController, PIDGains
from .servo import ServoController, ServoConfig
from .thermal_camera import CaddxInfra256CA, ThermalConfig, ThermalColormap
from .thermal_tracker import ThermalTracker

logger = logging.getLogger(__name__)


@dataclass
class StabilizerConfig:
    """Configuration for stabilization system"""
    # Camera settings
    camera_resolution: tuple = (320, 240)
    camera_framerate: int = 20
    
    # Thermal camera settings (Caddx Infra 256CA)
    use_thermal_camera: bool = False
    thermal_port: str = '/dev/ttyUSB0'
    thermal_baudrate: int = 115200
    thermal_colormap: str = 'ironbow'
    thermal_temp_range: tuple = (20.0, 40.0)
    thermal_weight: float = 0.5  # Weight for thermal vs optical tracking
    
    # Tracker settings
    max_features: int = 50
    feature_quality: float = 0.3
    min_feature_distance: int = 10
    
    # PID settings
    pan_kp: float = 0.5
    pan_ki: float = 0.1
    pan_kd: float = 0.05
    tilt_kp: float = 0.5
    tilt_ki: float = 0.1
    tilt_kd: float = 0.05
    
    # Servo settings
    pan_pin: int = 17
    tilt_pin: int = 18
    servo_smoothing: float = 0.3
    use_pca9685: bool = False
    
    # System settings
    control_rate_hz: int = 50
    enable_recording: bool = False
    debug_mode: bool = False
    
    @classmethod
    def from_json(cls, filepath: str) -> 'StabilizerConfig':
        """Load configuration from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(**data)
        
    def to_json(self, filepath: str):
        """Save configuration to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.__dict__, f, indent=2)


class Stabilizer:
    """
    Main stabilization system controller
    Coordinates all components for optical position stabilization
    """
    
    def __init__(self, config: Optional[StabilizerConfig] = None):
        """
        Initialize stabilizer system
        
        Args:
            config: System configuration
        """
        self.config = config or StabilizerConfig()
        
        # Initialize components
        self.camera = None
        self.thermal_camera = None
        self.tracker = None
        self.controller = None
        self.servos = None
        
        # System state
        self.running = False
        self.stabilization_enabled = False
        self.control_thread = None
        self.monitor_thread = None
        
        # Performance monitoring
        self.stats = {
            'frame_count': 0,
            'tracking_fps': 0,
            'control_fps': 0,
            'tracking_confidence': 0,
            'mean_error': 0,
            'cpu_usage': 0,
            'start_time': None
        }
        
        # Data recording
        self.recording_queue = Queue() if self.config.enable_recording else None
        self.recording_thread = None
        
        # Callbacks
        self.frame_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def initialize(self) -> bool:
        """Initialize all hardware components"""
        logger.info("Initializing stabilization system...")
        
        try:
            # Initialize camera (thermal or standard)
            if self.config.use_thermal_camera:
                # Initialize Caddx Infra 256CA thermal camera
                thermal_config = ThermalConfig(
                    port=self.config.thermal_port,
                    baudrate=self.config.thermal_baudrate,
                    colormap=ThermalColormap(self.config.thermal_colormap),
                    temperature_range=self.config.thermal_temp_range
                )
                self.thermal_camera = CaddxInfra256CA(thermal_config)
                if not self.thermal_camera.initialize():
                    logger.error("Thermal camera initialization failed")
                    return False
                    
                # Use thermal tracker
                self.tracker = ThermalTracker(
                    max_features=30,  # Reduced for thermal
                    quality_level=0.2,
                    min_distance=15,
                    thermal_weight=self.config.thermal_weight
                )
                logger.info("Using thermal camera and tracker")
            else:
                # Standard visible light camera
                self.camera = Camera(
                    resolution=self.config.camera_resolution,
                    framerate=self.config.camera_framerate
                )
                if not self.camera.initialize():
                    logger.error("Camera initialization failed")
                    return False
                    
                # Standard optical tracker
                self.tracker = OpticalTracker(
                    max_features=self.config.max_features,
                    quality_level=self.config.feature_quality,
                    min_distance=self.config.min_feature_distance
                )
                logger.info("Using standard camera and tracker")
            
            # Initialize PID controller
            pan_gains = PIDGains(
                kp=self.config.pan_kp,
                ki=self.config.pan_ki,
                kd=self.config.pan_kd
            )
            tilt_gains = PIDGains(
                kp=self.config.tilt_kp,
                ki=self.config.tilt_ki,
                kd=self.config.tilt_kd
            )
            self.controller = DualAxisPIDController(
                x_gains=pan_gains,
                y_gains=tilt_gains,
                x_limits=(-45, 45),
                y_limits=(-45, 45)
            )
            
            # Initialize servos
            pan_config = ServoConfig(smoothing=self.config.servo_smoothing)
            tilt_config = ServoConfig(smoothing=self.config.servo_smoothing)
            self.servos = ServoController(
                pan_pin=self.config.pan_pin,
                tilt_pin=self.config.tilt_pin,
                pan_config=pan_config,
                tilt_config=tilt_config,
                use_pca9685=self.config.use_pca9685
            )
            
            # Center servos
            self.servos.center()
            
            logger.info("Stabilization system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False
            
    def start(self):
        """Start stabilization system"""
        if self.running:
            logger.warning("System already running")
            return
            
        logger.info("Starting stabilization system...")
        self.running = True
        self.stats['start_time'] = time.time()
        
        # Start camera capture
        if self.config.use_thermal_camera:
            self.thermal_camera.start_capture()
        else:
            self.camera.start_capture()
        
        # Start control loop
        self.control_thread = threading.Thread(target=self._control_loop)
        self.control_thread.daemon = True
        self.control_thread.start()
        
        # Start monitoring
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # Start recording if enabled
        if self.config.enable_recording:
            self.recording_thread = threading.Thread(target=self._recording_loop)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
        logger.info("Stabilization system started")
        
    def stop(self):
        """Stop stabilization system"""
        logger.info("Stopping stabilization system...")
        self.running = False
        self.stabilization_enabled = False
        
        # Wait for threads to finish
        if self.control_thread:
            self.control_thread.join(timeout=2.0)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
            
        # Stop camera
        if self.config.use_thermal_camera and self.thermal_camera:
            self.thermal_camera.stop_capture()
        elif self.camera:
            self.camera.stop_capture()
            
        # Center and disable servos
        if self.servos:
            self.servos.center()
            time.sleep(0.5)
            self.servos.disable()
            
        logger.info("Stabilization system stopped")
        
    def _control_loop(self):
        """Main control loop for stabilization"""
        control_period = 1.0 / self.config.control_rate_hz
        last_control_time = time.time()
        control_count = 0
        tracker_initialized = False
        
        while self.running:
            try:
                loop_start = time.time()
                
                # Get frame from camera
                if self.config.use_thermal_camera:
                    thermal_frame = self.thermal_camera.get_frame(timeout=0.1)
                    if thermal_frame is None:
                        continue
                    frame = thermal_frame['colorized']  # Use colorized for display
                else:
                    frame = self.camera.get_frame(timeout=0.1)
                    if frame is None:
                        continue
                    
                self.stats['frame_count'] += 1
                
                # Initialize tracker on first frame
                if not tracker_initialized:
                    if self.config.use_thermal_camera:
                        if self.tracker.initialize_thermal(thermal_frame):
                            tracker_initialized = True
                            logger.info("Thermal tracker initialized")
                    else:
                        if self.tracker.initialize(frame):
                            tracker_initialized = True
                            logger.info("Tracker initialized")
                    continue
                    
                # Track features
                if self.config.use_thermal_camera:
                    tracking_result = self.tracker.track_thermal(thermal_frame)
                else:
                    tracking_result = self.tracker.track(frame)
                if tracking_result is None:
                    # Try to reinitialize
                    tracker_initialized = False
                    continue
                    
                # Update tracking stats
                self.stats['tracking_confidence'] = tracking_result.confidence
                
                # Only run control if stabilization is enabled
                if self.stabilization_enabled:
                    # Get displacement from center
                    displacement = self.tracker.get_displacement()
                    
                    # Convert pixel displacement to angle
                    # Approximate: 1 pixel = 0.1 degrees (tune based on camera FOV)
                    pan_error = displacement[0] * 0.1
                    tilt_error = displacement[1] * 0.1
                    
                    # Compute control output
                    pan_output, tilt_output = self.controller.compute(
                        -pan_error, -tilt_error
                    )
                    
                    # Apply to servos
                    self.servos.set_angle(pan_output, tilt_output)
                    
                    # Update stats
                    self.stats['mean_error'] = np.sqrt(pan_error**2 + tilt_error**2)
                    
                # Update control rate
                control_count += 1
                if time.time() - last_control_time >= 1.0:
                    self.stats['control_fps'] = control_count
                    control_count = 0
                    last_control_time = time.time()
                    
                # Callback for frame processing (e.g., visualization)
                if self.frame_callback:
                    if self.config.use_thermal_camera:
                        annotated_frame = self.tracker.draw_thermal_overlay(frame, thermal_frame)
                    else:
                        annotated_frame = self.tracker.draw_features(frame)
                    self.frame_callback(annotated_frame, tracking_result)
                    
                # Record data if enabled
                if self.recording_queue and tracking_result:
                    self.recording_queue.put({
                        'timestamp': tracking_result.timestamp,
                        'position': tracking_result.position,
                        'velocity': tracking_result.velocity,
                        'confidence': tracking_result.confidence,
                        'servo_position': self.servos.get_position()
                    })
                    
                # Maintain control rate
                elapsed = time.time() - loop_start
                if elapsed < control_period:
                    time.sleep(control_period - elapsed)
                    
            except Exception as e:
                logger.error(f"Control loop error: {e}")
                time.sleep(0.1)
                
    def _monitor_loop(self):
        """Monitor system performance"""
        while self.running:
            try:
                # Update tracking FPS
                self.stats['tracking_fps'] = self.camera.get_fps() if self.camera else 0
                
                # Calculate CPU usage (simplified)
                # In production, use psutil for accurate measurement
                import os
                load_avg = os.getloadavg()[0]  # 1-minute load average
                self.stats['cpu_usage'] = min(100, load_avg * 100)
                
                # Call status callback
                if self.status_callback:
                    self.status_callback(self.stats.copy())
                    
                # Log stats periodically
                if self.config.debug_mode:
                    logger.debug(f"Stats: FPS={self.stats['tracking_fps']:.1f}, "
                               f"Confidence={self.stats['tracking_confidence']:.2f}, "
                               f"Error={self.stats['mean_error']:.1f}")
                               
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(1.0)
                
    def _recording_loop(self):
        """Record tracking data to file"""
        if not self.recording_queue:
            return
            
        filepath = f"tracking_data_{int(time.time())}.json"
        data_buffer = []
        
        while self.running:
            try:
                # Collect data from queue
                while not self.recording_queue.empty():
                    data_buffer.append(self.recording_queue.get_nowait())
                    
                # Periodically write to file
                if len(data_buffer) >= 100:
                    with open(filepath, 'a') as f:
                        for item in data_buffer:
                            json.dump(item, f)
                            f.write('\n')
                    data_buffer.clear()
                    
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Recording error: {e}")
                
        # Write remaining data
        if data_buffer:
            with open(filepath, 'a') as f:
                for item in data_buffer:
                    json.dump(item, f)
                    f.write('\n')
                    
    def enable_stabilization(self, enable: bool = True):
        """Enable/disable stabilization"""
        self.stabilization_enabled = enable
        if enable:
            self.controller.enable()
            logger.info("Stabilization enabled")
        else:
            self.controller.disable()
            self.servos.center()
            logger.info("Stabilization disabled")
            
    def reset_tracking(self):
        """Reset tracking to current position"""
        if self.tracker:
            self.tracker.reset_reference()
            self.controller.reset()
            logger.info("Tracking reset")
            
    def set_pid_gains(self, axis: str, kp: float, ki: float, kd: float):
        """Update PID gains for specific axis"""
        if axis == 'pan':
            self.controller.x_controller.set_gains(kp, ki, kd)
        elif axis == 'tilt':
            self.controller.y_controller.set_gains(kp, ki, kd)
        else:
            logger.error(f"Unknown axis: {axis}")
            
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            'running': self.running,
            'stabilization_enabled': self.stabilization_enabled,
            'stats': self.stats.copy(),
            'controller_state': self.controller.get_state() if self.controller else {},
            'servo_position': self.servos.get_position() if self.servos else (0, 0)
        }
        
    def capture_calibration_image(self, filepath: str):
        """Capture image for calibration"""
        if self.camera:
            return self.camera.capture_still(filepath)
        return False
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        self.cleanup()
        sys.exit(0)
        
    def cleanup(self):
        """Cleanup all resources"""
        if self.camera:
            self.camera.release()
        if self.thermal_camera:
            self.thermal_camera.release()
        if self.servos:
            self.servos.cleanup()
        logger.info("Cleanup complete")