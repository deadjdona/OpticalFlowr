#!/usr/bin/env python3
"""
Betafly Optical Position Stabilization System
Main application entry point
"""

import argparse
import json
import logging
import sys
import os
import time
import signal
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.stabilizer import Stabilizer, StabilizerConfig
from src.utils import check_raspberry_pi, optimize_for_pi_zero

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BetaflyStabilization:
    """Main application controller"""
    
    def __init__(self, config_file: str = None):
        """
        Initialize Betafly stabilization system
        
        Args:
            config_file: Path to configuration file
        """
        # Load configuration
        if config_file and os.path.exists(config_file):
            self.config = StabilizerConfig.from_json(config_file)
            logger.info(f"Loaded configuration from {config_file}")
        else:
            self.config = StabilizerConfig()
            logger.info("Using default configuration")
            
        # Initialize stabilizer
        self.stabilizer = Stabilizer(self.config)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = False
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        
    def start(self):
        """Start stabilization system"""
        logger.info("Starting Betafly Stabilization System...")
        
        # Check hardware
        pi_info = check_raspberry_pi()
        if pi_info['is_pi']:
            logger.info(f"Running on {pi_info['model']} with {pi_info['memory']}")
            if 'Zero' in pi_info.get('model', ''):
                logger.info("Detected Pi Zero - applying optimizations")
                optimize_for_pi_zero()
        else:
            logger.warning("Not running on Raspberry Pi - some features may not work")
            
        # Initialize hardware
        if not self.stabilizer.initialize():
            logger.error("Failed to initialize stabilizer")
            return False
            
        # Start stabilization
        self.stabilizer.start()
        self.running = True
        
        # Wait a moment for system to stabilize
        time.sleep(2)
        
        # Enable stabilization
        self.stabilizer.enable_stabilization(True)
        
        logger.info("System running - press Ctrl+C to stop")
        return True
        
    def stop(self):
        """Stop stabilization system"""
        if self.running:
            logger.info("Stopping system...")
            self.stabilizer.stop()
            self.stabilizer.cleanup()
            self.running = False
            logger.info("System stopped")
            
    def run_interactive(self):
        """Run with interactive console"""
        if not self.start():
            return
            
        logger.info("Interactive mode - enter commands (help for list)")
        
        while self.running:
            try:
                cmd = input("> ").strip().lower()
                
                if cmd == 'help':
                    print("Commands:")
                    print("  enable/disable - Enable/disable stabilization")
                    print("  reset - Reset tracking reference")
                    print("  status - Show system status")
                    print("  gains <axis> <kp> <ki> <kd> - Set PID gains")
                    print("  capture <filename> - Capture calibration image")
                    print("  record on/off - Enable/disable data recording")
                    print("  quit - Exit program")
                    
                elif cmd == 'enable':
                    self.stabilizer.enable_stabilization(True)
                    print("Stabilization enabled")
                    
                elif cmd == 'disable':
                    self.stabilizer.enable_stabilization(False)
                    print("Stabilization disabled")
                    
                elif cmd == 'reset':
                    self.stabilizer.reset_tracking()
                    print("Tracking reset")
                    
                elif cmd == 'status':
                    status = self.stabilizer.get_status()
                    print(f"Status: {json.dumps(status, indent=2)}")
                    
                elif cmd.startswith('gains'):
                    parts = cmd.split()
                    if len(parts) == 5:
                        axis = parts[1]
                        kp, ki, kd = float(parts[2]), float(parts[3]), float(parts[4])
                        self.stabilizer.set_pid_gains(axis, kp, ki, kd)
                        print(f"Set {axis} gains: P={kp}, I={ki}, D={kd}")
                    else:
                        print("Usage: gains <pan|tilt> <kp> <ki> <kd>")
                        
                elif cmd.startswith('capture'):
                    parts = cmd.split()
                    if len(parts) == 2:
                        if self.stabilizer.capture_calibration_image(parts[1]):
                            print(f"Image saved to {parts[1]}")
                        else:
                            print("Capture failed")
                    else:
                        print("Usage: capture <filename>")
                        
                elif cmd == 'record on':
                    self.config.enable_recording = True
                    print("Recording enabled")
                    
                elif cmd == 'record off':
                    self.config.enable_recording = False
                    print("Recording disabled")
                    
                elif cmd in ['quit', 'exit']:
                    break
                    
                elif cmd == '':
                    continue
                    
                else:
                    print(f"Unknown command: {cmd}")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Command error: {e}")
                
        self.stop()
        
    def run_daemon(self):
        """Run as background daemon"""
        if not self.start():
            return
            
        try:
            while self.running:
                time.sleep(1)
                
                # Log status periodically
                if int(time.time()) % 10 == 0:
                    status = self.stabilizer.get_status()
                    logger.debug(f"Status: FPS={status['stats']['tracking_fps']:.1f}, "
                               f"Confidence={status['stats']['tracking_confidence']:.2f}")
                               
        except KeyboardInterrupt:
            pass
            
        self.stop()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Betafly Optical Position Stabilization')
    parser.add_argument('--config', '-c', default='config/config.json',
                       help='Configuration file path')
    parser.add_argument('--daemon', '-d', action='store_true',
                       help='Run as daemon (no interaction)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    parser.add_argument('--test', action='store_true',
                       help='Run system test')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Copy default config if needed
    if not os.path.exists(args.config):
        default_config = 'config/default.json'
        if os.path.exists(default_config):
            import shutil
            os.makedirs(os.path.dirname(args.config), exist_ok=True)
            shutil.copy(default_config, args.config)
            logger.info(f"Created config from default: {args.config}")
            
    # Run system test
    if args.test:
        logger.info("Running system test...")
        app = BetaflyStabilization(args.config)
        
        if app.stabilizer.initialize():
            logger.info("✓ Hardware initialization successful")
            
            # Test camera
            app.stabilizer.camera.start_capture()
            time.sleep(1)
            frame = app.stabilizer.camera.get_frame()
            if frame is not None:
                logger.info(f"✓ Camera capture working: {frame.shape}")
            else:
                logger.error("✗ Camera capture failed")
                
            # Test servos
            logger.info("Testing servo sweep...")
            app.stabilizer.servos.sweep_test('both', duration=3.0)
            logger.info("✓ Servo control working")
            
            app.stabilizer.cleanup()
            logger.info("System test complete!")
        else:
            logger.error("✗ Hardware initialization failed")
            
        return 0
        
    # Create application
    app = BetaflyStabilization(args.config)
    
    # Run in appropriate mode
    if args.daemon:
        app.run_daemon()
    else:
        app.run_interactive()
        
    return 0


if __name__ == '__main__':
    sys.exit(main())