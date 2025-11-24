# Betafly Camera-Based Position Stabilization

A complete camera-based position stabilization system for the Betafly drone, optimized for Raspberry Pi Zero with CSI cameras.

## ✨ Features

- **🌐 Web Interface**: Beautiful real-time dashboard for monitoring and configuration (port 8080)
- **📷 Camera Support**: Raspberry Pi CSI cameras (IMX219, OV5647), USB cameras, and analog FPV cameras
- **🎮 Manual Stick Inputs**: RC receiver integration with SBUS/PWM support and smooth blending
- **🔧 Live Configuration**: Edit PID gains and settings through web GUI
- **📊 Real-time Visualization**: Live position tracking and control output graphs

## Core Features

- **Camera-Based Optical Flow**: Uses computer vision for precise motion tracking
- **Position Hold**: Maintains GPS-free position hold using visual odometry
- **Velocity Damping**: Reduces drift and oscillations during flight
- **PID Control**: Tunable PID controllers for X and Y axis stabilization
- **Multiple Modes**: Off, velocity damping, and position hold modes
- **Real-time Logging**: Optional CSV logging for flight data analysis
- **Lightweight**: Optimized for Raspberry Pi Zero's limited resources

## Hardware Requirements

### Required Components
- **Raspberry Pi Zero W** (or Zero 2 W for better performance)
- **Camera** (choose one):
  - **Raspberry Pi Camera Module** (IMX219, OV5647) - **Recommended** ⭐
  - USB Webcam (for testing and development)
  - Analog FPV Camera via USB capture card
- **Flight Controller** (Betaflight, iNav, or ArduPilot compatible)
- **Power Supply** (5V for Pi, shared with drone battery via BEC)

### Camera Connection

#### Raspberry Pi Camera Module (CSI) - **Recommended** ⭐

Supported sensors:
- **IMX219** - 8MP (Pi Camera Module V2)
- **OV5647** - 5MP (Pi Camera Module V1)
- **IMX477** - 12MP (Pi HQ Camera)
- **IMX708** - 12MP (Pi Camera Module V3)

**Connection:**
```
┌──────────────────────────────────────────┐
│  Camera Module                           │
│  ┌───────────┐         Ribbon Cable     │
│  │  IMX219   │  ════════════════════╗   │
│  │           │                      ║   │
│  └───────────┘                      ║   │
│                                     ║   │
│  Raspberry Pi Zero                  ║   │
│  ┌─────────────────┐                ║   │
│  │                 │  ┌──────────┐  ║   │
│  │    [USB]        │  │ CSI Port │←═╝   │
│  │                 │  └──────────┘      │
│  └─────────────────┘                    │
└──────────────────────────────────────────┘

- Blue side of cable faces USB port
- Metal contacts face HDMI ports
- Camera lens faces downward (for optical flow)
```

**Benefits of CSI Camera:**
- ✅ Direct connection, no USB needed
- ✅ Low latency and power consumption
- ✅ High frame rates (up to 90fps)
- ✅ Compact and integrated
- ✅ Officially supported

**Important**: Camera must be mounted facing **downward** with clear view of the ground for optical flow tracking.

For detailed camera setup and wiring, see **[CAMERA_SETUP.md](CAMERA_SETUP.md)**.  
For flight controller wiring, see **[WIRING_GUIDE.md](WIRING_GUIDE.md)**.

## Software Installation

### 1. Prepare Raspberry Pi Zero

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3 and pip (if not already installed)
sudo apt-get install python3 python3-pip -y

# Enable Camera interface
sudo raspi-config
# Navigate to: Interface Options -> Camera -> Enable
```

### 2. Clone Repository

```bash
cd ~
git clone https://github.com/yourusername/betafly-stabilization.git
cd betafly-stabilization
```

### 3. Install Dependencies

```bash
# Install Python packages
pip3 install -r requirements.txt

# Make main script executable
chmod +x betafly_stabilizer.py
```

### 4. Test Camera Connection

```bash
# Quick camera test (for CSI camera)
libcamera-still -o test.jpg

# Or test with Python
python3 -c "from camera_optical_flow import auto_detect_camera; print(f'Camera ID: {auto_detect_camera()}')"
```

## Configuration

Edit `config.json` to customize the system for your setup:

### Key Parameters

```json
{
  "sensor": {
    "rotation": 0,  // Adjust based on sensor mounting orientation
  },
  "tracker": {
    "initial_height": 0.5,  // Expected flight height in meters
  },
  "pid": {
    "position_x": {
      "kp": 0.5,  // Increase for more aggressive position correction
      "ki": 0.1,  // Increase to eliminate steady-state error
      "kd": 0.2   // Increase to reduce oscillations
    }
  },
  "stabilizer": {
    "max_tilt_angle": 15.0,  // Maximum tilt command in degrees
    "velocity_damping": 0.3  // Damping factor (0-1)
  },
  "control": {
    "update_rate_hz": 50  // Control loop frequency
  }
}
```

## Usage

### Quick Start with Web Interface

```bash
# Start advanced system with web interface (recommended)
./betafly_stabilizer_advanced.py

