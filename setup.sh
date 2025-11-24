#!/bin/bash

# Betafly Optical Stabilization System - Setup Script
# This script installs all required dependencies for Raspberry Pi Zero/Zero 2

set -e  # Exit on error

echo "========================================="
echo "Betafly Optical Stabilization Setup"
echo "========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running on Raspberry Pi
check_raspberry_pi() {
    if [ -f /proc/cpuinfo ]; then
        if grep -q "Raspberry Pi" /proc/cpuinfo || grep -q "BCM" /proc/cpuinfo; then
            print_status "Raspberry Pi detected"
            return 0
        fi
    fi
    print_warning "Not running on Raspberry Pi - some features may not work"
    return 1
}

# Update system
update_system() {
    print_status "Updating system packages..."
    sudo apt-get update
    sudo apt-get upgrade -y
}

# Install system dependencies
install_system_deps() {
    print_status "Installing system dependencies..."
    
    # Core dependencies
    sudo apt-get install -y \
        python3-pip \
        python3-dev \
        python3-venv \
        git \
        cmake \
        build-essential \
        pkg-config
        
    # OpenCV dependencies
    sudo apt-get install -y \
        libjpeg-dev \
        libtiff5-dev \
        libpng-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libv4l-dev \
        libxvidcore-dev \
        libx264-dev \
        libgtk-3-dev \
        libatlas-base-dev \
        gfortran
        
    # Camera dependencies
    sudo apt-get install -y \
        libcamera-dev \
        libcamera-tools \
        python3-libcamera \
        python3-kms++ \
        python3-pyqt5 \
        python3-prctl \
        libatlas-base-dev \
        ffmpeg \
        libopenjp2-7 \
        python3-picamera2
        
    # Hardware control
    sudo apt-get install -y \
        pigpio \
        python3-pigpio \
        i2c-tools \
        python3-smbus
}

# Enable hardware interfaces
enable_hardware() {
    print_status "Enabling hardware interfaces..."
    
    # Enable camera
    if ! grep -q "^camera_auto_detect=1" /boot/config.txt; then
        echo "camera_auto_detect=1" | sudo tee -a /boot/config.txt
        print_status "Camera interface enabled"
    fi
    
    # Enable I2C
    if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
        echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
        print_status "I2C interface enabled"
    fi
    
    # Set GPU memory split for camera
    if ! grep -q "^gpu_mem=" /boot/config.txt; then
        echo "gpu_mem=128" | sudo tee -a /boot/config.txt
        print_status "GPU memory set to 128MB"
    fi
    
    # Add user to required groups
    sudo usermod -a -G video,i2c,gpio $USER
    print_status "User added to hardware groups"
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Upgrade pip
    python3 -m pip install --upgrade pip
    
    # Install numpy first (required by opencv)
    python3 -m pip install numpy==1.24.3
    
    # Install OpenCV (use pre-built wheel for ARM if available)
    if check_raspberry_pi; then
        # Try to install optimized OpenCV for Pi
        python3 -m pip install opencv-python-headless==4.8.1.78
    else
        python3 -m pip install opencv-python==4.8.1.78
    fi
    
    # Install other requirements
    python3 -m pip install -r requirements.txt --no-deps
    
    print_status "Python dependencies installed"
}

# Setup pigpio daemon
setup_pigpio() {
    print_status "Setting up pigpio daemon..."
    
    # Enable pigpio daemon to start on boot
    sudo systemctl enable pigpiod
    sudo systemctl start pigpiod
    
    print_status "pigpio daemon configured"
}

# Create systemd service
create_service() {
    print_status "Creating systemd service..."
    
    cat > /tmp/betafly-stabilization.service << EOF
[Unit]
Description=Betafly Optical Stabilization System
After=multi-user.target pigpiod.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/main.py --daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    sudo mv /tmp/betafly-stabilization.service /etc/systemd/system/
    sudo systemctl daemon-reload
    
    print_status "Systemd service created (betafly-stabilization.service)"
}

# Performance optimizations for Pi Zero
optimize_pi_zero() {
    print_status "Applying Pi Zero optimizations..."
    
    # Disable unnecessary services
    sudo systemctl disable bluetooth
    sudo systemctl disable hciuart
    sudo systemctl disable avahi-daemon
    sudo systemctl disable triggerhappy
    
    # Set CPU governor to performance
    echo "performance" | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
    
    # Add to rc.local for persistence
    if ! grep -q "scaling_governor" /etc/rc.local; then
        sudo sed -i '/^exit 0/i echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor' /etc/rc.local
    fi
    
    print_status "Pi Zero optimizations applied"
}

# Test installation
test_installation() {
    print_status "Testing installation..."
    
    # Test Python imports
    python3 -c "import cv2; print('OpenCV version:', cv2.__version__)" || print_error "OpenCV import failed"
    python3 -c "import numpy; print('NumPy version:', numpy.__version__)" || print_error "NumPy import failed"
    
    if check_raspberry_pi; then
        python3 -c "import picamera2; print('PiCamera2 available')" || print_warning "PiCamera2 not available"
        python3 -c "import pigpio; print('pigpio available')" || print_warning "pigpio not available"
    fi
    
    # Test camera
    if command -v libcamera-hello &> /dev/null; then
        print_status "Testing camera..."
        timeout 2 libcamera-hello --nopreview || print_warning "Camera test failed"
    fi
    
    # Run system test
    print_status "Running system test..."
    python3 main.py --test || print_warning "System test failed"
}

# Main installation flow
main() {
    echo ""
    print_status "Starting Betafly setup..."
    echo ""
    
    # Check for Raspberry Pi
    IS_PI=false
    if check_raspberry_pi; then
        IS_PI=true
    fi
    
    # Update system
    read -p "Update system packages? (recommended) [Y/n]: " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_warning "Skipping system update"
    else
        update_system
    fi
    
    # Install dependencies
    install_system_deps
    
    # Hardware setup (Pi only)
    if [ "$IS_PI" = true ]; then
        enable_hardware
        setup_pigpio
        
        # Check if Pi Zero
        if grep -q "Pi Zero" /proc/cpuinfo; then
            read -p "Apply Pi Zero optimizations? [Y/n]: " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                optimize_pi_zero
            fi
        fi
    fi
    
    # Install Python dependencies
    install_python_deps
    
    # Create service
    read -p "Create systemd service for auto-start? [Y/n]: " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        create_service
        echo ""
        print_status "To enable auto-start: sudo systemctl enable betafly-stabilization"
        print_status "To start service: sudo systemctl start betafly-stabilization"
    fi
    
    # Test installation
    echo ""
    test_installation
    
    # Final instructions
    echo ""
    echo "========================================="
    print_status "Setup complete!"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "1. Calibrate camera: python3 calibrate.py --camera"
    echo "2. Calibrate servos: python3 calibrate.py --servo"
    echo "3. Run stabilization: python3 main.py"
    echo ""
    
    if [ "$IS_PI" = true ]; then
        print_warning "A reboot is recommended to apply all changes"
        read -p "Reboot now? [Y/n]: " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            sudo reboot
        fi
    fi
}

# Run main function
main