# Wiring Guide: Raspberry Pi Zero to Flight Controller

This guide explains how to wire a Raspberry Pi Zero to your flight controller for position stabilization control.

## Overview

The Raspberry Pi Zero communicates with the flight controller using the **UART serial interface** (TX/RX pins). This allows the Pi to send stabilization commands using protocols like MAVLink (for ArduPilot/PX4) or MSP (for Betaflight/iNav).

---

## Raspberry Pi Zero GPIO Pinout

```
Raspberry Pi Zero W - GPIO Header (40 pins)

        3.3V [ 1] [ 2] 5V
   I2C SDA/GPIO2 [ 3] [ 4] 5V
   I2C SCL/GPIO3 [ 5] [ 6] GND
        GPIO4 [ 7] [ 8] GPIO14 (TXD/UART TX)
          GND [ 9] [10] GPIO15 (RXD/UART RX)
       GPIO17 [11] [12] GPIO18
       GPIO27 [13] [14] GND
       GPIO22 [15] [16] GPIO23
        3.3V [17] [18] GPIO24
 SPI MOSI/GPIO10 [19] [20] GND
 SPI MISO/GPIO9 [21] [22] GPIO25
 SPI SCLK/GPIO11 [23] [24] GPIO8/SPI CE0
          GND [25] [26] GPIO7/SPI CE1
       GPIO0 [27] [28] GPIO1
       GPIO5 [29] [30] GND
       GPIO6 [31] [32] GPIO12
      GPIO13 [33] [34] GND
      GPIO19 [35] [36] GPIO16
      GPIO26 [37] [38] GPIO20
         GND [39] [40] GPIO21

Key Pins for Flight Controller Connection:
- Pin 8:  GPIO14 (UART TX) - Transmit data FROM Pi TO FC
- Pin 10: GPIO15 (UART RX) - Receive data FROM FC TO Pi
- Pin 6:  GND - Common ground (MUST be connected)
```

---

## Basic Wiring Connection

### Minimum Connection (3 wires)

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  Raspberry Pi Zero                   Flight Controller        │
│  ┌──────────────┐                    ┌─────────────────┐      │
│  │              │                    │                 │      │
│  │    [USB]     │                    │                 │      │
│  │              │                    │   ┌─────────┐   │      │
│  │              │                    │   │ UART    │   │      │
│  │  GPIO Header │                    │   │ Port    │   │      │
│  │  ┌────────┐  │                    │   └─────────┘   │      │
│  │  │●●●●●●●│  │                    │    TX  RX  GND   │      │
│  │  │●●●●●●●│  │                    │    │   │   │     │      │
│  │  └────────┘  │                    │    │   │   │     │      │
│  │   TX RX GND  │                    │    │   │   │     │      │
│  │   8  10  6   │                    │    │   │   │     │      │
│  │   │  │   │   │                    │    │   │   │     │      │
│  └───┼──┼───┼───┘                    └────┼───┼───┼─────┘      │
│      │  │   │                             │   │   │            │
│      │  │   └─────────────────────────────┼───┼───┘            │
│      │  └─────────────────────────────────┘   │                │
│      └────────────────────────────────────────┘                │
│      TX crosses to RX (TX->RX, RX->TX)                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Wiring:
┌─────────────────┬──────────────────┬──────────────────────────┐
│ Pi Zero Pin     │ Signal           │ Flight Controller        │
├─────────────────┼──────────────────┼──────────────────────────┤
│ Pin 8 (GPIO14)  │ TX (Transmit)    │ RX (Receive) on UART port│
│ Pin 10 (GPIO15) │ RX (Receive)     │ TX (Transmit) on UART port│
│ Pin 6           │ GND (Ground)     │ GND (Ground)             │
└─────────────────┴──────────────────┴──────────────────────────┘

IMPORTANT:
- TX from Pi connects to RX on Flight Controller
- RX from Pi connects to TX on Flight Controller
- GND MUST be connected for common reference
```

### Recommended Connection (4 wires)

Add a 5V power connection to power the Pi from the flight controller's BEC:

```
┌─────────────────┬──────────────────┬──────────────────────────┐
│ Pi Zero Pin     │ Signal           │ Flight Controller        │
├─────────────────┼──────────────────┼──────────────────────────┤
│ Pin 8 (GPIO14)  │ TX (Transmit)    │ RX on UART port          │
│ Pin 10 (GPIO15) │ RX (Receive)     │ TX on UART port          │
│ Pin 6           │ GND (Ground)     │ GND                      │
│ Pin 2 or 4      │ 5V (Power)       │ 5V BEC output            │
└─────────────────┴──────────────────┴──────────────────────────┘

