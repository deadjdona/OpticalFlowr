"""
Betafly Optical Position Stabilization System
Core modules for vision-based stabilization on Raspberry Pi Zero
"""

__version__ = "1.0.0"
__author__ = "Betafly Team"

from .camera import Camera
from .tracker import OpticalTracker
from .controller import PIDController
from .servo import ServoController
from .stabilizer import Stabilizer
from .thermal_camera import CaddxInfra256CA, ThermalConfig, ThermalColormap
from .thermal_tracker import ThermalTracker
from .thermal_processing import ThermalProcessor

__all__ = [
    'Camera',
    'OpticalTracker',
    'PIDController',
    'ServoController',
    'Stabilizer',
    'CaddxInfra256CA',
    'ThermalConfig',
    'ThermalColormap',
    'ThermalTracker',
    'ThermalProcessor'
]