# Access web interface at:
# http://raspberrypi.local:8080
```

The web interface provides:
- Real-time position and velocity display
- Live control output visualization
- Configuration editor
- Mode switching controls
- Stick input monitoring

### Basic Command Line Usage

```bash
# Start with velocity damping (reduces drift)
./betafly_stabilizer.py --mode velocity_damping

# Start advanced system with all features
./betafly_stabilizer_advanced.py --mode position_hold

# Use custom config file
./betafly_stabilizer_advanced.py --config my_config.json

# Enable data logging
./betafly_stabilizer_advanced.py --log --mode position_hold

# Disable web interface
./betafly_stabilizer_advanced.py --no-web
```

### Using Different Camera Types

```bash
# CSI camera (default - Raspberry Pi Camera)
./betafly_stabilizer_advanced.py

# USB camera
# Edit config.json: "sensor": {"type": "usb_camera"}
./betafly_stabilizer_advanced.py --config config.json

# Analog camera via USB capture card
# Edit config.json: "sensor": {"type": "analog_usb"}
./betafly_stabilizer_advanced.py --config config.json
```

### Command Line Options

```
-c, --config FILE       Configuration file (JSON)
-m, --mode MODE         Initial mode: off, velocity_damping, position_hold
-l, --log              Enable CSV data logging
-v, --verbose          Enable verbose logging
```

### Operating Modes

1. **Off**: No stabilization (pass-through)
2. **Velocity Damping**: Reduces drift by opposing velocity
3. **Position Hold**: Maintains position at the point where mode was activated

## Integration with Flight Controller

The system outputs pitch and roll correction angles that need to be sent to your flight controller via serial (UART) communication.

### Wiring: Pi Zero to Flight Controller

Connect via UART (TX/RX pins):

```
┌─────────────────────┬───────────────────────────────┐
│ Pi Zero             │ Flight Controller             │
├─────────────────────┼───────────────────────────────┤
│ Pin 8 (GPIO14 TX)   │ RX (UART Receive)             │
│ Pin 10 (GPIO15 RX)  │ TX (UART Transmit)            │
│ Pin 6 (GND)         │ GND (Common Ground)           │
└─────────────────────┴───────────────────────────────┘
```

**Important:** TX crosses to RX (TX→RX, RX→TX)

**See [WIRING_GUIDE.md](WIRING_GUIDE.md) for complete wiring instructions**

### Option 1: MAVLink (ArduPilot/PX4)

For ArduPilot or PX4 flight controllers:
- Connect Pi TX/RX to FC TELEM port
- Set `"interface": "mavlink"` in config
- Configure SERIAL2_PROTOCOL=2 on FC

### Option 2: MSP Protocol (Betaflight/iNav)

For Betaflight/iNav flight controllers:
- Connect Pi TX/RX to FC UART port
- Set `"interface": "msp"` in config
- Enable MSP on UART in Betaflight Configurator

### Option 3: PWM Override (Advanced)

- Connect Pi GPIO to FC receiver inputs
- Set `"interface": "pwm"` in config
- Use pigpio library for PWM generation

## Tuning Guide

### Step 1: Verify Camera Optical Flow

1. Start system with logging enabled
2. Manually move drone and observe position tracking
3. Ensure `surface_quality` value stays above 100 for good tracking
4. Camera should have a clear, textured view of the ground

### Step 2: Tune Velocity Damping

1. Start in velocity_damping mode
2. Adjust `velocity_damping` factor (0.1 to 0.5)
3. Higher values = more aggressive damping

### Step 3: Tune Position Hold

1. Start with conservative PID gains
2. Increase Kp until position holds with minimal error
3. Add Kd to reduce oscillations
4. Add small Ki to eliminate steady-state error

### Tuning Tips

- **Too oscillatory?** Decrease Kp, increase Kd
- **Too slow to respond?** Increase Kp
- **Steady-state error?** Increase Ki (but keep small!)
- **Drifting away?** Check camera mounting (must face down) and height setting

## Performance Optimization

### For Raspberry Pi Zero

The Pi Zero is single-core and slower, so:

1. **Reduce update rate**: Try 30-40 Hz instead of 50 Hz
2. **Disable logging**: Reduces CPU and SD card writes
3. **Use lightweight OS**: Raspberry Pi OS Lite (no desktop)
4. **Overclock safely**: Add to `/boot/config.txt`:
   ```
   arm_freq=1000
   over_voltage=2
   ```

### For Raspberry Pi Zero 2 W

The quad-core Zero 2 W can handle:
- 100 Hz update rate
- Real-time logging
- Additional sensor fusion (IMU integration)

## Data Analysis

Flight logs are saved as CSV files with columns:
- `time`: Time in seconds
- `pos_x`, `pos_y`: Position in meters
- `vel_x`, `vel_y`: Velocity in m/s
- `pitch_cmd`, `roll_cmd`: Control outputs in degrees
- `mode`: Current stabilization mode
- `squal`: Surface quality (0-255)

Analyze with Python:

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('flight_log.csv')
plt.plot(df['time'], df['pos_x'], label='X position')
plt.plot(df['time'], df['pos_y'], label='Y position')
plt.legend()
plt.show()
```

