#!/usr/bin/env python3
"""
Thermal camera calibration tool for Caddx Infra 256CA
Calibrates temperature readings and tracking parameters
"""

import argparse
import json
import time
import sys
import os
import numpy as np
import cv2
import logging
from typing import List, Tuple, Optional

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.thermal_camera import CaddxInfra256CA, ThermalConfig, ThermalColormap
from src.thermal_processing import ThermalProcessor
from src.thermal_tracker import ThermalTracker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThermalCalibrator:
    """Calibration tool for Caddx Infra 256CA thermal camera"""
    
    def __init__(self, port: str = '/dev/ttyUSB0'):
        """
        Initialize thermal calibrator
        
        Args:
            port: Serial port for thermal camera
        """
        self.thermal_config = ThermalConfig(port=port)
        self.thermal_camera = None
        self.processor = ThermalProcessor()
        self.calibration_data = {}
        
    def connect_camera(self) -> bool:
        """Connect to thermal camera"""
        logger.info(f"Connecting to Caddx Infra 256CA on {self.thermal_config.port}")
        
        self.thermal_camera = CaddxInfra256CA(self.thermal_config)
        if self.thermal_camera.initialize():
            self.thermal_camera.start_capture()
            time.sleep(1)  # Allow camera to stabilize
            logger.info("Thermal camera connected successfully")
            return True
        else:
            logger.error("Failed to connect to thermal camera")
            return False
            
    def calibrate_temperature(self, reference_temp: float):
        """
        Calibrate temperature readings using reference object
        
        Args:
            reference_temp: Known temperature of reference object
        """
        logger.info(f"Starting temperature calibration with reference: {reference_temp}°C")
        logger.info("Place reference object in center of view and press ENTER")
        input()
        
        # Capture multiple frames for averaging
        temps = []
        for i in range(10):
            frame = self.thermal_camera.get_frame(timeout=1.0)
            if frame and 'temperature' in frame:
                temp_array = frame['temperature']
                # Use center region
                h, w = temp_array.shape
                center_region = temp_array[h//3:2*h//3, w//3:2*w//3]
                temps.append(np.mean(center_region))
                time.sleep(0.1)
                
        if temps:
            measured_temp = np.mean(temps)
            offset = reference_temp - measured_temp
            
            self.thermal_camera.temp_offset = offset
            self.calibration_data['temperature_offset'] = offset
            
            logger.info(f"Measured: {measured_temp:.2f}°C")
            logger.info(f"Calibration offset: {offset:.2f}°C")
        else:
            logger.error("Failed to capture temperature data")
            
    def calibrate_emissivity(self):
        """Interactive emissivity calibration"""
        logger.info("Emissivity calibration")
        logger.info("Common emissivity values:")
        logger.info("  Human skin: 0.98")
        logger.info("  Water: 0.96")
        logger.info("  Concrete: 0.95")
        logger.info("  Aluminum: 0.05")
        logger.info("  Polished steel: 0.07")
        
        emissivity = float(input("Enter emissivity value (0.1-1.0): "))
        self.thermal_camera.set_emissivity(emissivity)
        self.calibration_data['emissivity'] = emissivity
        
        logger.info(f"Emissivity set to {emissivity}")
        
    def test_colormaps(self):
        """Test different thermal colormaps"""
        logger.info("Testing thermal colormaps (press any key to cycle, ESC to finish)")
        
        colormaps = list(ThermalColormap)
        current_idx = 0
        
        while True:
            # Set colormap
            self.thermal_camera.set_colormap(colormaps[current_idx])
            
            # Get frame
            frame = self.thermal_camera.get_frame(timeout=1.0)
            if frame:
                display = frame['colorized']
                
                # Add colormap name
                cv2.putText(display, f"Colormap: {colormaps[current_idx].value}",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Add temperature info
                cv2.putText(display, f"Min: {frame['min_temp']:.1f}C Max: {frame['max_temp']:.1f}C",
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Show frame
                cv2.imshow('Thermal Colormap Test', cv2.cvtColor(display, cv2.COLOR_RGB2BGR))
                
            key = cv2.waitKey(0) & 0xFF
            if key == 27:  # ESC
                break
            else:
                current_idx = (current_idx + 1) % len(colormaps)
                
        cv2.destroyAllWindows()
        
        # Ask for preference
        selected = input(f"Enter preferred colormap [{colormaps[0].value}]: ").strip()
        if selected:
            try:
                self.thermal_camera.set_colormap(ThermalColormap(selected))
                self.calibration_data['colormap'] = selected
                logger.info(f"Selected colormap: {selected}")
            except:
                logger.warning(f"Invalid colormap: {selected}")
                
    def calibrate_tracking(self):
        """Calibrate thermal tracking parameters"""
        logger.info("Thermal tracking calibration")
        
        # Create thermal tracker
        tracker = ThermalTracker()
        
        # Test tracking on live feed
        logger.info("Move a warm object in view. Press SPACE to capture good tracking, ESC to finish")
        
        tracking_samples = []
        
        while True:
            frame = self.thermal_camera.get_frame(timeout=1.0)
            if frame:
                # Initialize tracker if needed
                if not tracker.tracking_active:
                    if tracker.initialize_thermal(frame):
                        logger.info("Tracker initialized")
                        
                # Track
                result = tracker.track_thermal(frame)
                
                # Visualize
                display = frame['colorized'].copy()
                if result:
                    # Draw tracking result
                    px, py = map(int, result.position)
                    cv2.circle(display, (px, py), 5, (0, 255, 0), -1)
                    cv2.putText(display, f"Temp: {result.temperature:.1f}C",
                               (px + 10, py - 10), cv2.FONT_HERSHEY_SIMPLEX,
                               0.5, (0, 255, 0), 1)
                    cv2.putText(display, f"Confidence: {result.confidence:.2f}",
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                               0.5, (0, 255, 0), 1)
                               
                # Show
                cv2.imshow('Thermal Tracking Calibration', cv2.cvtColor(display, cv2.COLOR_RGB2BGR))
                
                key = cv2.waitKey(30) & 0xFF
                if key == 27:  # ESC
                    break
                elif key == ord(' ') and result:  # SPACE
                    tracking_samples.append({
                        'confidence': result.confidence,
                        'thermal_weight': tracker.thermal_weight,
                        'features': result.features_count
                    })
                    logger.info(f"Sample captured (total: {len(tracking_samples)})")
                    
        cv2.destroyAllWindows()
        
        if tracking_samples:
            # Calculate optimal parameters
            avg_confidence = np.mean([s['confidence'] for s in tracking_samples])
            
            if avg_confidence < 0.5:
                # Poor tracking, increase thermal weight
                optimal_weight = min(0.8, tracker.thermal_weight + 0.2)
            elif avg_confidence > 0.8:
                # Good tracking, can balance weights
                optimal_weight = 0.5
            else:
                optimal_weight = tracker.thermal_weight
                
            self.calibration_data['thermal_tracking_weight'] = optimal_weight
            logger.info(f"Recommended thermal tracking weight: {optimal_weight}")
            
    def test_hotspot_detection(self):
        """Test and calibrate hotspot detection"""
        logger.info("Testing hotspot detection")
        
        threshold = 95
        
        while True:
            frame = self.thermal_camera.get_frame(timeout=1.0)
            if frame:
                # Find hotspots
                hotspots = self.thermal_camera.find_hotspots(threshold)
                
                # Visualize
                display = frame['colorized'].copy()
                
                for i, (x, y, temp) in enumerate(hotspots[:5]):  # Show top 5
                    cv2.circle(display, (x, y), 10, (0, 0, 255), 2)
                    cv2.putText(display, f"#{i+1}: {temp:.1f}C",
                               (x + 15, y), cv2.FONT_HERSHEY_SIMPLEX,
                               0.4, (0, 0, 255), 1)
                               
                cv2.putText(display, f"Threshold: {threshold}% (UP/DOWN to adjust)",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                           0.5, (255, 255, 255), 1)
                cv2.putText(display, f"Hotspots: {len(hotspots)}",
                           (10, 50), cv2.FONT_HERSHEY_SIMPLEX,
                           0.5, (255, 255, 255), 1)
                           
                cv2.imshow('Hotspot Detection', cv2.cvtColor(display, cv2.COLOR_RGB2BGR))
                
                key = cv2.waitKey(30) & 0xFF
                if key == 27:  # ESC
                    break
                elif key == 82:  # UP arrow
                    threshold = min(99, threshold + 1)
                elif key == 84:  # DOWN arrow
                    threshold = max(50, threshold - 1)
                    
        cv2.destroyAllWindows()
        
        self.calibration_data['hotspot_threshold'] = threshold
        logger.info(f"Hotspot detection threshold set to {threshold}%")
        
    def test_temperature_range(self):
        """Determine optimal temperature range for scene"""
        logger.info("Analyzing temperature range (capture 5 seconds of data)")
        
        temps_min = []
        temps_max = []
        
        start_time = time.time()
        while time.time() - start_time < 5:
            frame = self.thermal_camera.get_frame(timeout=1.0)
            if frame:
                temps_min.append(frame['min_temp'])
                temps_max.append(frame['max_temp'])
                time.sleep(0.1)
                
        if temps_min and temps_max:
            scene_min = np.percentile(temps_min, 5)  # 5th percentile
            scene_max = np.percentile(temps_max, 95)  # 95th percentile
            
            # Add margin
            range_min = scene_min - 2.0
            range_max = scene_max + 2.0
            
            self.calibration_data['temperature_range'] = [range_min, range_max]
            logger.info(f"Recommended temperature range: {range_min:.1f}°C to {range_max:.1f}°C")
            
    def save_calibration(self, filename: str):
        """
        Save calibration data to file
        
        Args:
            filename: Output filename
        """
        # Add camera info
        self.calibration_data['camera'] = 'Caddx Infra 256CA'
        self.calibration_data['resolution'] = [256, 192]
        self.calibration_data['port'] = self.thermal_config.port
        
        with open(filename, 'w') as f:
            json.dump(self.calibration_data, f, indent=2)
            
        logger.info(f"Calibration saved to {filename}")
        
    def cleanup(self):
        """Cleanup resources"""
        if self.thermal_camera:
            self.thermal_camera.release()


def main():
    """Main calibration routine"""
    parser = argparse.ArgumentParser(description='Caddx Infra 256CA Thermal Camera Calibration')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port')
    parser.add_argument('--output', default='thermal_calibration.json', help='Output file')
    parser.add_argument('--temp', action='store_true', help='Calibrate temperature')
    parser.add_argument('--emissivity', action='store_true', help='Calibrate emissivity')
    parser.add_argument('--colormap', action='store_true', help='Test colormaps')
    parser.add_argument('--tracking', action='store_true', help='Calibrate tracking')
    parser.add_argument('--hotspot', action='store_true', help='Test hotspot detection')
    parser.add_argument('--range', action='store_true', help='Determine temperature range')
    parser.add_argument('--all', action='store_true', help='Run all calibrations')
    
    args = parser.parse_args()
    
    # Create calibrator
    calibrator = ThermalCalibrator(args.port)
    
    # Connect to camera
    if not calibrator.connect_camera():
        logger.error("Failed to connect to thermal camera")
        return 1
        
    try:
        # Run calibrations
        if args.all or args.temp:
            ref_temp = float(input("Enter reference temperature in Celsius: "))
            calibrator.calibrate_temperature(ref_temp)
            
        if args.all or args.emissivity:
            calibrator.calibrate_emissivity()
            
        if args.all or args.colormap:
            calibrator.test_colormaps()
            
        if args.all or args.tracking:
            calibrator.calibrate_tracking()
            
        if args.all or args.hotspot:
            calibrator.test_hotspot_detection()
            
        if args.all or args.range:
            calibrator.test_temperature_range()
            
        # Save calibration
        if calibrator.calibration_data:
            calibrator.save_calibration(args.output)
            
        logger.info("Calibration complete!")
        
    finally:
        calibrator.cleanup()
        
    return 0


if __name__ == '__main__':
    sys.exit(main())