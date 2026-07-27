"""
Optical tracking module using feature detection and optical flow
Optimized for real-time performance on Raspberry Pi Zero
"""

import numpy as np
import cv2
import time
import logging
from collections import deque
from dataclasses import dataclass
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class TrackingResult:
    """Container for tracking results"""
    position: Tuple[float, float]  # Current position (x, y)
    velocity: Tuple[float, float]  # Velocity (vx, vy)
    confidence: float  # Tracking confidence [0, 1]
    features_count: int  # Number of tracked features
    timestamp: float  # Timestamp


class OpticalTracker:
    """
    Lightweight optical tracker using Lucas-Kanade optical flow
    Optimized for Pi Zero's limited processing power
    """
    
    def __init__(self, max_features=50, quality_level=0.3, min_distance=10):
        """
        Initialize optical tracker
        
        Args:
            max_features: Maximum number of features to track
            quality_level: Quality threshold for corner detection
            min_distance: Minimum distance between features
        """
        self.max_features = max_features
        self.quality_level = quality_level
        self.min_distance = min_distance
        
        # Optical flow parameters (tuned for speed on Pi Zero)
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # Feature detection parameters
        self.feature_params = dict(
            maxCorners=max_features,
            qualityLevel=quality_level,
            minDistance=min_distance,
            blockSize=7
        )
        
        # State variables
        self.prev_frame = None
        self.prev_features = None
        self.position_history = deque(maxlen=10)
        self.velocity_filter = deque(maxlen=5)
        self.last_timestamp = None
        self.reference_position = None
        self.tracking_active = False
        
        # Kalman filter for smoothing
        self.kalman = self._init_kalman_filter()
        
    def _init_kalman_filter(self):
        """Initialize Kalman filter for position smoothing"""
        kalman = cv2.KalmanFilter(4, 2)
        kalman.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], np.float32)
        
        kalman.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], np.float32)
        
        kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
        kalman.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.1
        
        return kalman
        
    def initialize(self, frame: np.ndarray, roi: Optional[Tuple[int, int, int, int]] = None):
        """
        Initialize tracking with first frame
        
        Args:
            frame: Initial frame (grayscale or color)
            roi: Optional region of interest (x, y, width, height)
        """
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        else:
            gray = frame.copy()
            
        # Apply ROI if specified
        if roi:
            x, y, w, h = roi
            gray_roi = gray[y:y+h, x:x+w]
            mask = np.zeros_like(gray)
            mask[y:y+h, x:x+w] = 255
        else:
            gray_roi = gray
            mask = None
            
        # Detect initial features
        features = cv2.goodFeaturesToTrack(
            gray_roi, mask=mask, **self.feature_params
        )
        
        if features is not None and len(features) > 0:
            # Adjust feature coordinates if ROI was used
            if roi:
                features[:, :, 0] += roi[0]
                features[:, :, 1] += roi[1]
                
            self.prev_frame = gray
            self.prev_features = features
            self.reference_position = np.mean(features[:, 0, :], axis=0)
            self.tracking_active = True
            self.last_timestamp = time.time()
            
            # Initialize Kalman filter state
            self.kalman.statePre = np.array([
                [self.reference_position[0]],
                [self.reference_position[1]],
                [0],
                [0]
            ], np.float32)
            
            logger.info(f"Tracker initialized with {len(features)} features")
            return True
        else:
            logger.warning("No features found for tracking")
            return False
            
    def track(self, frame: np.ndarray) -> Optional[TrackingResult]:
        """
        Track features in new frame
        
        Args:
            frame: Current frame
            
        Returns:
            TrackingResult or None if tracking failed
        """
        if not self.tracking_active or self.prev_frame is None:
            return None
            
        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        else:
            gray = frame.copy()
            
        current_time = time.time()
        dt = current_time - self.last_timestamp if self.last_timestamp else 0.05
        
        # Calculate optical flow
        next_features, status, error = cv2.calcOpticalFlowPyrLK(
            self.prev_frame, gray, self.prev_features, None, **self.lk_params
        )
        
        if next_features is None:
            logger.warning("Optical flow calculation failed")
            return None
            
        # Filter good features
        good_old = self.prev_features[status == 1]
        good_new = next_features[status == 1]
        
        if len(good_new) < 5:  # Minimum features threshold
            logger.warning(f"Too few features tracked: {len(good_new)}")
            self._reinitialize_features(gray)
            return None
            
        # Calculate average displacement
        current_position = np.mean(good_new, axis=0)
        
        # Apply Kalman filter for smoothing
        measurement = np.array([[current_position[0]], [current_position[1]]], np.float32)
        self.kalman.correct(measurement)
        prediction = self.kalman.predict()
        filtered_position = (float(prediction[0]), float(prediction[1]))
        
        # Calculate velocity
        if len(self.position_history) > 0:
            prev_pos = self.position_history[-1]
            velocity = ((filtered_position[0] - prev_pos[0]) / dt,
                       (filtered_position[1] - prev_pos[1]) / dt)
        else:
            velocity = (0.0, 0.0)
            
        # Smooth velocity
        self.velocity_filter.append(velocity)
        if len(self.velocity_filter) > 0:
            smooth_velocity = tuple(np.mean(self.velocity_filter, axis=0))
        else:
            smooth_velocity = velocity
            
        # Calculate confidence based on feature count and error
        confidence = min(1.0, len(good_new) / self.max_features)
        mean_error = np.mean(error[status == 1])
        if mean_error > 10:
            confidence *= max(0.3, 1.0 - mean_error / 50.0)
            
        # Update state
        self.prev_frame = gray
        self.prev_features = good_new.reshape(-1, 1, 2)
        self.position_history.append(filtered_position)
        self.last_timestamp = current_time
        
        # Create result
        result = TrackingResult(
            position=filtered_position,
            velocity=smooth_velocity,
            confidence=confidence,
            features_count=len(good_new),
            timestamp=current_time
        )
        
        # Periodically refresh features to maintain tracking quality
        if len(good_new) < self.max_features * 0.5:
            self._add_new_features(gray, good_new)
            
        return result
        
    def _reinitialize_features(self, gray: np.ndarray):
        """Reinitialize features when tracking is poor"""
        features = cv2.goodFeaturesToTrack(gray, **self.feature_params)
        
        if features is not None and len(features) > 10:
            self.prev_features = features
            self.tracking_active = True
            logger.info(f"Features reinitialized: {len(features)}")
        else:
            self.tracking_active = False
            logger.warning("Failed to reinitialize features")
            
    def _add_new_features(self, gray: np.ndarray, existing_features: np.ndarray):
        """Add new features to maintain tracking quality"""
        # Create mask to avoid existing features
        mask = np.zeros_like(gray)
        mask[:] = 255
        
        for x, y in existing_features:
            cv2.circle(mask, (int(x), int(y)), self.min_distance, 0, -1)
            
        # Detect new features
        new_features = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=self.max_features - len(existing_features),
            qualityLevel=self.quality_level * 0.5,  # Lower quality threshold
            minDistance=self.min_distance,
            mask=mask
        )
        
        if new_features is not None and len(new_features) > 0:
            self.prev_features = np.vstack([
                existing_features.reshape(-1, 1, 2),
                new_features
            ])
            logger.debug(f"Added {len(new_features)} new features")
            
    def get_displacement(self) -> Tuple[float, float]:
        """Get displacement from reference position"""
        if not self.tracking_active or len(self.position_history) == 0:
            return (0.0, 0.0)
            
        current_pos = self.position_history[-1]
        return (current_pos[0] - self.reference_position[0],
                current_pos[1] - self.reference_position[1])
                
    def reset_reference(self):
        """Reset reference position to current position"""
        if len(self.position_history) > 0:
            self.reference_position = self.position_history[-1]
            logger.info("Reference position reset")
            
    def get_tracked_points(self) -> Optional[np.ndarray]:
        """Get current tracked feature points"""
        return self.prev_features if self.tracking_active else None
        
    def draw_features(self, frame: np.ndarray, color=(0, 255, 0)) -> np.ndarray:
        """
        Draw tracked features on frame
        
        Args:
            frame: Frame to draw on
            color: Color for features (B, G, R)
            
        Returns:
            Frame with features drawn
        """
        output = frame.copy()
        
        if self.prev_features is not None:
            for feature in self.prev_features:
                x, y = feature.ravel()
                cv2.circle(output, (int(x), int(y)), 3, color, -1)
                
        # Draw reference position
        if self.reference_position is not None:
            cv2.drawMarker(output, 
                          (int(self.reference_position[0]), int(self.reference_position[1])),
                          (0, 0, 255), cv2.MARKER_CROSS, 10, 2)
                          
        # Draw current center
        if len(self.position_history) > 0:
            current = self.position_history[-1]
            cv2.drawMarker(output,
                          (int(current[0]), int(current[1])),
                          (255, 0, 0), cv2.MARKER_SQUARE, 8, 2)
                          
        return output