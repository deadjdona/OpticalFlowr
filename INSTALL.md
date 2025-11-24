# Installation Guide

## Hardware Setup

### 1. Connect Camera to Raspberry Pi Zero

**For Raspberry Pi Camera (CSI) - Recommended:**

1. Locate the CSI camera connector on Pi Zero (between HDMI ports)
2. Flip up the black latch on the connector
3. Insert camera ribbon cable:
   - Blue side facing USB port
   - Metal contacts facing HDMI ports
4. Push latch down to secure

**Mounting**: Camera must face **downward** with clear view of ground surface.

**For USB Camera:**

1. Connect USB camera to Pi Zero via micro USB OTG adapter
2. Use data port (not power port)

**See [CAMERA_SETUP.md](CAMERA_SETUP.md) for detailed camera wiring and setup.**

### 2. Power Supply

- Raspberry Pi Zero requires stable 5V supply
- Use a BEC (Battery Eliminator Circuit) from drone battery
- Minimum 2A capacity recommended
- Add capacitor (100-470µF) near Pi for stability

## Software Installation

### Quick Install (Recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/betafly-stabilization.git
cd betafly-stabilization

# Run setup script
./setup.sh

# Reboot to enable SPI (if prompted)
sudo reboot
```

### Manual Install

```bash
# 1. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install dependencies
sudo apt-get install -y python3 python3-pip python3-dev git

# 3. Enable Camera interface
sudo raspi-config
# Interface Options -> Camera -> Enable

# 4. Install Python packages
pip3 install -r requirements.txt

# 5. Make scripts executable
chmod +x betafly_stabilizer.py betafly_stabilizer_advanced.py test_sensor.py setup.sh

# 6. Reboot
sudo reboot
```

## Verification

### 1. Test Camera Connection

```bash
# For CSI camera (test with libcamera)
libcamera-still -o test.jpg

# Or with legacy camera stack
raspistill -o test.jpg

# Verify camera is detected
vcgencmd get_camera
# Should output: supported=1 detected=1
```

### 2. Test Python Camera Access

```bash
python3 -c "
from camera_optical_flow import auto_detect_camera
cam_id = auto_detect_camera()
if cam_id is not None:
    print(f'✓ Camera detected at ID: {cam_id}')
else:
    print('✗ No camera detected')
"
```

### 3. Test Optical Flow

```bash
./test_sensor.py --test tracking --duration 10
```

Move the camera (or object below it) and observe optical flow tracking.

## Configuration

### 1. Edit Config File

```bash
nano config.json
```

### 2. Key Settings to Adjust

**Sensor Rotation**: Match physical mounting
```json
"rotation": 0  // 0, 90, 180, or 270 degrees
```

**Flight Height**: Expected altitude above ground
```json
"initial_height": 0.5  // meters
```

**PID Gains**: Start conservative, tune later
```json
"position_x": {
  "kp": 0.5,
  "ki": 0.1,
  "kd": 0.2
}
```

## Running the System

### Manual Start

```bash
# Velocity damping mode (recommended for first flight)
./betafly_stabilizer.py --mode velocity_damping

# Position hold mode
./betafly_stabilizer.py --mode position_hold

# With logging enabled
./betafly_stabilizer.py --mode position_hold --log
```

### Auto-Start on Boot (Optional)

```bash
# Copy service file
sudo cp betafly-stabilizer.service /etc/systemd/system/

# Edit paths in service file if needed
sudo nano /etc/systemd/system/betafly-stabilizer.service

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable betafly-stabilizer.service

# Start service
sudo systemctl start betafly-stabilizer.service

# Check status
sudo systemctl status betafly-stabilizer.service

# View logs
sudo journalctl -u betafly-stabilizer.service -f
```

## Flight Controller Integration

### Wiring: Pi Zero to Flight Controller

Connect via UART (TX/RX):

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

### Enable UART on Pi Zero

```bash
sudo raspi-config
# Interface Options -> Serial Port
# - Login shell over serial: NO
# - Serial port hardware enabled: YES

# Reboot
sudo reboot
```

### Configure Protocol

**For MAVLink (ArduPilot/PX4):**
```json
{
  "output": {
    "interface": "mavlink",
    "port": "/dev/ttyAMA0",
    "baudrate": 115200
  }
}
```

**For MSP (Betaflight/iNav):**
```json
{
  "output": {
    "interface": "msp",
    "port": "/dev/ttyAMA0",
    "baudrate": 115200
  }
}
```

**See [WIRING_GUIDE.md](WIRING_GUIDE.md) for complete wiring instructions and flight controller configuration.**

## Initial Flight Test

### Safety Checklist

- [ ] Sensor securely mounted and facing down
- [ ] All connections secure and insulated
- [ ] Pi powered from stable BEC (not USB)
- [ ] Manual control mode configured as backup
- [ ] Test area is safe and clear
- [ ] Adequate lighting for optical tracking
- [ ] Textured surface below (not uniform/blank)

### Test Procedure

1. **Ground Test**
   ```bash
   ./betafly_stabilizer.py --mode velocity_damping --log
   ```
   - Move drone manually on ground
   - Verify sensor responds correctly
   - Check logs show reasonable values

2. **Hover Test**
   - Start in manual mode
   - Take off and hover at ~0.5m height
   - Enable velocity damping
   - Verify drift reduction

3. **Position Hold Test**
   - Hover stable in velocity damping mode
   - Switch to position hold
   - Release controls
   - Verify drone maintains position

## Troubleshooting

### Camera Not Detected

```bash
# Check camera is enabled
vcgencmd get_camera
# Should show: supported=1 detected=1

# For CSI camera, check connection
# - Ribbon cable fully inserted
# - Blue side facing USB port
# - Metal contacts facing HDMI ports

# For USB camera
ls /dev/video*
# Should show: /dev/video0 or similar

lsusb
# Should show USB camera device
```

### Camera Not Working

```bash
# Test camera capture (CSI)
libcamera-still -o test.jpg
# or
raspistill -o test.jpg

# Test with Python
python3 -c "
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print(f'Camera works: {ret}')
if ret:
    print(f'Resolution: {frame.shape}')
cap.release()
"
```

### Poor Tracking

- Ensure good lighting (avoid direct sunlight)
- Check camera lens is clean
- Verify ground surface has visible texture
- Verify height setting is accurate
- Reduce vibrations (add vibration damping)
- Surface quality should be >100 for good tracking

### Permission Errors

```bash
# Add user to SPI group
sudo usermod -a -G spi,gpio pi

# Make scripts executable
chmod +x *.py *.sh

# Reboot
sudo reboot
```

## Performance Optimization

### For Raspberry Pi Zero

```json
{
  "control": {
    "update_rate_hz": 30  // Reduce from 50
  },
  "logging": {
    "enabled": false  // Disable for production
  }
}
```

Optional overclock (`/boot/config.txt`):
```
arm_freq=1000
over_voltage=2
```

### For Raspberry Pi Zero 2 W

Can handle higher rates:
```json
{
  "control": {
    "update_rate_hz": 100
  }
}
```

## Next Steps

1. ✓ Verify sensor working
2. ✓ Configure for your setup
3. ✓ Ground test tracking
4. → Tune PID gains (see README.md)
5. → Implement flight controller interface
6. → Flight test in safe area

## Support

- Documentation: [README.md](README.md)
- Tuning Guide: See "Tuning Guide" section in README.md
- Issues: Create GitHub issue with logs

## Safety Reminder

⚠️ **Always have manual override ready**
⚠️ **Test in safe, controlled environment**
⚠️ **Monitor battery voltage**
⚠️ **Never fly over people**
