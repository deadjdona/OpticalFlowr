"""
Utility functions for the stabilization system
"""

import cv2
import numpy as np
import json
import time
import logging
from typing import Tuple, List, Optional
import subprocess
import os

logger = logging.getLogger(__name__)


def calculate_fov(focal_length: float, sensor_size: float) -> float:
    """
    Calculate field of view from focal length and sensor size
    
    Args:
        focal_length: Focal length in mm
        sensor_size: Sensor size in mm
        
    Returns:
        Field of view in degrees
    """
    return 2 * np.arctan(sensor_size / (2 * focal_length)) * 180 / np.pi


def pixels_to_degrees(pixels: float, image_width: int, fov_degrees: float) -> float:
    """
    Convert pixel displacement to angular displacement
    
    Args:
        pixels: Pixel displacement
        image_width: Image width in pixels
        fov_degrees: Field of view in degrees
        
    Returns:
        Angular displacement in degrees
    """
    return (pixels / image_width) * fov_degrees


def degrees_to_pixels(degrees: float, image_width: int, fov_degrees: float) -> float:
    """
    Convert angular displacement to pixel displacement
    
    Args:
        degrees: Angular displacement in degrees
        image_width: Image width in pixels
        fov_degrees: Field of view in degrees
        
    Returns:
        Pixel displacement
    """
    return (degrees / fov_degrees) * image_width


def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """
    Rotate image by given angle
    
    Args:
        image: Input image
        angle: Rotation angle in degrees
        
    Returns:
        Rotated image
    """
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, matrix, (w, h))


def apply_image_stabilization(image: np.ndarray, 
                             displacement: Tuple[float, float]) -> np.ndarray:
    """
    Apply digital image stabilization
    
    Args:
        image: Input image
        displacement: (x, y) displacement to compensate
        
    Returns:
        Stabilized image
    """
    h, w = image.shape[:2]
    matrix = np.float32([[1, 0, -displacement[0]], [0, 1, -displacement[1]]])
    return cv2.warpAffine(image, matrix, (w, h))


def calculate_motion_blur_kernel(velocity: Tuple[float, float], 
                                exposure_time: float) -> np.ndarray:
    """
    Calculate motion blur kernel from velocity
    
    Args:
        velocity: (vx, vy) velocity in pixels/second
        exposure_time: Exposure time in seconds
        
    Returns:
        Motion blur kernel
    """
    # Calculate motion vector
    motion_x = velocity[0] * exposure_time
    motion_y = velocity[1] * exposure_time
    motion_length = np.sqrt(motion_x**2 + motion_y**2)
    
    if motion_length < 1:
        return np.array([[1]], dtype=np.float32)
        
    # Create kernel
    kernel_size = int(motion_length) + 1
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    
    # Draw line representing motion
    angle = np.arctan2(motion_y, motion_x)
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    
    for i in range(kernel_size):
        x = int(kernel_size/2 + i * cos_a)
        y = int(kernel_size/2 + i * sin_a)
        if 0 <= x < kernel_size and 0 <= y < kernel_size:
            kernel[y, x] = 1.0
            
    # Normalize
    kernel /= kernel.sum()
    
    return kernel


def deblur_image(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """
    Simple deblurring using Wiener filter
    
    Args:
        image: Blurred image
        kernel: Blur kernel
        
    Returns:
        Deblurred image
    """
    # Convert to frequency domain
    image_fft = np.fft.fft2(image)
    kernel_fft = np.fft.fft2(kernel, s=image.shape)
    
    # Wiener filter
    snr = 0.01  # Signal-to-noise ratio
    kernel_conj = np.conj(kernel_fft)
    denominator = np.abs(kernel_fft)**2 + snr
    
    deblurred_fft = image_fft * kernel_conj / denominator
    deblurred = np.fft.ifft2(deblurred_fft)
    
    return np.real(deblurred).astype(np.uint8)


def estimate_motion_from_frames(frame1: np.ndarray, 
                               frame2: np.ndarray) -> Tuple[float, float]:
    """
    Estimate global motion between two frames
    
    Args:
        frame1: First frame
        frame2: Second frame
        
    Returns:
        (dx, dy) displacement
    """
    # Convert to grayscale if needed
    if len(frame1.shape) == 3:
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_RGB2GRAY)
    else:
        gray1 = frame1
        
    if len(frame2.shape) == 3:
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2GRAY)
    else:
        gray2 = frame2
        
    # Use phase correlation for motion estimation
    shift, _ = cv2.phaseCorrelate(gray1.astype(np.float32), 
                                  gray2.astype(np.float32))
    
    return shift


