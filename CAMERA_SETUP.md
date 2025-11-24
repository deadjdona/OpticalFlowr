# Camera Setup Guide

This guide covers how to set up and use Raspberry Pi cameras or analog FPV cameras with the Betafly position stabilization system.

## Supported Camera Types

### 1. Raspberry Pi Camera Module (CSI) - **Recommended** ⭐

Supported sensors:
- **IMX219** - 8MP sensor (Raspberry Pi Camera Module V2)
- **OV5647** - 5MP sensor (Raspberry Pi Camera Module V1)
- **IMX477** - 12MP sensor (Raspberry Pi HQ Camera)
- **IMX708** - 12MP sensor (Raspberry Pi Camera Module V3)

**Advantages:**
- ✅ Direct connection via CSI interface (no USB needed)
- ✅ Low latency
- ✅ Low power consumption
- ✅ Compact size
- ✅ Better integration with Raspberry Pi
- ✅ High frame rates possible (up to 90fps at lower resolutions)

### 2. USB Webcam

Standard USB webcams for testing and development.

**Advantages:**
- ✅ Easy to connect and test
- ✅ Wide availability
- ✅ Good for prototyping

**Disadvantages:**
- ❌ Higher power consumption
- ❌ Uses USB port
- ❌ Typically lower frame rates

### 3. Analog FPV Camera via USB Capture Card

Use existing analog FPV cameras through a USB video capture dongle.

**Advantages:**
- ✅ Use existing FPV camera
- ✅ Wide field of view
- ✅ Works in various lighting conditions

**Disadvantages:**
- ❌ Requires USB capture card
- ❌ Potential latency from capture device
- ❌ May have interlacing artifacts

---

## Hardware Setup

### Option 1: Raspberry Pi Camera Module (CSI) - Recommended

#### Required Hardware
- Raspberry Pi Zero W or Zero 2 W
- Raspberry Pi Camera Module (IMX219, OV5647, or similar)
- Camera cable for Pi Zero (shorter, narrower connector)

#### Physical Installation

1. **Locate the CSI Camera Connector**
   - On Raspberry Pi Zero, the CSI connector is between the mini-HDMI ports
   - It's a small black connector with a flip-up latch

2. **Insert the Camera Cable**
   ```
   ┌─────────────────────────────────────┐
   │  Raspberry Pi Zero W                │
   │                                     │
   │   ┌──────┐  ┌─────────┐  ┌──────┐  │
   │   │ HDMI │  │  CSI    │  │ USB  │  │
   │   │      │  │  Port   │  │      │  │
   │   └──────┘  └─────────┘  └──────┘  │
   │              ↑ Camera                │
   │              ↑ cable here            │
   └─────────────────────────────────────┘
   ```

3. **Cable Connection Steps**
   - Gently pull up the black latch on the CSI connector
   - Insert the camera cable with the **blue side facing the USB port**
   - The metal contacts should face **towards the HDMI ports**
   - Push the latch down to secure the cable
   - Ensure the cable is fully inserted and straight

4. **Camera Module Orientation**
   - Mount the camera facing **downward** for optical flow
   - Ensure clear view of the ground
   - Recommended height: 0.5-2.0 meters above ground
   - Avoid mounting near vibration sources

#### Camera Cable Wiring Diagram

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Camera Module                Raspberry Pi Zero        │
│  ┌───────────┐                                         │
│  │           │                                         │
│  │  IMX219   │                                         │
│  │  OV5647   │               ┌──────────────────┐     │
│  │           │               │                  │     │
│  │    [●]    │  Ribbon       │    ┌──────────┐  │     │
│  │           │  Cable        │    │   CSI    │  │     │
│  └─────┬─────┘  ═══════════════▶  │   Port   │  │     │
│        │         15-pin             └──────────┘  │     │
│        │         Flex Cable                       │     │
│        │                                          │     │
│   Camera Lens                    Pi Zero W        │     │
│   (facing down)                                    │     │
│                                                    │     │
└────────────────────────────────────────────────────────┘

Cable Orientation:
- Blue side of cable faces USB port on Pi Zero
- Metal contacts face HDMI ports
- Cable should be straight and fully inserted
```

#### Enable Camera Interface

```bash
# Enable camera interface
sudo raspi-config

# Navigate to:
# 3. Interface Options
#    → I1 Legacy Camera (for older Pi OS)
#    OR
#    → P1 Camera (for newer Pi OS)
#    → Enable

