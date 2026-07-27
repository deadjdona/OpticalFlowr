#!/usr/bin/env python3
"""
Test script for camera-based optical flow
Verifies camera connection and displays optical flow data
"""

import time
import sys
import argparse
from camera_optical_flow import CameraOpticalFlow, AnalogCameraFlow, OpticalFlowTracker, auto_detect_camera

def test_camera_detection():
    """Test camera detection"""
    print("Detecting cameras...")
    try:
        camera_id = auto_detect_camera()
        if camera_id is not None:
            print(f"✓ Camera detected at ID: {camera_id}")
            return camera_id
        else:
            print("✗ No camera detected")
            print("\nTroubleshooting:")
            print("  - Check camera cable connection")
            print("  - Run: vcgencmd get_camera")
            print("  - Run: ls /dev/video*")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Failed to detect camera: {e}")
        sys.exit(1)

def test_camera_initialization(camera_id=0):
    """Test camera initialization"""
    print(f"\nInitializing camera {camera_id}...")
    try:
        sensor = CameraOpticalFlow(
            camera_id=camera_id,
            width=320,
            height=240,
            fps=30,
            method='lucas_kanade'  # Faster for testing
        )
        sensor.start()
        time.sleep(1)  # Let camera warm up
        print("✓ Camera initialized successfully")
        return sensor
    except Exception as e:
        print(f"✗ Failed to initialize camera: {e}")
        sys.exit(1)

def test_motion_reading(sensor, duration=5):
    """Test optical flow motion reading"""
    print(f"\nReading optical flow for {duration} seconds...")
    print("Move the camera (or object below) to see motion values\n")
    print("Time(s) | Flow X  | Flow Y  | Quality")
    print("-" * 45)
    
    start_time = time.time()
    while time.time() - start_time < duration:
        flow_x, flow_y = sensor.get_motion()
        quality = sensor.get_surface_quality()
        elapsed = time.time() - start_time
        
        print(f"{elapsed:6.2f}  | {flow_x:7.2f} | {flow_y:7.2f} | {quality:3d}    ", end='\r')
        time.sleep(0.1)
    
    print("\n✓ Motion reading test complete")

def test_position_tracking(camera_id=0, duration=10):
    """Test position tracking with integration"""
    print(f"\nTesting position tracking for {duration} seconds...")
    print("Move the camera to track position\n")
    
    sensor = CameraOpticalFlow(
        camera_id=camera_id,
        width=320,
        height=240,
        fps=30,
        method='lucas_kanade'
    )
    sensor.start()
    time.sleep(1)  # Camera warm-up
    
    tracker = OpticalFlowTracker(sensor, scale_factor=0.001, height_m=0.5)
    
    print("Time(s) | Pos X(m) | Pos Y(m) | Vel X(m/s) | Vel Y(m/s) | Quality")
    print("-" * 75)
    
    start_time = time.time()
    while time.time() - start_time < duration:
        pos_x, pos_y = tracker.update()
        vel_x, vel_y = tracker.get_velocity()
        quality = tracker.get_surface_quality()
        elapsed = time.time() - start_time
        
        print(
            f"{elapsed:6.2f}  | {pos_x:8.4f} | {pos_y:8.4f} | "
            f"{vel_x:10.4f} | {vel_y:10.4f} | {quality:3d}    ",
            end='\r'
        )
        time.sleep(0.05)
    
    print("\n✓ Position tracking test complete")
    
    # Final position
    print(f"\nFinal position: ({pos_x:.4f}, {pos_y:.4f}) meters")
    
    sensor.stop()

def test_surface_quality(sensor, duration=5):
    """Monitor surface quality over time"""
    print(f"\nMonitoring surface quality for {duration} seconds...")
    print("Quality values: <100 (poor), 100-200 (good), >200 (excellent)\n")
    
    qualities = []
    start_time = time.time()
    
    while time.time() - start_time < duration:
        quality = sensor.get_surface_quality()
        qualities.append(quality)
        elapsed = time.time() - start_time
        
        bar_length = min(quality // 5, 50)
        print(f"Time: {elapsed:5.2f}s | Quality: {quality:3d} {'█' * bar_length}    ", end='\r')
        time.sleep(0.1)
    
    print("\n")
    avg_quality = sum(qualities) / len(qualities) if qualities else 0
    min_quality = min(qualities) if qualities else 0
    max_quality = max(qualities) if qualities else 0
    
    print(f"Average quality: {avg_quality:.1f}")
    print(f"Range: {min_quality} - {max_quality}")
    
    if avg_quality < 100:
        print("⚠️  Low quality - improve lighting or surface texture")
        print("    Tips:")
        print("    - Ensure surface has visible texture (not blank)")
        print("    - Check lighting conditions")
        print("    - Clean camera lens")
    elif avg_quality < 200:
        print("✓ Good quality - suitable for tracking")
    else:
        print("✓ Excellent quality - optimal for tracking")

def test_camera_capture(sensor):
    """Test camera frame capture"""
    print("\nTesting camera frame capture...")
    try:
        frame = sensor.get_current_frame()
        if frame is not None:
            print(f"✓ Frame captured successfully")
            print(f"  Resolution: {frame.shape[1]}x{frame.shape[0]}")
            print(f"  Channels: {frame.shape[2] if len(frame.shape) > 2 else 1}")
        else:
            print("✗ Failed to capture frame")
    except Exception as e:
        print(f"✗ Frame capture error: {e}")

def main():
    parser = argparse.ArgumentParser(description='Test camera-based optical flow')
    parser.add_argument(
        '-t', '--test',
        choices=['detection', 'motion', 'tracking', 'quality', 'capture', 'all'],
        default='all',
        help='Test to run'
    )
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=5,
        help='Test duration in seconds'
    )
    parser.add_argument(
        '-c', '--camera',
        type=int,
        default=None,
        help='Camera ID (auto-detect if not specified)'
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("Camera-Based Optical Flow Test")
    print("=" * 50)
    print()
    
    try:
        # Detect or use specified camera
        if args.camera is None:
            if args.test in ['detection', 'all']:
                camera_id = test_camera_detection()
            else:
                camera_id = auto_detect_camera()
                if camera_id is None:
                    print("✗ No camera detected. Specify with -c option.")
                    sys.exit(1)
        else:
            camera_id = args.camera
            print(f"Using specified camera ID: {camera_id}")
        
        # Initialize camera for tests
        if args.test not in ['detection', 'tracking']:
            sensor = test_camera_initialization(camera_id)
        
        # Run tests
        if args.test in ['capture', 'all']:
            test_camera_capture(sensor)
        
        if args.test in ['motion', 'all']:
            test_motion_reading(sensor, args.duration)
        
        if args.test in ['quality', 'all']:
            test_surface_quality(sensor, args.duration)
        
        if args.test in ['tracking', 'all']:
            if args.test != 'tracking':
                sensor.stop()
            test_position_tracking(camera_id, args.duration * 2)
        elif args.test not in ['detection']:
            sensor.stop()
        
        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