Note: 5V power connection is optional. You can also power the Pi
      separately via its micro USB power port.
```

---

## Flight Controller Specific Wiring

### Option 1: Betaflight / iNav Flight Controllers

Most F4/F7/H7 flight controllers have multiple UART ports.

#### Example: Standard F4 Flight Controller

```
┌──────────────────────────────────────────────────────────┐
│ Flight Controller (Top View)                             │
│                                                           │
│  [Motor Pads]                    [UART Ports]            │
│                                                           │
│                                  ┌─────────────────┐     │
│  [M1] [M2] [M3] [M4]             │ UART3           │     │
│                                  │ TX3 RX3 GND 5V  │     │
│                                  │  │   │   │   │  │     │
│                                  └──┼───┼───┼───┼──┘     │
│                                     │   │   │   │        │
│  [USB]                              │   │   │   │        │
│                                     │   │   │   │        │
└─────────────────────────────────────┼───┼───┼───┼────────┘
                                      │   │   │   │
                                      │   │   │   │
            ┌─────────────────────────┘   │   │   └──────────┐
            │                             │   │              │
            │  ┌──────────────────────────┘   │              │
            │  │                              │              │
            │  │  ┌───────────────────────────┘              │
            │  │  │                                          │
            ↓  ↓  ↓  ↓                                       │
      ┌────────────────┐                                    │
      │ Raspberry Pi   │                                    │
      │ Zero W         │                                    │
      │  RX TX GND 5V  │                                    │
      │  10  8  6   2  │                                    │
      └────────────────┘                                    │
```

**Wiring Table:**
```
┌─────────────────────┬───────────────────────────────────┐
│ Pi Zero             │ Flight Controller UART3           │
├─────────────────────┼───────────────────────────────────┤
│ Pin 8 (TX/GPIO14)   │ RX3 (Receive on UART3)            │
│ Pin 10 (RX/GPIO15)  │ TX3 (Transmit on UART3)           │
│ Pin 6 (GND)         │ GND                               │
│ Pin 2 (5V) optional │ 5V (from BEC)                     │
└─────────────────────┴───────────────────────────────────┘
```

#### Betaflight Configuration

1. **Enable UART:**
   - Connect to Betaflight Configurator
   - Go to **Ports** tab
   - Find UART3 (or whichever UART you used)
   - Enable **MSP** on that UART
   - Set baud rate: **115200**
   - Save and reboot

2. **Configure MSP:**
   ```
   In CLI:
   set msp_override_channels_mask = 0
   save
   ```

---

### Option 2: ArduPilot / PX4 Flight Controllers

ArduPilot/PX4 use MAVLink protocol instead of MSP.

#### Example: Pixhawk-style Flight Controller

```
┌───────────────────────────────────────────────────────────┐
│ Pixhawk Flight Controller                                 │
│                                                            │
│  [Main Out]    [AUX Out]                                  │
│                                                            │
│  ┌─────────────────────┐                                  │
│  │ TELEM 2 Port        │                                  │
│  │ TX  RX  CTS RTS 5V GND                                │
│  │  │   │   │   │  │  │ │                                │
│  └──┼───┼───┼───┼──┼──┼─┘                                │
│     │   │   │   │  │  │                                   │
│     │   │   │   │  │  │   [USB]                          │
│     │   │   │   │  │  │                                   │
└─────┼───┼───┼───┼──┼──┼───────────────────────────────────┘
      │   │   X   X  │  │
      │   │          │  │
      │   │          │  │
      ↓   ↓          ↓  ↓
┌────────────────────────┐
│ Raspberry Pi Zero      │
│  RX  TX       5V  GND  │
│  10   8        2   6   │
└────────────────────────┘