# Reboot
sudo reboot
```

#### Test Camera

```bash
# For legacy camera stack (older Pi OS)
raspistill -o test.jpg

# For libcamera (newer Pi OS - Bullseye or later)
libcamera-still -o test.jpg

# View the image
# Transfer test.jpg to your computer to verify camera works
```

---

### Option 2: USB Webcam

#### Required Hardware
- Raspberry Pi Zero W or Zero 2 W
- USB webcam
- Micro USB to USB-A adapter (OTG adapter)

#### Connection Diagram

```
┌────────────────────────────────────────────┐
│                                            │
│  USB Webcam                                │
│  ┌──────────┐                              │
│  │          │                              │
│  │  Camera  │                              │
│  │          │                              │
│  │   [●]    │                              │
│  └────┬─────┘                              │
│       │ USB Cable                          │
│       │                                    │
│       ↓                                    │
│  ┌────────────┐   Micro USB Cable         │
│  │ USB-A to   │                            │
│  │ Micro USB  │   ┌──────────────────┐    │
│  │ OTG Adapter│───│  Raspberry Pi    │    │
│  └────────────┘   │  Zero W          │    │
│                   │                  │    │
│                   │  [USB Port]      │    │
│                   └──────────────────┘    │
│                                            │
└────────────────────────────────────────────┘

Note: Pi Zero has only one micro USB port for data.
Make sure to use the data port, not the power port.
```

#### Test USB Camera

```bash
# List video devices
ls /dev/video*

# Should show: /dev/video0 (or similar)

# Test with Python
python3 << EOF
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
if ret:
    print(f"Camera works! Resolution: {frame.shape}")
    cv2.imwrite('test.jpg', frame)
else:
    print("Camera failed!")
cap.release()
EOF
```

---

### Option 3: Analog FPV Camera via USB Capture Card

#### Required Hardware
- Raspberry Pi Zero W or Zero 2 W
- Analog FPV camera (any standard FPV cam)
- USB video capture card (EasyCap, Elgato, or generic)
- Micro USB to USB-A adapter (OTG adapter)
- Power supply for FPV camera (usually 5V from drone battery via BEC)

#### Connection Diagram

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  Analog FPV Camera                                   │
│  ┌──────────────┐                                    │
│  │              │                                    │
│  │   Camera     │                                    │
│  │    [●]       │                                    │
│  └──────┬───────┘                                    │
│         │                                            │
│         │ Video Cable (usually yellow RCA)           │
│         │ + Power (red/black wires)                  │
│         ↓                                            │
│  ┌──────────────────┐                                │
│  │  USB Video       │                                │
│  │  Capture Card    │                                │
│  │  (EasyCap/etc)   │                                │
│  │                  │                                │
│  │ [Video In] [USB] │                                │
│  └──────────┬───────┘                                │
│             │ USB Cable                              │
│             ↓                                        │
│  ┌────────────────┐                                  │
│  │ USB OTG        │   Micro USB Cable                │
│  │ Adapter        │───┐                              │
│  └────────────────┘   │  ┌──────────────────┐       │
│                       └──│  Raspberry Pi    │       │
│                          │  Zero W          │       │
│  Camera Power:           │                  │       │
│  ┌────────────┐          │  [USB Port]      │       │
│  │ 5V BEC     │──────────│                  │       │
│  │ from drone │          └──────────────────┘       │
│  └────────────┘                                      │
│                                                      │
└──────────────────────────────────────────────────────┘

Power Wiring for FPV Camera:
┌────────────────────────────────┐
│ FPV Camera                     │
│  Red wire (+5V) ────────┐      │
│  Black wire (GND) ───┐  │      │
│                      │  │      │
│                      ↓  ↓      │
│                   ┌────────┐   │
│                   │  BEC   │   │
│                   │  5V    │   │
│                   └───┬────┘   │
│                       │        │
│                       ↓        │
│                  Drone Battery │
│                  (2S-6S LiPo)  │
└────────────────────────────────┘
```

#### Recommended USB Capture Cards

1. **EasyCap DC60** - Budget option, works well
2. **Generic USB 2.0 capture dongle** - Widely available
3. **Elgato Cam Link 4K** - High quality, more expensive

#### Test Analog Camera