## Troubleshooting

### Camera Not Detected

- Verify camera is enabled: `vcgencmd get_camera` (should show supported=1 detected=1)
- Check camera ribbon cable connection
- For USB camera: `ls /dev/video*` should show camera device
- Test camera: `libcamera-still -o test.jpg` or `raspistill -o test.jpg`

### Poor Tracking Quality

- Ensure adequate lighting (avoid direct sunlight)
- Check camera lens is clean
- Verify height setting matches actual flight height
- Ensure ground surface has visible texture (not blank/uniform)
- Surface quality should be >100 for good tracking

### Position Drift

- Verify sensor rotation setting matches physical mounting
- Check for vibrations (dampen sensor mounting)
- Increase velocity damping factor
- Ensure height is set correctly (scales optical flow)

### Control Loop Running Slow

- Reduce update rate in config
- Disable data logging
- Close unnecessary processes
- Consider Pi Zero 2 W for better performance

## System Architecture

```
┌─────────────────────────────────────────────────┐
│          Betafly Stabilization System           │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐         ┌────────▼────────┐
│ Optical Flow   │         │  Stabilization  │
│    Tracking    │         │   Controller    │
│                │         │                 │
│ - PMW3901      │────────▶│ - Position PID  │
│ - Position Est │         │ - Velocity Damp │
│ - Velocity Est │         │ - Mode Control  │
└────────────────┘         └─────────┬───────┘
                                     │
                            ┌────────▼────────┐
                            │ Flight Control  │
                            │   Interface     │
                            │                 │
                            │ - MAVLink / MSP │
                            │ - PWM Output    │
                            └─────────────────┘
```

## API Reference

### OpticalFlowTracker

```python
tracker = OpticalFlowTracker(sensor, scale_factor=0.001, height_m=0.5)
pos_x, pos_y = tracker.update()  # Get current position
vel_x, vel_y = tracker.get_velocity()  # Get velocity
tracker.reset_position()  # Reset to origin
tracker.set_height(new_height)  # Update height
```

### PositionStabilizer

```python
stabilizer = PositionStabilizer(x_gains, y_gains, max_tilt_angle=15.0)
stabilizer.set_target_position(x, y)  # Set target
stabilizer.enable()  # Enable position hold
pitch, roll = stabilizer.update(current_x, current_y)  # Get corrections
```

### StabilizationController

```python
controller = StabilizationController(gains_x, gains_y, damping, max_tilt)
controller.set_mode("position_hold")  # Set mode
pitch, roll = controller.update(x, y, vx, vy)  # Update control
controller.hold_current_position(x, y)  # Hold at position
```

## New Features Documentation

For detailed information about new features:
- **[FEATURES.md](FEATURES.md)** - Complete guide to web interface, camera support, and stick inputs
- **[INSTALL.md](INSTALL.md)** - Installation and setup instructions

## Project Files

### Core System
- `betafly_stabilizer.py` - Basic camera-based control script
- `betafly_stabilizer_advanced.py` - Advanced system with web interface and all features
- `camera_optical_flow.py` - Camera-based optical flow (USB/CSI/Analog)
- `position_stabilizer.py` - PID control and stabilization algorithms
- `stick_input.py` - RC receiver input handling (SBUS/PWM)
- `web_interface.py` - Flask web server and API

### Web Interface
- `templates/index.html` - Web dashboard UI
- `static/css/style.css` - Styling
- `static/js/app.js` - Frontend JavaScript

### Configuration & Setup
- `config.json` - Configuration file with camera and control options
- `setup.sh` - Automated setup script
- `requirements.txt` - Python dependencies (OpenCV, Flask, etc.)

### Testing & Utilities
- `test_sensor.py` - Camera testing utility

### Documentation
- `README.md` - This file (system overview)
- `CAMERA_SETUP.md` - **Camera wiring and setup guide**
- `WIRING_GUIDE.md` - **Pi Zero to flight controller wiring**
- `FEATURES.md` - Detailed feature guide
- `INSTALL.md` - Installation guide

## Contributing

Contributions welcome! Areas for improvement:
- Flight controller integration implementations (MAVLink/MSP)
- Additional camera support and optimization
- Kalman filter for sensor fusion
- Auto-tuning algorithms
- Ground effect compensation
- Improved optical flow algorithms
- Additional web interface features
- Mobile app development

## License

MIT License - See LICENSE file for details

## Safety Warning

⚠️ **IMPORTANT**: This system is experimental. Always:
- Test in a safe environment
- Have manual control override ready
- Start with low gains and gentle movements
- Monitor battery voltage (Pi can brownout)
- Never fly over people or property

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/yourusername/betafly-stabilization/issues
- Documentation: https://github.com/yourusername/betafly-stabilization/wiki

## Credits

Developed for the Betafly drone project using:
- Raspberry Pi Camera modules (IMX219, OV5647)
- Raspberry Pi Zero platform
- OpenCV optical flow algorithms
- PID control theory
- Visual odometry principles

---

**Happy Flying! 🚁**