Note: CTS/RTS (flow control) are not needed for basic operation
```

**Wiring Table:**
```
┌─────────────────────┬───────────────────────────────────┐
│ Pi Zero             │ Pixhawk TELEM 2                   │
├─────────────────────┼───────────────────────────────────┤
│ Pin 8 (TX/GPIO14)   │ RX (Receive)                      │
│ Pin 10 (RX/GPIO15)  │ TX (Transmit)                     │
│ Pin 6 (GND)         │ GND                               │
│ Pin 2 (5V) optional │ 5V                                │
└─────────────────────┴───────────────────────────────────┘
```

#### ArduPilot Configuration

1. **Set Serial Port:**
   - Connect with Mission Planner or QGroundControl
   - Go to **Config → Parameters**
   - Set `SERIAL2_PROTOCOL = 2` (MAVLink 2)
   - Set `SERIAL2_BAUD = 115` (115200 baud)
   - Save parameters

2. **Enable Companion Computer:**
   - Set `SYSID_MYGCS = 1`
   - Set `SR2_EXTRA1 = 10` (stream rate)
   - Set `SR2_POSITION = 10`
   - Reboot flight controller

---

## Detailed Connection Steps

### Step 1: Identify UART Pads/Pins on Flight Controller

Flight controllers have UART connections in different forms:

**Pad-style (requires soldering):**
```
┌────────────────────┐
│ Flight Controller  │
│                    │
│ ○ ○ ○ ○           │
│ T R G 5           │
│ X X N V           │
│ 3 3 D             │
└────────────────────┘
```

**Through-hole pins:**
```
┌────────────────────┐
│ Flight Controller  │
│                    │
│ [●][●][●][●]      │
│  TX RX GND 5V      │
└────────────────────┘
```

**JST connector:**
```
┌────────────────────┐
│ Flight Controller  │
│  ┌──────────┐      │
│  │ UART 3   │      │
│  │  ┌────┐  │      │
│  └──┘    └──┘      │
└────────────────────┘
```

### Step 2: Prepare Wires

**Required Materials:**
- 22-26 AWG silicone wire (flexible)
- 4 wires minimum (TX, RX, GND, optionally 5V)
- Dupont connectors (female) for Pi Zero
- Solder and soldering iron (if soldering to FC pads)

**Wire Colors (Suggested):**
- Yellow or White: TX
- Orange or Green: RX
- Black or Brown: GND
- Red: 5V (power)

### Step 3: Soldering to Flight Controller (if needed)

If your FC has pads instead of pins:

1. **Prepare the pad:**
   - Clean the pad with isopropyl alcohol
   - Apply a small amount of solder to the pad (tinning)

2. **Prepare the wire:**
   - Strip 2-3mm of insulation
   - Tin the wire end with solder

3. **Solder wire to pad:**
   - Hold wire to pad with tweezers
   - Heat pad and wire together
   - Let solder flow to join them
   - Remove iron and let cool
   - Verify good connection (gentle tug test)

4. **Secure wires:**
   - Use hot glue or tape to relieve strain
   - Ensure wires won't pull off pads during vibration

### Step 4: Connect to Raspberry Pi Zero

1. **Attach Dupont Connectors:**
   - Female dupont connectors fit directly onto Pi GPIO pins
   - Make sure they're secure

2. **Connect Wires:**
   ```
   FC TX  → Pi Pin 10 (RX)
   FC RX  → Pi Pin 8  (TX)
   FC GND → Pi Pin 6  (GND)
   FC 5V  → Pi Pin 2  (5V) - optional
   ```

3. **Double Check:**
   - **TX crosses to RX** (TX→RX, RX→TX)
   - GND is connected
   - No shorts between pins

### Step 5: Enable UART on Raspberry Pi

```bash
# Disable serial console (frees up UART for data)
sudo raspi-config

# Navigate to:
# 3. Interface Options
#    → I6 Serial Port
#    → Login shell over serial: NO
#    → Serial port hardware enabled: YES
#    → Finish

# Alternatively, edit /boot/config.txt and /boot/cmdline.txt manually
```

Edit `/boot/config.txt`:
```bash
sudo nano /boot/config.txt

# Add or uncomment:
enable_uart=1
```

Edit `/boot/cmdline.txt`:
```bash
sudo nano /boot/cmdline.txt

# Remove any console=serial0,115200 or console=ttyAMA0,115200
# Example line should look like:
console=tty1 root=PARTUUID=... rootfstype=ext4 ...
```

Reboot:
```bash
sudo reboot
```

### Step 6: Test Connection

```bash
# Check serial port exists
ls -l /dev/ttyAMA0
# or
ls -l /dev/serial0

# Test serial communication (optional)
# Install minicom
sudo apt-get install minicom