```bash
# List video devices
v4l2-ctl --list-devices

# Test capture
python3 << EOF
import cv2
cap = cv2.VideoCapture('/dev/video0')
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 720)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
ret, frame = cap.read()
if ret:
    print(f"Analog camera works! Resolution: {frame.shape}")
    cv2.imwrite('test.jpg', frame)
else:
    print("Camera failed!")
cap.release()
EOF
```

---

## Software Configuration

### Configuration File Setup

Edit `config.json` to select your camera type:

#### For Raspberry Pi Camera (CSI)

```json
{
  "sensor": {
    "type": "csi_camera",
    "rotation": 0
  },
  "camera": {
    "device": 0,
    "width": 640,
    "height": 480,
    "fps": 30,
    "method": "farneback"
  }
}
```

#### For USB Webcam

```json
{
  "sensor": {
    "type": "usb_camera",
    "rotation": 0
  },
  "camera": {
    "device": 0,
    "width": 640,
    "height": 480,
    "fps": 30,
    "method": "farneback"
  }
}
```

#### For Analog Camera via USB

```json
{
  "sensor": {
    "type": "analog_usb",
    "rotation": 0
  },
  "camera": {
    "device": "/dev/video0",
    "width": 720,
    "height": 480,
    "fps": 30,
    "method": "farneback",
    "deinterlace": true
  }
}
```

### Optical Flow Methods

Two methods are available:

**Farneback (Dense Optical Flow)** - Recommended
- More accurate
- Better for textured surfaces
- Slower computation
- Good for Pi Zero 2 W and higher

**Lucas-Kanade (Sparse Optical Flow)**
- Faster computation
- Tracks feature points
- Good for Pi Zero (original)
- Better for high-contrast scenes

Change in config:
```json
{
  "camera": {
    "method": "farneback"  // or "lucas_kanade"
  }
}
```

---

## Performance Tuning

### For Raspberry Pi Zero (Single Core)

Use lower resolution and simpler optical flow:

```json
{
  "camera": {
    "width": 320,
    "height": 240,
    "fps": 30,
    "method": "lucas_kanade"
  },
  "control": {
    "update_rate_hz": 30
  }
}
```

### For Raspberry Pi Zero 2 W (Quad Core)

Can handle higher resolution and better optical flow:

```json
{
  "camera": {
    "width": 640,
    "height": 480,
    "fps": 30,
    "method": "farneback"
  },
  "control": {
    "update_rate_hz": 50
  }
}
```

### For Raspberry Pi 4 or 5

Maximum performance:

```json
{
  "camera": {
    "width": 640,
    "height": 480,
    "fps": 60,
    "method": "farneback"
  },
  "control": {
    "update_rate_hz": 100
  }
}
```

---

## Camera Mounting Guidelines

### Position and Orientation

1. **Downward Facing**
   - Camera must face directly downward
   - Clear view of ground surface
   - No obstructions (landing gear, etc.)

2. **Height Above Ground**
   - Optimal: 0.5-2.0 meters
   - Update `initial_height` in config.json to match
   - Too low: Limited range of motion tracking
   - Too high: Reduced tracking accuracy

3. **Field of View**
   - Wider FOV better for tracking
   - Typical: 60-160 degrees
   - FPV cameras usually have good wide FOV

4. **Vibration Isolation**
   - Mount camera on vibration dampening material
   - Foam padding or rubber grommets
   - Vibration degrades optical flow quality

### Lighting Considerations

1. **Best Conditions**
   - Uniform, diffuse lighting
   - Avoid direct sunlight
   - Indoor: standard lighting is fine
   - Outdoor: Overcast days are ideal

2. **Challenging Conditions**
   - Direct sunlight (causes shadows and glare)
   - Very low light (reduced contrast)
   - Rapidly changing lighting

3. **Solutions**
   - Add IR LEDs for night flying
   - Use camera with good low-light performance
   - Adjust camera exposure settings

### Surface Requirements

The ground surface needs **visible texture** for optical flow:

**Good Surfaces:**
- ✅ Grass
- ✅ Textured concrete
- ✅ Patterned flooring
- ✅ Carpets
- ✅ Dirt/gravel

**Poor Surfaces:**
- ❌ Blank white floors
- ❌ Still water
- ❌ Uniform surfaces
- ❌ Highly reflective surfaces

---

## Testing Your Setup

### 1. Basic Camera Test

