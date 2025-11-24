"""
Thermal-aware tracker for Caddx Infra 256CA
Extends optical tracker with thermal-specific features
"""

import numpy as np
import cv2
import time
import logging
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from collections import deque

from .tracker import OpticalTracker, TrackingResult
from .thermal_processing import ThermalProcessor, ThermalTarget

logger = logging.getLogger(__name__)


@dataclass
class ThermalTrackingResult(TrackingResult):
    """Extended tracking result with thermal information"""
    temperature: float  # Temperature at tracked position
    thermal_confidence: float  # Thermal-specific confidence
    hotspot_count: int  # Number of detected hotspots
    temp_gradient: float  # Temperature gradient at position


class ThermalTracker(OpticalTracker):
    """
    Thermal-aware tracker optimized for Caddx Infra 256CA
    Combines optical flow with thermal target detection
    """
    
    def __init__(self, max_features=30, quality_level=0.2, min_distance=15,
                 thermal_weight=0.5):
        """
        Initialize thermal tracker
        
        Args:
            max_features: Maximum features to track (reduced for thermal)
            quality_level: Quality threshold for features
            min_distance: Minimum distance between features
            thermal_weight: Weight of thermal vs optical tracking (0-1)
        """
        # Initialize base optical tracker with thermal-optimized parameters
        super().__init__(max_features, quality_level, min_distance)
        
        # Thermal-specific parameters
        self.thermal_weight = thermal_weight
        self.optical_weight = 1.0 - thermal_weight
        
        # Thermal processor
        self.thermal_processor = ThermalProcessor()
        
        # Thermal tracking state
        self.thermal_target = None
        self.thermal_history = deque(maxlen=30)
        self.temperature_history = deque(maxlen=30)
        
        # Adaptive parameters
        self.adaptive_threshold = True
        self.min_thermal_gradient = 0.5  # Minimum gradient for feature
        
        # Thermal-specific optical flow parameters
        self.lk_params_thermal = dict(
            winSize=(21, 21),  # Larger window for thermal
            maxLevel=3,  # More pyramid levels
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 15, 0.01)
        )
        
    def initialize_thermal(self, thermal_frame: Dict, 
                          temperature_threshold: Optional[float] = None) -> bool:
        """
        Initialize tracking with thermal frame
        
        Args:
            thermal_frame: Thermal frame dictionary from CaddxInfra256CA
            temperature_threshold: Optional temperature threshold for target
            
        Returns:
            Success status
        """
        if 'normalized' not in thermal_frame or 'temperature' not in thermal_frame:
            logger.error("Invalid thermal frame format")
            return False
            
        normalized = thermal_frame['normalized']
        temperature = thermal_frame['temperature']
        
        # Enhance thermal image for better features
        enhanced = self.thermal_processor.enhance_contrast(normalized, 'clahe')
        
        # Detect thermal targets
        targets = self.thermal_processor.detect_thermal_targets(temperature, enhanced)
        
        if targets:
            # Track the hottest target by default
            self.thermal_target = targets[0]
            
            # Initialize optical tracking around thermal target
            roi = self._create_roi_around_target(self.thermal_target, enhanced.shape)
            success = super().initialize(enhanced, roi)
            
            if success:
                logger.info(f"Thermal tracker initialized on target at {self.thermal_target.center}, "
                          f"temp={self.thermal_target.temperature:.1f}°C")
                return True
        else:
            # Fall back to standard initialization
            logger.warning("No thermal targets found, using standard initialization")
            return super().initialize(enhanced)
            
        return False
        
    def track_thermal(self, thermal_frame: Dict) -> Optional[ThermalTrackingResult]:
        """
        Track using thermal frame
        
        Args:
            thermal_frame: Thermal frame dictionary
            
        Returns:
            Thermal tracking result
        """
        if 'normalized' not in thermal_frame or 'temperature' not in thermal_frame:
            return None
            
        normalized = thermal_frame['normalized']
        temperature = thermal_frame['temperature']
        
        # Enhance for better tracking
        enhanced = self.thermal_processor.enhance_contrast(normalized, 'clahe')
        denoised = self.thermal_processor.denoise_thermal(enhanced, temperature)
        
        # Optical flow tracking
        optical_result = self._track_optical_thermal(denoised)
        
        # Thermal target tracking
        thermal_result = self._track_thermal_target(temperature)
        
        # Fuse results
        fused_result = self._fuse_tracking_results(optical_result, thermal_result, temperature)
        
        # Update history
        if fused_result:
            self.thermal_history.append(fused_result)
            if fused_result.temperature > 0:
                self.temperature_history.append(fused_result.temperature)
                
        return fused_result
        
    def _track_optical_thermal(self, enhanced_frame: np.ndarray) -> Optional[TrackingResult]:
        """
        Perform optical flow tracking on thermal frame
        
        Args:
            enhanced_frame: Enhanced thermal frame
            
        Returns:
            Optical tracking result
        """
        if self.prev_frame is None or self.prev_features is None:
            return None
            
        # Use thermal-specific optical flow parameters
        next_features, status, error = cv2.calcOpticalFlowPyrLK(
            self.prev_frame, enhanced_frame, self.prev_features, None, 
            **self.lk_params_thermal
        )
        
        if next_features is None:
            return None
            
        # Filter features based on thermal gradients
        if self.adaptive_threshold:
            gradient_mag, _ = self.thermal_processor.calculate_thermal_gradient(enhanced_frame)
            good_features = []
            
            for i, (feature, st) in enumerate(zip(next_features, status)):
                if st == 1:
                    x, y = int(feature[0, 0]), int(feature[0, 1])
                    if 0 <= x < gradient_mag.shape[1] and 0 <= y < gradient_mag.shape[0]:
                        if gradient_mag[y, x] >= self.min_thermal_gradient:
                            good_features.append(feature)
                            
            if len(good_features) < 5:
                # Too few features, reinitialize
                self._reinitialize_thermal_features(enhanced_frame)
                return None
                
            next_features = np.array(good_features)
        else:
            # Standard filtering
            good_old = self.prev_features[status == 1]
            good_new = next_features[status == 1]
            
            if len(good_new) < 5:
                self._reinitialize_thermal_features(enhanced_frame)
                return None
                
            next_features = good_new.reshape(-1, 1, 2)
            
        # Calculate position
        current_position = np.mean(next_features[:, 0, :], axis=0)
        
        # Update state
        self.prev_frame = enhanced_frame
        self.prev_features = next_features
        
        # Create basic result
        result = TrackingResult(
            position=tuple(current_position),
            velocity=(0, 0),  # Will be calculated in fusion
            confidence=len(next_features) / self.max_features,
            features_count=len(next_features),
            timestamp=time.time()
        )
        
        return result
        
    def _track_thermal_target(self, temperature_data: np.ndarray) -> Optional[ThermalTarget]:
        """
        Track thermal target in temperature data
        
        Args:
            temperature_data: Temperature array
            
        Returns:
            Updated thermal target
        """
        if self.thermal_target is None:
            # Find new target
            targets = self.thermal_processor.detect_thermal_targets(temperature_data, None)
            if targets:
                self.thermal_target = targets[0]
                return self.thermal_target
            return None
            
        # Track existing target
        updated_target = self.thermal_processor.track_thermal_target(
            temperature_data, self.thermal_target
        )
        
        if updated_target:
            self.thermal_target = updated_target
            return updated_target
        else:
            # Lost target, try to find new one
            logger.warning("Lost thermal target, searching for new target")
            targets = self.thermal_processor.detect_thermal_targets(temperature_data, None)
            if targets:
                self.thermal_target = targets[0]
                return self.thermal_target
            return None
            
    def _fuse_tracking_results(self, optical_result: Optional[TrackingResult],
                              thermal_target: Optional[ThermalTarget],
                              temperature_data: np.ndarray) -> Optional[ThermalTrackingResult]:
        """
        Fuse optical and thermal tracking results
        
        Args:
            optical_result: Optical flow tracking result
            thermal_target: Thermal target tracking result
            temperature_data: Temperature array
            
        Returns:
            Fused thermal tracking result
        """
        # Handle cases where one tracker fails
        if optical_result is None and thermal_target is None:
            return None
        elif optical_result is None:
            # Use thermal only
            position = thermal_target.center
            confidence = thermal_target.confidence * 0.7  # Lower confidence
            features_count = 0
        elif thermal_target is None:
            # Use optical only
            position = optical_result.position
            confidence = optical_result.confidence * 0.7
            features_count = optical_result.features_count
        else:
            # Fuse both results
            optical_pos = np.array(optical_result.position)
            thermal_pos = np.array(thermal_target.center)
            
            # Weighted average based on confidence and settings
            optical_conf = optical_result.confidence * self.optical_weight
            thermal_conf = thermal_target.confidence * self.thermal_weight
            
            total_weight = optical_conf + thermal_conf
            if total_weight > 0:
                fused_pos = (optical_pos * optical_conf + thermal_pos * thermal_conf) / total_weight
                position = tuple(fused_pos)
                confidence = min(1.0, total_weight)
            else:
                position = optical_result.position
                confidence = optical_result.confidence
                
            features_count = optical_result.features_count
            
        # Get temperature at tracked position
        px, py = int(position[0]), int(position[1])
        if 0 <= py < temperature_data.shape[0] and 0 <= px < temperature_data.shape[1]:
            temperature = float(temperature_data[py, px])
            
            # Calculate temperature gradient
            gradient_mag, _ = self.thermal_processor.calculate_thermal_gradient(temperature_data)
            temp_gradient = float(gradient_mag[py, px])
        else:
            temperature = 0.0
            temp_gradient = 0.0
            
        # Calculate velocity
        if len(self.position_history) > 0:
            prev_pos = self.position_history[-1]
            dt = 1.0 / 25.0  # Assume 25 FPS for thermal camera
            velocity = ((position[0] - prev_pos[0]) / dt,
                       (position[1] - prev_pos[1]) / dt)
        else:
            velocity = (0.0, 0.0)
            
        # Count hotspots
        hotspots = self.thermal_processor.detect_thermal_targets(temperature_data, None)
        hotspot_count = len(hotspots)
        
        # Create thermal tracking result
        result = ThermalTrackingResult(
            position=position,
            velocity=velocity,
            confidence=confidence,
            features_count=features_count,
            timestamp=time.time(),
            temperature=temperature,
            thermal_confidence=thermal_target.confidence if thermal_target else 0.0,
            hotspot_count=hotspot_count,
            temp_gradient=temp_gradient
        )
        
        # Update position history
        self.position_history.append(position)
        
        return result
        
    def _create_roi_around_target(self, target: ThermalTarget, 
                                 frame_shape: Tuple[int, int]) -> Tuple[int, int, int, int]:
        """
        Create ROI around thermal target
        
        Args:
            target: Thermal target
            frame_shape: Frame dimensions (height, width)
            
        Returns:
            ROI tuple (x, y, width, height)
        """
        margin = 30  # Pixels around target
        
        x = max(0, target.center[0] - margin)
        y = max(0, target.center[1] - margin)
        w = min(margin * 2, frame_shape[1] - x)
        h = min(margin * 2, frame_shape[0] - y)
        
        return (x, y, w, h)
        
    def _reinitialize_thermal_features(self, frame: np.ndarray):
        """Reinitialize features for thermal tracking"""
        # Detect edges for feature-rich areas
        edges = self.thermal_processor.detect_thermal_edges(frame)
        
        # Find good features preferring edge regions
        features = cv2.goodFeaturesToTrack(
            frame,
            maxCorners=self.max_features,
            qualityLevel=self.quality_level * 0.7,  # Lower threshold for thermal
            minDistance=self.min_distance,
            mask=edges
        )
        
        if features is not None and len(features) > 10:
            self.prev_features = features
            self.tracking_active = True
            logger.info(f"Thermal features reinitialized: {len(features)}")
        else:
            # Try without edge mask
            features = cv2.goodFeaturesToTrack(
                frame,
                maxCorners=self.max_features,
                qualityLevel=self.quality_level * 0.5,
                minDistance=self.min_distance
            )
            
            if features is not None and len(features) > 5:
                self.prev_features = features
                self.tracking_active = True
                logger.info(f"Thermal features reinitialized (no edges): {len(features)}")
            else:
                self.tracking_active = False
                logger.warning("Failed to reinitialize thermal features")
                
    def set_thermal_weight(self, weight: float):
        """
        Set weight for thermal vs optical tracking
        
        Args:
            weight: Thermal weight (0-1, higher = more thermal influence)
        """
        self.thermal_weight = np.clip(weight, 0.0, 1.0)
        self.optical_weight = 1.0 - self.thermal_weight
        logger.info(f"Tracking weights: thermal={self.thermal_weight:.2f}, optical={self.optical_weight:.2f}")
        
    def get_temperature_stats(self) -> Dict[str, float]:
        """Get temperature statistics from tracking"""
        if len(self.temperature_history) == 0:
            return {}
            
        temps = np.array(self.temperature_history)
        
        return {
            'current_temp': float(temps[-1]) if len(temps) > 0 else 0.0,
            'mean_temp': float(np.mean(temps)),
            'max_temp': float(np.max(temps)),
            'min_temp': float(np.min(temps)),
            'std_temp': float(np.std(temps)),
            'stabilized_temp': self.thermal_processor.stabilize_temperature_reading(
                list(self.temperature_history)
            )
        }
        
    def draw_thermal_overlay(self, frame: np.ndarray, thermal_data: Dict) -> np.ndarray:
        """
        Draw thermal tracking overlay on frame
        
        Args:
            frame: Display frame (RGB)
            thermal_data: Thermal frame data
            
        Returns:
            Frame with overlay
        """
        output = frame.copy()
        
        # Draw tracked features
        if self.prev_features is not None:
            for feature in self.prev_features:
                x, y = feature.ravel()
                cv2.circle(output, (int(x), int(y)), 3, (0, 255, 0), -1)
                
        # Draw thermal target
        if self.thermal_target:
            cx, cy = self.thermal_target.center
            
            # Draw target box
            cv2.rectangle(output,
                         (cx - 15, cy - 15),
                         (cx + 15, cy + 15),
                         (255, 0, 0), 2)
                         
            # Draw temperature
            temp_text = f"{self.thermal_target.temperature:.1f}C"
            cv2.putText(output, temp_text,
                       (cx - 20, cy - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                       (255, 255, 0), 1)
                       
        # Draw temperature scale
        if 'min_temp' in thermal_data and 'max_temp' in thermal_data:
            scale_text = f"Range: {thermal_data['min_temp']:.1f}-{thermal_data['max_temp']:.1f}C"
            cv2.putText(output, scale_text,
                       (10, output.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                       (255, 255, 255), 1)
                       
        return output