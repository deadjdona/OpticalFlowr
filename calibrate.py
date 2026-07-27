#!/usr/bin/env python3
"""
Calibration tool for Betafly optical stabilization system
Calibrates camera intrinsics and servo ranges
"""

import argparse
import json
import time
import sys
import os
import numpy as np
import cv2
import logging
from typing import List, Tuple

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.camera import Camera
from src.servo import ServoController, ServoConfig
from src.utils import create_calibration_pattern, check_raspberry_pi

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CameraCalibrator:
    """Camera calibration using checkerboard pattern"""
    
    def __init__(self, pattern_size: Tuple[int, int] = (9, 6)):
        """
        Initialize calibrator
        
        Args:
            pattern_size: Checkerboard inner corners (width, height)
        """
        self.pattern_size = pattern_size
        self.calibration_images = []
        self.object_points = []
        self.image_points = []
        
    def capture_calibration_images(self, camera: Camera, count: int = 10):
        """
        Capture calibration images interactively
        
        Args:
            camera: Camera instance
            count: Number of images to capture
        """
        logger.info(f"Capturing {count} calibration images")
        logger.info("Position checkerboard at different angles and distances")
        logger.info("Press SPACE to capture, ESC to finish early")
        
        camera.start_capture()
        captured = 0
        
        while captured < count:
            frame = camera.get_frame()
            if frame is None:
                continue
                
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            
            # Find checkerboard corners
            ret, corners = cv2.findChessboardCorners(gray, self.pattern_size)
            
            # Draw corners
            display = frame.copy()
            if ret:
                cv2.drawChessboardCorners(display, self.pattern_size, corners, ret)
                status = "Pattern found - Press SPACE to capture"
                color = (0, 255, 0)
            else:
                status = "No pattern detected"
                color = (0, 0, 255)
                
            # Add status text
            cv2.putText(display, status, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(display, f"Captured: {captured}/{count}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                       
            # Show frame
            cv2.imshow('Camera Calibration', cv2.cvtColor(display, cv2.COLOR_RGB2BGR))
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' ') and ret:
                # Capture image
                self.calibration_images.append(gray)
                captured += 1
                logger.info(f"Captured image {captured}/{count}")
                time.sleep(0.5)  # Brief pause
            elif key == 27:  # ESC
                break
                
        cv2.destroyAllWindows()
        camera.stop_capture()
        
        logger.info(f"Captured {len(self.calibration_images)} calibration images")
        
    def calibrate(self) -> dict:
        """
        Perform camera calibration
        
        Returns:
            Calibration parameters
        """
        if len(self.calibration_images) < 3:
            logger.error("Need at least 3 calibration images")
            return None
            
        logger.info("Performing camera calibration...")
        
        # Prepare object points
        objp = np.zeros((self.pattern_size[0] * self.pattern_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.pattern_size[0], 0:self.pattern_size[1]].T.reshape(-1, 2)
        
        for img in self.calibration_images:
            ret, corners = cv2.findChessboardCorners(img, self.pattern_size)
            if ret:
                # Refine corners
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners = cv2.cornerSubPix(img, corners, (11, 11), (-1, -1), criteria)
                
                self.object_points.append(objp)
                self.image_points.append(corners)
                
        # Calibrate camera
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            self.object_points, self.image_points, 
            self.calibration_images[0].shape[::-1], None, None
        )
        
        if ret:
            # Calculate reprojection error
            total_error = 0
            for i in range(len(self.object_points)):
                imgpoints2, _ = cv2.projectPoints(
                    self.object_points[i], rvecs[i], tvecs[i], mtx, dist
                )
                error = cv2.norm(self.image_points[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
                total_error += error
                
            avg_error = total_error / len(self.object_points)
            
            # Extract calibration results
            calibration = {
                'camera_matrix': mtx.tolist(),
                'distortion_coefficients': dist.tolist(),
                'reprojection_error': avg_error,
                'image_size': self.calibration_images[0].shape[::-1],
                'calibration_images_count': len(self.calibration_images)
            }
            
            # Calculate FOV
            fx = mtx[0, 0]
            fy = mtx[1, 1]
            h, w = self.calibration_images[0].shape
            fov_x = 2 * np.arctan(w / (2 * fx)) * 180 / np.pi
            fov_y = 2 * np.arctan(h / (2 * fy)) * 180 / np.pi
            
            calibration['fov_horizontal'] = fov_x
            calibration['fov_vertical'] = fov_y
            
            logger.info(f"Calibration successful!")
            logger.info(f"Reprojection error: {avg_error:.3f} pixels")
            logger.info(f"FOV: {fov_x:.1f}° x {fov_y:.1f}°")
            
            return calibration
        else:
            logger.error("Calibration failed")
            return None


class ServoCalibrator:
    """Interactive servo calibration"""
    
    def __init__(self, servo_controller: ServoController):
        """
        Initialize servo calibrator
        
        Args:
            servo_controller: Servo controller instance
        """
        self.servo = servo_controller
        
    def calibrate_range(self, axis: str = 'pan') -> dict:
        """
        Calibrate servo range interactively
        
        Args:
            axis: 'pan' or 'tilt'
            
        Returns:
            Calibration results
        """
        logger.info(f"Starting {axis} servo calibration")
        logger.info("Use arrow keys to adjust position, SPACE to confirm")
        
        calibration = {
            'min_angle': -90,
            'center_angle': 0,
            'max_angle': 90,
            'min_pulse_ms': 0.5,
            'max_pulse_ms': 2.5
        }
        
        # Test center position
        logger.info("Adjust to CENTER position and press SPACE")
        angle = self._adjust_servo(axis, 0)
        calibration['center_angle'] = angle
        
        # Test minimum position
        logger.info("Adjust to MINIMUM position and press SPACE")
        angle = self._adjust_servo(axis, -45)
        calibration['min_angle'] = angle
        
        # Test maximum position
        logger.info("Adjust to MAXIMUM position and press SPACE")
        angle = self._adjust_servo(axis, 45)
        calibration['max_angle'] = angle
        
        # Return to center
        self.servo.center()
        
        logger.info(f"{axis} calibration complete: {calibration}")
        return calibration
        
    def _adjust_servo(self, axis: str, initial_angle: float) -> float:
        """
        Interactively adjust servo position
        
        Args:
            axis: 'pan' or 'tilt'
            initial_angle: Starting angle
            
        Returns:
            Final angle
        """
        angle = initial_angle
        step = 1.0
        
        while True:
            # Set servo position
            if axis == 'pan':
                self.servo.set_angle(pan=angle)
            else:
                self.servo.set_angle(tilt=angle)
                
            # Display current angle
            print(f"\rCurrent angle: {angle:6.1f}° (↑/↓: adjust, SHIFT+↑/↓: fine, SPACE: confirm)", end='')
            
            # Wait for key press (simplified for non-blocking input)
            # In production, use a proper key capture library
            import termios
            import tty
            
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setraw(sys.stdin.fileno())
                key = sys.stdin.read(1)
                
                if key == ' ':  # SPACE - confirm
                    break
                elif key == '\x1b':  # Arrow key sequence
                    sys.stdin.read(1)  # Skip [
                    arrow = sys.stdin.read(1)
                    if arrow == 'A':  # Up arrow
                        angle = min(90, angle + step)
                    elif arrow == 'B':  # Down arrow
                        angle = max(-90, angle - step)
                elif key == 'q':  # Quit
                    break
                    
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                
        print()  # New line
        return angle
        
    def test_sweep(self):
        """Test servo movement with sweep pattern"""
        logger.info("Testing servo sweep pattern...")
        self.servo.sweep_test('both', duration=5.0)
        logger.info("Sweep test complete")


def main():
    """Main calibration routine"""
    parser = argparse.ArgumentParser(description='Betafly Stabilization Calibration Tool')
    parser.add_argument('--camera', action='store_true', help='Calibrate camera')
    parser.add_argument('--servo', action='store_true', help='Calibrate servos')
    parser.add_argument('--test', action='store_true', help='Test servo sweep')
    parser.add_argument('--output', default='calibration.json', help='Output file')
    parser.add_argument('--pattern-size', nargs=2, type=int, default=[9, 6],
                       help='Checkerboard pattern size (inner corners)')
    parser.add_argument('--resolution', nargs=2, type=int, default=[640, 480],
                       help='Camera resolution for calibration')
    
    args = parser.parse_args()
    
    # Check if running on Raspberry Pi
    pi_info = check_raspberry_pi()
    if pi_info['is_pi']:
        logger.info(f"Running on {pi_info['model']} with {pi_info['memory']}")
    else:
        logger.warning("Not running on Raspberry Pi - hardware features may not work")
        
    calibration_data = {}
    
    # Load existing calibration if it exists
    if os.path.exists(args.output):
        with open(args.output, 'r') as f:
            calibration_data = json.load(f)
        logger.info(f"Loaded existing calibration from {args.output}")
        
    # Camera calibration
    if args.camera:
        logger.info("Starting camera calibration...")
        
        # Initialize camera
        camera = Camera(resolution=tuple(args.resolution))
        if not camera.initialize():
            logger.error("Failed to initialize camera")
            return 1
            
        # Perform calibration
        calibrator = CameraCalibrator(pattern_size=tuple(args.pattern_size))
        calibrator.capture_calibration_images(camera, count=10)
        
        camera_calib = calibrator.calibrate()
        if camera_calib:
            calibration_data['camera'] = camera_calib
            
        camera.release()
        
    # Servo calibration
    if args.servo:
        logger.info("Starting servo calibration...")
        
        # Initialize servos
        servo = ServoController()
        calibrator = ServoCalibrator(servo)
        
        # Calibrate pan
        pan_calib = calibrator.calibrate_range('pan')
        calibration_data['pan_servo'] = pan_calib
        
        # Calibrate tilt
        tilt_calib = calibrator.calibrate_range('tilt')
        calibration_data['tilt_servo'] = tilt_calib
        
        servo.cleanup()
        
    # Test servos
    if args.test:
        logger.info("Testing servos...")
        servo = ServoController()
        calibrator = ServoCalibrator(servo)
        calibrator.test_sweep()
        servo.cleanup()
        
    # Save calibration
    if calibration_data:
        with open(args.output, 'w') as f:
            json.dump(calibration_data, f, indent=2)
        logger.info(f"Calibration saved to {args.output}")
        
    logger.info("Calibration complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())