```bash
# Run camera test
python3 -c "
from camera_optical_flow import auto_detect_camera, CameraOpticalFlow
import time

camera_id = auto_detect_camera()
if camera_id is not None:
    print(f'Camera detected at ID: {camera_id}')
    cam = CameraOpticalFlow(camera_id)
    cam.start()
    time.sleep(2)
    
    motion = cam.get_motion()
    quality = cam.get_surface_quality()
    
    print(f'Motion: {motion}')
    print(f'Surface quality: {quality}')
    
    cam.stop()
    print('Test completed successfully!')
else:
    print('No camera detected!')
"
```

### 2. Run Stabilizer Test

```bash
# Start stabilizer with logging
./betafly_stabilizer.py --config config.json --log --mode velocity_damping

# Move the drone manually on ground
# Check that position values change in console output
```

### 3. Check Surface Quality

Surface quality should be:
- **>100**: Good tracking
- **50-100**: Acceptable
- **<50**: Poor surface, tracking may be unreliable

---

## Troubleshooting

### Camera Not Detected

```bash
# For CSI camera
sudo raspi-config  # Enable camera interface

# Check camera is recognized
vcgencmd get_camera

# Should output: supported=1 detected=1

# For USB camera
lsusb  # Should show USB camera device
ls /dev/video*  # Should show /dev/video0
```

### Poor Optical Flow Quality

**Symptoms:** Erratic position tracking, low surface quality values

**Solutions:**
1. Improve lighting conditions
2. Ensure textured surface below camera
3. Reduce vibration
4. Lower flight height
5. Clean camera lens
6. Adjust exposure settings

### Low Frame Rate / High CPU Usage

**Solutions:**
1. Reduce resolution (320x240)
2. Use Lucas-Kanade method instead of Farneback
3. Reduce control loop rate
4. Disable unnecessary processes
5. Consider upgrading to Pi Zero 2 W

### Camera Image Quality Issues

**For CSI Camera:**
```bash
# Adjust camera settings
# Create /boot/config.txt additions:

# Disable camera LED
disable_camera_led=1

# Adjust camera parameters (optional)
awb_auto_is_greyworld=1
```

**For USB/Analog Camera:**
```bash
# Install v4l-utils to adjust camera
sudo apt-get install v4l-utils

# List camera controls
v4l2-ctl -d /dev/video0 --list-ctrls

# Adjust brightness, contrast, etc.
v4l2-ctl -d /dev/video0 --set-ctrl=brightness=128
v4l2-ctl -d /dev/video0 --set-ctrl=contrast=32
```

---

## Recommended Camera Models

### Raspberry Pi CSI Cameras

| Model | Sensor | Resolution | FOV | Notes |
|-------|--------|------------|-----|-------|
| **Pi Camera V2** | IMX219 | 8MP | 62° | Best value ⭐ |
| Pi Camera V1 | OV5647 | 5MP | 54° | Still works well |
| Pi Camera V3 | IMX708 | 12MP | 66° | Newer, better low light |
| Pi HQ Camera | IMX477 | 12MP | Lens-dependent | High quality, expensive |
| Pi Camera V3 Wide | IMX708 | 12MP | 102° | Wide FOV, great for tracking |

**Recommendation:** Pi Camera V2 (IMX219) or V3 Wide offer the best balance of performance, price, and availability.

### USB Webcams

- Logitech C270 - Budget, works well
- Logitech C920 - Higher quality
- Generic USB cameras - Many work fine

### Analog FPV Cameras

Most analog FPV cameras work well:
- Caddx Ratel 2
- Foxeer Razer Mini
- RunCam Swift
- Any NTSC/PAL camera with standard video output

---

## Next Steps

1. ✅ Hardware connected and tested
2. ✅ Camera configuration set
3. → Test optical flow tracking
4. → Tune PID parameters (see README.md)
5. → Wire to flight controller (see WIRING_GUIDE.md)
6. → First flight test

---

## Additional Resources

- [Official Raspberry Pi Camera Documentation](https://www.raspberrypi.com/documentation/accessories/camera.html)
- [OpenCV Optical Flow Documentation](https://docs.opencv.org/master/d4/dee/tutorial_optical_flow.html)
- See `README.md` for system overview
- See `WIRING_GUIDE.md` for flight controller connection

---

**Safety Reminder:** Always test in a controlled environment before actual flight!
