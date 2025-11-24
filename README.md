# Betafly Optical Position Stabilization System

A lightweight optical position stabilization system designed for Raspberry Pi Zero, optimized for drone/UAV applications.

## Features

- **Real-time Optical Tracking**: Feature-based tracking using optimized OpenCV algorithms
- **PID Control**: Multi-axis stabilization with tunable PID controllers
- **Hardware Optimization**: Designed for Pi Zero's limited resources (512MB RAM, single-core)
- **Low Latency**: Sub-100ms tracking and control loop
- **Web Monitoring**: Real-time monitoring interface
- **Flexible Configuration**: JSON-based configuration with hot-reload

## System Architecture

```
┌─────────────────┐
│   Pi Camera     │
└────────┬────────┘
         │
    ┌────▼─────┐
    │  Capture  │
    │  Module   │
    └────┬─────┘
         │
    ┌────▼─────┐
    │  Optical  │
    │  Tracker  │
    └────┬─────┘
         │
    ┌────▼─────┐
    │    PID    │
    │ Controller│
    └────┬─────┘
         │
    ┌────▼─────┐
    │   Servo   │
    │  Control  │
    └────┬─────┘
         │
    ┌────▼─────┐
    │  2-Axis   │
    │  Gimbal   │
    └──────────┘
```

## Hardware Requirements

- Raspberry Pi Zero W/2W
- Pi Camera Module (v1.3 or v2)
- 2x SG90 Micro Servos (or similar)
- PCA9685 PWM Driver (optional, for better servo control)
- 5V 2A Power Supply
- Gimbal Mount (3D printed or purchased)

## Software Requirements

- Raspbian OS Lite (Bullseye or later)
- Python 3.9+
- OpenCV 4.5+ (optimized build)
- NumPy
- pigpio (for PWM control)

## Quick Start

1. **Install Dependencies**:
   ```bash
   sudo ./setup.sh
   ```

2. **Configure System**:
   ```bash
   cp config/default.json config/config.json
   nano config/config.json  # Edit settings
   ```

3. **Calibrate Camera**:
   ```bash
   python3 calibrate.py
   ```

4. **Run Stabilization**:
   ```bash
   sudo python3 main.py
   ```

5. **Monitor System** (optional):
   Open browser to `http://<pi-ip>:8080`

## Performance Metrics

- **Frame Rate**: 15-20 FPS (Pi Zero), 25-30 FPS (Pi Zero 2)
- **Tracking Latency**: 50-80ms
- **Control Update Rate**: 50Hz
- **Power Consumption**: ~2.5W (active), ~1W (idle)

## Configuration

Edit `config/config.json` to adjust:

- Camera settings (resolution, framerate)
- Tracking parameters (features, window size)
- PID gains (P, I, D for each axis)
- Servo limits and calibration
- System behavior (logging, monitoring)

## Project Structure

```
betafly-stabilization/
├── main.py                 # Main application entry point
├── setup.sh               # Installation script
├── calibrate.py           # Camera calibration tool
├── requirements.txt       # Python dependencies
├── config/
│   ├── default.json      # Default configuration
│   └── config.json       # User configuration
├── src/
│   ├── __init__.py
│   ├── camera.py         # Camera capture module
│   ├── tracker.py        # Optical tracking algorithms
│   ├── controller.py     # PID controller implementation
│   ├── servo.py          # Servo/PWM control
│   ├── stabilizer.py     # Main stabilization loop
│   └── utils.py          # Utility functions
├── web/
│   ├── server.py         # Web monitoring server
│   ├── static/           # Frontend assets
│   └── templates/        # HTML templates
└── tests/
    └── test_*.py         # Unit tests
```

## Troubleshooting

### Low Frame Rate
- Reduce resolution in config
- Decrease number of tracked features
- Enable GPU acceleration (Pi Zero 2 only)

### Jittery Movement
- Tune PID gains (start with low values)
- Increase motion smoothing
- Check servo power supply

### Camera Not Detected
- Enable camera: `sudo raspi-config` > Interface Options > Camera
- Check cable connection
- Verify with: `vcgencmd get_camera`

## Advanced Features

- **Adaptive Tracking**: Automatically adjusts parameters based on scene
- **Motion Prediction**: Kalman filter for smoother tracking
- **Multi-Target**: Track multiple objects simultaneously
- **Recording**: Save stabilized video output

## License

MIT License - See LICENSE file for details

## Contributing

Pull requests welcome! Please see CONTRIBUTING.md for guidelines.

## Support

For issues and questions, please open a GitHub issue or contact the maintainers.