# Betafly Optical Position Stabilization System

A lightweight optical position stabilization system designed for Raspberry Pi Zero, optimized for drone/UAV applications.

## Features

- **Real-time Optical Tracking**: Feature-based tracking using optimized OpenCV algorithms
- **Thermal Imaging Support**: Full support for Caddx Infra 256CA (256x192 LWIR thermal camera)
- **Hybrid Tracking**: Fuses optical and thermal tracking for robust performance
- **PID Control**: Multi-axis stabilization with tunable PID controllers
- **Hardware Optimization**: Designed for Pi Zero's limited resources (512MB RAM, single-core)
- **Low Latency**: Sub-100ms tracking and control loop
- **Web Monitoring**: Real-time monitoring interface with thermal visualization
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
- Camera Options:
  - Pi Camera Module (v1.3 or v2) for visible light
  - Caddx Infra 256CA for thermal imaging (256x192 LWIR)
- 2x SG90 Micro Servos (or similar)
- PCA9685 PWM Driver (optional, for better servo control)
- 5V 2A Power Supply (3A recommended for thermal camera)
- Gimbal Mount (3D printed or purchased)
- For thermal camera: USB-to-Serial adapter or UART connection

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

## Thermal Camera Support (Caddx Infra 256CA)

The system fully supports the Caddx Infra 256CA thermal camera, providing:

### Features
- 256x192 resolution LWIR thermal imaging
- Temperature measurement and calibration
- Multiple thermal colormaps (Ironbow, White Hot, Black Hot, etc.)
- Hotspot detection and tracking
- Thermal-optical fusion tracking
- Temperature-based target detection

### Setup
1. **Connect Hardware**:
   - Connect Caddx Infra 256CA via USB-Serial adapter to Pi
   - Default port: `/dev/ttyUSB0` (or `/dev/ttyAMA0` for GPIO UART)

2. **Enable Thermal Mode**:
   ```bash
   # Use thermal configuration
   cp config/thermal.json config/config.json
   # Or set in existing config:
   # "use_thermal_camera": true
   ```

3. **Calibrate Thermal Camera**:
   ```bash
   python3 calibrate_thermal.py --all
   ```

### Thermal Tracking Modes
- **Thermal Only**: Track hottest object in scene
- **Hybrid**: Combine thermal and optical features (best performance)
- **Temperature Threshold**: Track objects within specific temperature range

## Configuration

Edit `config/config.json` to adjust:

- Camera settings (resolution, framerate, thermal/visible)
- Thermal settings (port, colormap, temperature range)
- Tracking parameters (features, window size, thermal weight)
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