def check_raspberry_pi() -> dict:
    """
    Check if running on Raspberry Pi and get hardware info
    
    Returns:
        Dictionary with Pi information
    """
    pi_info = {
        'is_pi': False,
        'model': None,
        'revision': None,
        'memory': None
    }
    
    try:
        # Check /proc/cpuinfo for Pi hardware
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            
        if 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo:
            pi_info['is_pi'] = True
            
            # Extract model
            for line in cpuinfo.split('\n'):
                if 'Model' in line:
                    pi_info['model'] = line.split(':')[1].strip()
                elif 'Revision' in line:
                    pi_info['revision'] = line.split(':')[1].strip()
                    
        # Get memory info
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            for line in meminfo.split('\n'):
                if 'MemTotal' in line:
                    mem_kb = int(line.split()[1])
                    pi_info['memory'] = f"{mem_kb // 1024}MB"
                    break
                    
    except Exception as e:
        logger.debug(f"Could not detect Raspberry Pi: {e}")
        
    return pi_info


def optimize_for_pi_zero():
    """
    Apply system optimizations for Raspberry Pi Zero
    """
    if not check_raspberry_pi()['is_pi']:
        logger.info("Not running on Raspberry Pi, skipping optimizations")
        return
        
    try:
        # Set CPU governor to performance
        subprocess.run(['sudo', 'sh', '-c', 
                       'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'],
                      check=False)
        
        # Increase GPU memory split (requires reboot)
        # This is typically done in /boot/config.txt with gpu_mem=128
        
        # Set process priority
        os.nice(-10)  # Higher priority
        
        logger.info("Applied Pi Zero optimizations")
        
    except Exception as e:
        logger.error(f"Failed to apply optimizations: {e}")


def create_calibration_pattern(pattern_type: str = 'checkerboard',
                              size: Tuple[int, int] = (9, 6),
                              square_size: int = 30) -> np.ndarray:
    """
    Create calibration pattern image
    
    Args:
        pattern_type: 'checkerboard' or 'circles'
        size: Pattern size (columns, rows)
        square_size: Size of each square in pixels
        
    Returns:
        Calibration pattern image
    """
    if pattern_type == 'checkerboard':
        cols, rows = size
        pattern = np.zeros((rows * square_size, cols * square_size), dtype=np.uint8)
        
        for i in range(rows):
            for j in range(cols):
                if (i + j) % 2 == 0:
                    pattern[i*square_size:(i+1)*square_size,
                           j*square_size:(j+1)*square_size] = 255
                           
        return pattern
        
    elif pattern_type == 'circles':
        cols, rows = size
        pattern = np.ones((rows * square_size * 2, cols * square_size * 2, 3), 
                         dtype=np.uint8) * 255
        
        for i in range(rows):
            for j in range(cols):
                center = ((j * 2 + 1) * square_size, (i * 2 + 1) * square_size)
                cv2.circle(pattern, center, square_size // 3, (0, 0, 0), -1)
                
        return pattern
        
    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}")


def benchmark_tracker(tracker, test_frames: List[np.ndarray]) -> dict:
    """
    Benchmark tracker performance
    
    Args:
        tracker: Tracker instance
        test_frames: List of test frames
        
    Returns:
        Performance metrics
    """
    if len(test_frames) < 2:
        return {}
        
    # Initialize tracker
    tracker.initialize(test_frames[0])
    
    # Track through frames
    start_time = time.time()
    results = []
    
    for frame in test_frames[1:]:
        result = tracker.track(frame)
        if result:
            results.append(result)
            
    elapsed = time.time() - start_time
    
    # Calculate metrics
    metrics = {
        'total_time': elapsed,
        'frames_processed': len(test_frames) - 1,
        'avg_fps': (len(test_frames) - 1) / elapsed if elapsed > 0 else 0,
        'successful_tracks': len(results),
        'success_rate': len(results) / (len(test_frames) - 1) if len(test_frames) > 1 else 0
    }
    
    if results:
        confidences = [r.confidence for r in results]
        metrics['avg_confidence'] = np.mean(confidences)
        metrics['min_confidence'] = np.min(confidences)
        
    return metrics


def save_debug_frame(frame: np.ndarray, info: dict, filepath: str):
    """
    Save annotated debug frame
    
    Args:
        frame: Image frame
        info: Debug information to overlay
        filepath: Output filepath
    """
    output = frame.copy()
    
    # Add text overlay
    y_offset = 20
    for key, value in info.items():
        text = f"{key}: {value}"
        cv2.putText(output, text, (10, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += 20
        
    # Add timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(output, timestamp, (10, output.shape[0] - 10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
               
    cv2.imwrite(filepath, output)
    logger.debug(f"Debug frame saved to {filepath}")