# Open serial port (115200 baud, 8N1)
minicom -D /dev/ttyAMA0 -b 115200

# You should see MAVLink or MSP messages
# Press Ctrl+A, then X to exit
```

---

## Power Considerations

### Option 1: Separate Power (Recommended for Development)

Power the Pi Zero via its micro USB port:

**Advantages:**
- ✅ Simple troubleshooting
- ✅ No risk of voltage issues
- ✅ Can power Pi independently

**Disadvantages:**
- ❌ Requires separate power source
- ❌ Extra cable

```
┌────────────────────────────────────────┐
│                                        │
│  USB Power    ┌──────────────┐        │
│  Adapter ─────│ Pi Zero      │        │
│  (5V 2A)      │   [USB PWR]  │        │
│               └──────────────┘        │
│                      │                │
│                      │ TX/RX/GND only │
│                      ↓                │
│               ┌──────────────┐        │
│               │ Flight       │        │
│               │ Controller   │        │
│               └──────────────┘        │
│                      ↓                │
│               Drone Battery           │
└────────────────────────────────────────┘
```

### Option 2: Power from Flight Controller BEC

Power the Pi from the flight controller's 5V BEC output:

**Advantages:**
- ✅ Single power source (drone battery)
- ✅ Clean installation
- ✅ No extra cables

**Disadvantages:**
- ❌ BEC must provide enough current (2A+ recommended)
- ❌ Voltage drops can cause Pi brownouts
- ❌ Pi draws power from drone battery

**Requirements:**
- BEC must provide **stable 5V**
- BEC must handle **2A minimum** (3A recommended)
- Add 470µF-1000µF capacitor near Pi for stability

```
┌────────────────────────────────────────┐
│                                        │
│              ┌──────────────┐          │
│         5V───│ Pi Zero      │          │
│        GND───│   GPIO       │          │
│      TX/RX───│   Header     │          │
│              └──────────────┘          │
│                      │                │
│                      ↓                │
│               ┌──────────────┐        │
│               │ Flight       │        │
│               │ Controller   │        │
│               │              │        │
│               │ 5V BEC       │        │
│               └──────┬───────┘        │
│                      │                │
│                      ↓                │
│              Drone Battery (2S-6S)    │
│                  LiPo                 │
└────────────────────────────────────────┘

Add capacitor near Pi:
┌──────────────┐
│ Pi Zero 5V   │
│   Pin 2 ─┬─  │
│          │   │
│        ═════ │  470µF-1000µF capacitor
│          │   │  (electrolytic)
│   Pin 6 ─┴─  │
│ (GND)        │
└──────────────┘
```

---

## Configuration in Software

### Update config.json

```json
{
  "output": {
    "interface": "mavlink",
    "port": "/dev/ttyAMA0",
    "baudrate": 115200
  }
}
```

**Interface Options:**
- `"mavlink"` - For ArduPilot / PX4
- `"msp"` - For Betaflight / iNav
- `"pwm"` - For PWM output (advanced)

**Serial Port:**
- `/dev/ttyAMA0` - Primary UART on Pi Zero
- `/dev/serial0` - Alias to primary UART

**Baud Rate:**
- `115200` - Standard for MAVLink and MSP
- `57600` - Alternative for older systems

---

## Verification Checklist

Before first flight test:

- [ ] TX/RX connections crossed correctly (TX→RX, RX→TX)
- [ ] GND connected between Pi and FC
- [ ] UART enabled on Raspberry Pi (serial console disabled)
- [ ] UART enabled on Flight Controller
- [ ] Correct baud rate set (115200)
- [ ] Wires secured and won't vibrate loose
- [ ] Power supply stable (capacitor added if using FC BEC)
- [ ] Serial port accessible: `ls /dev/ttyAMA0`
- [ ] No shorts between TX/RX/5V pins
- [ ] Proper protocol selected (MAVLink or MSP)

---

## Troubleshooting

### No Data on Serial Port

**Check:**
```bash
# Verify UART is enabled
ls /dev/ttyAMA0

# Check for serial console (should be disabled)
cat /boot/cmdline.txt | grep console

