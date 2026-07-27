"""
Thermal image processing and enhancement for Caddx Infra 256CA
Optimized algorithms for thermal tracking and stabilization
"""

import numpy as np
import cv2
import logging
from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass
from scipy import ndimage
from scipy.signal import medfilt2d

logger = logging.getLogger(__name__)


@dataclass
class ThermalTarget:
    """Thermal target detection result"""
    center: Tuple[int, int]  # Center position (x, y)
    temperature: float  # Temperature in Celsius
    size: int  # Size in pixels
    confidence: float  # Detection confidence
    bbox: Tuple[int, int, int, int]  # Bounding box (x, y, w, h)


class ThermalProcessor:
    """
    Advanced thermal image processing for tracking and stabilization
    Optimized for Caddx Infra 256CA characteristics
    """
    
    def __init__(self):
        """Initialize thermal processor"""
        self.background_model = None
        self.frame_history = []
        self.max_history = 10
        
        # Processing parameters
        self.noise_threshold = 0.5  # Celsius
        self.min_target_temp = 25.0  # Minimum target temperature
        self.max_target_temp = 45.0  # Maximum target temperature
        
    def enhance_contrast(self, thermal_frame: np.ndarray, 
                        method: str = 'clahe') -> np.ndarray:
        """
        Enhance thermal image contrast
        
        Args:
            thermal_frame: Input thermal image (normalized 0-255)
            method: Enhancement method ('clahe', 'histogram', 'adaptive')
            
        Returns:
            Enhanced thermal image
        """
        if method == 'clahe':
            # Contrast Limited Adaptive Histogram Equalization
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(thermal_frame)
            
        elif method == 'histogram':
            # Simple histogram equalization
            enhanced = cv2.equalizeHist(thermal_frame)
            
        elif method == 'adaptive':
            # Adaptive contrast enhancement
            mean = np.mean(thermal_frame)
            std = np.std(thermal_frame)
            
            # Normalize to mean=128, std=40
            enhanced = (thermal_frame - mean) * (40 / std) + 128
            enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)
            
        else:
            enhanced = thermal_frame
            
        return enhanced
        
    def denoise_thermal(self, thermal_frame: np.ndarray,
                       temperature_data: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Remove noise from thermal image
        
        Args:
            thermal_frame: Normalized thermal image
            temperature_data: Optional temperature array for advanced filtering
            
        Returns:
            Denoised thermal image
        """
        # Apply median filter to remove salt-and-pepper noise
        denoised = medfilt2d(thermal_frame, kernel_size=3)
        
        # Apply bilateral filter to preserve edges
        denoised = cv2.bilateralFilter(denoised, d=5, sigmaColor=10, sigmaSpace=10)
        
        # Temperature-based filtering if available
        if temperature_data is not None:
            # Remove pixels with unrealistic temperature changes
            if len(self.frame_history) > 0:
                prev_temp = self.frame_history[-1]
                temp_diff = np.abs(temperature_data - prev_temp)
                
                # Mask out pixels with large temperature changes (likely noise)
                noise_mask = temp_diff > self.noise_threshold
                denoised[noise_mask] = self.frame_history[-1][noise_mask]
                
            # Update history
            self.frame_history.append(temperature_data)
            if len(self.frame_history) > self.max_history:
                self.frame_history.pop(0)
                
        return denoised.astype(np.uint8)
        
    def detect_thermal_edges(self, thermal_frame: np.ndarray) -> np.ndarray:
        """
        Detect edges in thermal image
        
        Args:
            thermal_frame: Input thermal image
            
        Returns:
            Edge map
        """
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(thermal_frame, (3, 3), 1.0)
        
        # Sobel edge detection
        sobel_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        
        # Calculate gradient magnitude
        magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
        
        # Normalize to 0-255
        edges = np.clip(magnitude, 0, 255).astype(np.uint8)
        
        # Apply threshold to get binary edge map
        _, edges = cv2.threshold(edges, 30, 255, cv2.THRESH_BINARY)
        
        return edges
        
    def detect_thermal_targets(self, temperature_data: np.ndarray,
                              normalized_frame: np.ndarray) -> List[ThermalTarget]:
        """
        Detect thermal targets (hot objects) in the scene
        
        Args:
            temperature_data: Temperature array in Celsius
            normalized_frame: Normalized thermal image
            
        Returns:
            List of detected thermal targets
        """
        targets = []
        
        # Threshold based on temperature
        target_mask = (temperature_data >= self.min_target_temp) & \
                     (temperature_data <= self.max_target_temp)
        target_mask = target_mask.astype(np.uint8) * 255
        
        # Morphological operations to clean up mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_OPEN, kernel)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(target_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter small contours (noise)
            if area < 10:
                continue
                
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate center
            M = cv2.moments(contour)
            if M['m00'] > 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
            else:
                cx = x + w // 2
                cy = y + h // 2
                
            # Get temperature at center
            center_temp = temperature_data[cy, cx]
            
            # Calculate mean temperature in region
            roi_temp = temperature_data[y:y+h, x:x+w]
            mean_temp = np.mean(roi_temp)
            
            # Calculate confidence based on temperature consistency
            temp_std = np.std(roi_temp)
            confidence = max(0, 1.0 - (temp_std / 10.0))  # Lower std = higher confidence
            
            target = ThermalTarget(
                center=(cx, cy),
                temperature=float(mean_temp),
                size=int(np.sqrt(area)),
                confidence=confidence,
                bbox=(x, y, w, h)
            )
            targets.append(target)
            
        # Sort by temperature (hottest first)
        targets.sort(key=lambda t: t.temperature, reverse=True)
        
        return targets
        
    def track_thermal_target(self, temperature_data: np.ndarray,
                            prev_target: Optional[ThermalTarget] = None) -> Optional[ThermalTarget]:
        """
        Track a specific thermal target across frames
        
        Args:
            temperature_data: Current temperature array
            prev_target: Previous target to track
            
        Returns:
            Updated target position or None if lost
        """
        if prev_target is None:
            # Find hottest target
            targets = self.detect_thermal_targets(temperature_data, None)
            return targets[0] if targets else None
            
        # Search window around previous position
        search_size = 30
        px, py = prev_target.center
        
        # Define search region
        x1 = max(0, px - search_size)
        x2 = min(temperature_data.shape[1], px + search_size)
        y1 = max(0, py - search_size)
        y2 = min(temperature_data.shape[0], py + search_size)
        
        # Extract search region
        search_region = temperature_data[y1:y2, x1:x2]
        
        # Find peak temperature in search region
        peak_y, peak_x = np.unravel_index(np.argmax(search_region), search_region.shape)
        
        # Convert to global coordinates
        new_x = x1 + peak_x
        new_y = y1 + peak_y
        
        # Verify temperature is similar to previous
        new_temp = temperature_data[new_y, new_x]
        temp_diff = abs(new_temp - prev_target.temperature)
        
        if temp_diff > 5.0:  # Temperature changed too much, likely lost target
            return None
            
        # Create updated target
        updated_target = ThermalTarget(
            center=(new_x, new_y),
            temperature=float(new_temp),
            size=prev_target.size,
            confidence=max(0, prev_target.confidence - temp_diff * 0.1),
            bbox=(new_x - 10, new_y - 10, 20, 20)  # Approximate bbox
        )
        
        return updated_target
        
    def create_background_model(self, frames: List[np.ndarray]):
        """
        Create background model for foreground detection
        
        Args:
            frames: List of temperature arrays for background modeling
        """
        if len(frames) == 0:
            return
            
        # Calculate median background
        self.background_model = np.median(frames, axis=0)
        logger.info("Thermal background model created")
        
    def subtract_background(self, temperature_data: np.ndarray,
                           threshold: float = 2.0) -> np.ndarray:
        """
        Subtract background to highlight moving/changing objects
        
        Args:
            temperature_data: Current temperature array
            threshold: Temperature difference threshold
            
        Returns:
            Foreground mask
        """
        if self.background_model is None:
            return np.ones_like(temperature_data, dtype=np.uint8) * 255
            
        # Calculate difference from background
        diff = np.abs(temperature_data - self.background_model)
        
        # Create foreground mask
        foreground = (diff > threshold).astype(np.uint8) * 255
        
        # Clean up mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel)
        
        return foreground
        
    def stabilize_temperature_reading(self, temperature_history: List[float],
                                     window_size: int = 5) -> float:
        """
        Stabilize temperature readings using moving average
        
        Args:
            temperature_history: List of temperature readings
            window_size: Size of moving average window
            
        Returns:
            Stabilized temperature
        """
        if len(temperature_history) == 0:
            return 0.0
            
        # Use only recent readings
        recent = temperature_history[-window_size:]
        
        # Remove outliers
        mean = np.mean(recent)
        std = np.std(recent)
        filtered = [t for t in recent if abs(t - mean) < 2 * std]
        
        # Return mean of filtered values
        return np.mean(filtered) if filtered else mean
        
    def apply_thermal_agc(self, thermal_frame: np.ndarray,
                         temperature_data: np.ndarray) -> np.ndarray:
        """
        Apply Automatic Gain Control for optimal visualization
        
        Args:
            thermal_frame: Normalized thermal image
            temperature_data: Temperature array
            
        Returns:
            AGC-adjusted image
        """
        # Calculate histogram
        hist, bins = np.histogram(thermal_frame.flatten(), bins=256, range=(0, 255))
        
        # Find useful dynamic range (exclude outliers)
        cumsum = np.cumsum(hist)
        total = cumsum[-1]
        
        # Find 2% and 98% percentiles
        low_idx = np.searchsorted(cumsum, total * 0.02)
        high_idx = np.searchsorted(cumsum, total * 0.98)
        
        # Remap range
        low_val = bins[low_idx]
        high_val = bins[high_idx]
        
        if high_val > low_val:
            scaled = (thermal_frame - low_val) * 255.0 / (high_val - low_val)
            scaled = np.clip(scaled, 0, 255).astype(np.uint8)
        else:
            scaled = thermal_frame
            
        return scaled
        
    def calculate_thermal_gradient(self, temperature_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate thermal gradient for edge detection
        
        Args:
            temperature_data: Temperature array
            
        Returns:
            Gradient magnitude and direction
        """
        # Calculate gradients
        grad_x = ndimage.sobel(temperature_data, axis=1)
        grad_y = ndimage.sobel(temperature_data, axis=0)
        
        # Calculate magnitude and direction
        magnitude = np.sqrt(grad_x**2 + grad_y**2)
        direction = np.arctan2(grad_y, grad_x)
        
        return magnitude, direction
        
    def segment_thermal_regions(self, temperature_data: np.ndarray,
                               n_segments: int = 5) -> np.ndarray:
        """
        Segment thermal image into temperature regions
        
        Args:
            temperature_data: Temperature array
            n_segments: Number of temperature segments
            
        Returns:
            Segmented image with region labels
        """
        # Calculate temperature ranges
        min_temp = np.min(temperature_data)
        max_temp = np.max(temperature_data)
        temp_range = max_temp - min_temp
        
        if temp_range < 0.1:
            return np.zeros_like(temperature_data, dtype=np.uint8)
            
        # Create segments
        segment_size = temp_range / n_segments
        segmented = np.zeros_like(temperature_data, dtype=np.uint8)
        
        for i in range(n_segments):
            lower = min_temp + i * segment_size
            upper = min_temp + (i + 1) * segment_size
            
            mask = (temperature_data >= lower) & (temperature_data < upper)
            segmented[mask] = i + 1
            
        return segmented