# Test with minicom
minicom -D /dev/ttyAMA0 -b 115200
```

**Solutions:**
1. Disable serial console in raspi-config
2. Check wiring (TX↔RX crossed?)
3. Verify GND connection
4. Check baud rate matches on both sides

### Pi Not Booting When Powered from FC

**Causes:**
- Insufficient current from BEC
- Voltage drop under load
- Poor connections

**Solutions:**
1. Add large capacitor (1000µF) near Pi 5V input
2. Use thicker power wires (20-22 AWG)
3. Verify BEC can provide 2A+
4. Power Pi separately during testing

### FC Not Responding to Pi Commands

**Check:**
1. Correct protocol configured (MAVLink vs MSP)
2. Flight controller firmware up to date
3. UART port enabled in FC configuration
4. Baud rate matches
5. System ID configured correctly (for MAVLink)

### Data Corruption / Garbled Messages

**Causes:**
- EMI (electromagnetic interference) from motors/ESCs
- Baud rate mismatch
- Poor connections

**Solutions:**
1. Twist TX/RX wires together
2. Route signal wires away from motor wires
3. Add ferrite beads on wires
4. Shorten wire length
5. Use shielded cable

---

## Advanced: PWM Output (Alternative to Serial)

Instead of serial communication, you can output PWM signals to override RC receiver inputs. This requires pigpio library.

```bash
sudo apt-get install pigpio python3-pigpio
```

Connect PWM outputs to FC receiver inputs:
```
┌─────────────────────┬───────────────────────────────────┐
│ Pi Zero GPIO        │ Flight Controller Receiver Input  │
├─────────────────────┼───────────────────────────────────┤
│ GPIO 17 (Pin 11)    │ CH1 (Roll)                        │
│ GPIO 18 (Pin 12)    │ CH2 (Pitch)                       │
│ GPIO 22 (Pin 15)    │ CH3 (Throttle)                    │
│ GPIO 23 (Pin 16)    │ CH4 (Yaw)                         │
│ GND (Pin 6)         │ GND                               │
└─────────────────────┴───────────────────────────────────┘
```

Configure in config.json:
```json
{
  "output": {
    "interface": "pwm"
  }
}
```

---

## Complete Wiring Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                  Complete System Wiring                          │
│                                                                  │
│  Camera               Pi Zero W           Flight Controller     │
│  ┌────────┐           ┌──────────┐        ┌─────────────┐      │
│  │        │  Ribbon   │          │ Serial │             │      │
│  │ IMX219 │═══════════│   CSI    │────────│   UART      │      │
│  │        │  Cable    │          │ TX/RX  │             │      │
│  └────────┘           │          │ GND    │             │      │
│    ↓ (facing          │  GPIO    │        │             │      │
│       down)           │  Header  │        │   Motors    │      │
│                       │          │        │   [M1][M2]  │      │
│                       │  5V  ────────────── 5V BEC      │      │
│                       │  GND ────────────── GND         │      │
│                       │          │        │   [M3][M4]  │      │
│  USB Power            │  [USB]   │        │             │      │
│  (Optional)───────────│  PWR     │        └─────────────┘      │
│                       └──────────┘              ↓              │
│                                          Drone Battery          │
│                                          (2S-6S LiPo)           │
│                                                                 │
└──────────────────────────────────────────────────────────────────┘

Signal Flow:
1. Camera captures ground images
2. Pi Zero processes optical flow
3. Pi calculates position corrections
4. Pi sends commands to FC via UART
5. FC adjusts motors for stabilization
```

---

## Next Steps

1. ✅ Hardware wired correctly
2. ✅ UART enabled and configured
3. → Test serial communication
4. → Implement MAVLink/MSP protocol in code
5. → Ground test with FC in bench mode
6. → Flight test in safe area

---

## Safety Notes

⚠️ **Before First Flight:**
- Verify all connections are secure
- Test on ground with propellers OFF
- Have manual control override ready
- Start with low gains in config
- Test in open area away from people

⚠️ **Electrical Safety:**
- Never connect/disconnect while powered
- Verify voltage before connecting (5V only)
- Watch for shorts and exposed wires
- Use heat shrink or tape on all connections

---

## Additional Resources

- [MAVLink Documentation](https://mavlink.io/)
- [MSP Protocol Specification](https://github.com/iNavFlight/inav/wiki/MSP-V2)
- [Betaflight UART Configuration](https://betaflight.com/docs/wiki/guides/current/uart-setup)
- [ArduPilot Companion Computer Guide](https://ardupilot.org/dev/docs/companion-computers.html)

---

For camera setup, see `CAMERA_SETUP.md`  
For system configuration, see `README.md`
