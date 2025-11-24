"""
PID Controller for position stabilization
Includes auto-tuning and anti-windup features
"""

import time
import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PIDGains:
    """PID controller gains"""
    kp: float = 1.0  # Proportional gain
    ki: float = 0.0  # Integral gain
    kd: float = 0.0  # Derivative gain
    

@dataclass
class PIDState:
    """PID controller state"""
    error: float = 0.0
    integral: float = 0.0
    derivative: float = 0.0
    last_error: float = 0.0
    last_time: float = 0.0
    output: float = 0.0


class PIDController:
    """
    PID controller with anti-windup and rate limiting
    Optimized for servo control in stabilization systems
    """
    
    def __init__(self, gains: PIDGains, 
                 output_limits: Tuple[float, float] = (-90, 90),
                 integral_limits: Tuple[float, float] = (-50, 50),
                 derivative_filter_coeff: float = 0.1):
        """
        Initialize PID controller
        
        Args:
            gains: PID gain values
            output_limits: Min/max output values
            integral_limits: Anti-windup limits for integral term
            derivative_filter_coeff: Low-pass filter coefficient for derivative
        """
        self.gains = gains
        self.output_min, self.output_max = output_limits
        self.integral_min, self.integral_max = integral_limits
        self.derivative_filter_coeff = derivative_filter_coeff
        
        self.state = PIDState()
        self.setpoint = 0.0
        self.enabled = True
        
        # Performance monitoring
        self.error_history = deque(maxlen=100)
        self.output_history = deque(maxlen=100)
        
    def set_gains(self, kp: Optional[float] = None, 
                  ki: Optional[float] = None, 
                  kd: Optional[float] = None):
        """Update PID gains"""
        if kp is not None:
            self.gains.kp = kp
        if ki is not None:
            self.gains.ki = ki
        if kd is not None:
            self.gains.kd = kd
        logger.info(f"PID gains updated: P={self.gains.kp}, I={self.gains.ki}, D={self.gains.kd}")
        
    def reset(self):
        """Reset controller state"""
        self.state = PIDState()
        self.state.last_time = time.time()
        logger.debug("PID controller reset")
        
    def compute(self, measurement: float, dt: Optional[float] = None) -> float:
        """
        Compute PID output
        
        Args:
            measurement: Current measured value
            dt: Time delta (auto-calculated if None)
            
        Returns:
            Control output value
        """
        if not self.enabled:
            return 0.0
            
        current_time = time.time()
        
        if dt is None:
            if self.state.last_time == 0:
                dt = 0.02  # Default 50Hz
            else:
                dt = current_time - self.state.last_time
                
        if dt <= 0:
            return self.state.output
            
        # Calculate error
        error = self.setpoint - measurement
        self.state.error = error
        
        # Proportional term
        p_term = self.gains.kp * error
        
        # Integral term with anti-windup
        self.state.integral += error * dt
        self.state.integral = np.clip(
            self.state.integral, 
            self.integral_min, 
            self.integral_max
        )
        i_term = self.gains.ki * self.state.integral
        
        # Derivative term with filtering
        if self.state.last_error != 0:
            raw_derivative = (error - self.state.last_error) / dt
            # Low-pass filter on derivative
            self.state.derivative = (
                self.derivative_filter_coeff * raw_derivative + 
                (1 - self.derivative_filter_coeff) * self.state.derivative
            )
        else:
            self.state.derivative = 0
        d_term = self.gains.kd * self.state.derivative
        
        # Calculate total output
        output = p_term + i_term + d_term
        
        # Apply output limits
        self.state.output = np.clip(output, self.output_min, self.output_max)
        
        # Update state
        self.state.last_error = error
        self.state.last_time = current_time
        
        # Record for monitoring
        self.error_history.append(error)
        self.output_history.append(self.state.output)
        
        return self.state.output
        
    def set_setpoint(self, setpoint: float):
        """Update controller setpoint"""
        self.setpoint = setpoint
        
    def enable(self):
        """Enable controller"""
        self.enabled = True
        self.reset()
        
    def disable(self):
        """Disable controller"""
        self.enabled = False
        self.state.output = 0.0
        
    def get_state(self) -> dict:
        """Get current controller state"""
        return {
            'setpoint': self.setpoint,
            'error': self.state.error,
            'integral': self.state.integral,
            'derivative': self.state.derivative,
            'output': self.state.output,
            'enabled': self.enabled
        }
        
    def get_performance_metrics(self) -> dict:
        """Calculate performance metrics"""
        if len(self.error_history) == 0:
            return {}
            
        errors = np.array(self.error_history)
        outputs = np.array(self.output_history)
        
        return {
            'mean_error': float(np.mean(np.abs(errors))),
            'max_error': float(np.max(np.abs(errors))),
            'std_error': float(np.std(errors)),
            'mean_output': float(np.mean(outputs)),
            'output_range': float(np.max(outputs) - np.min(outputs))
        }


class DualAxisPIDController:
    """
    Dual-axis PID controller for 2D stabilization (pan/tilt)
    """
    
    def __init__(self, 
                 x_gains: PIDGains, 
                 y_gains: PIDGains,
                 x_limits: Tuple[float, float] = (-90, 90),
                 y_limits: Tuple[float, float] = (-90, 90)):
        """
        Initialize dual-axis controller
        
        Args:
            x_gains: PID gains for X axis (pan)
            y_gains: PID gains for Y axis (tilt)
            x_limits: Output limits for X axis
            y_limits: Output limits for Y axis
        """
        self.x_controller = PIDController(x_gains, x_limits)
        self.y_controller = PIDController(y_gains, y_limits)
        
    def compute(self, x_measurement: float, y_measurement: float, 
                dt: Optional[float] = None) -> Tuple[float, float]:
        """
        Compute control outputs for both axes
        
        Args:
            x_measurement: Current X position
            y_measurement: Current Y position
            dt: Time delta
            
        Returns:
            Tuple of (x_output, y_output)
        """
        x_output = self.x_controller.compute(x_measurement, dt)
        y_output = self.y_controller.compute(y_measurement, dt)
        return (x_output, y_output)
        
    def set_setpoint(self, x: float, y: float):
        """Set setpoint for both axes"""
        self.x_controller.set_setpoint(x)
        self.y_controller.set_setpoint(y)
        
    def reset(self):
        """Reset both controllers"""
        self.x_controller.reset()
        self.y_controller.reset()
        
    def enable(self):
        """Enable both controllers"""
        self.x_controller.enable()
        self.y_controller.enable()
        
    def disable(self):
        """Disable both controllers"""
        self.x_controller.disable()
        self.y_controller.disable()
        
    def get_state(self) -> dict:
        """Get state of both controllers"""
        return {
            'x': self.x_controller.get_state(),
            'y': self.y_controller.get_state()
        }


class AutoTuner:
    """
    PID auto-tuning using Ziegler-Nichols method
    Simplified for embedded systems
    """
    
    def __init__(self, controller: PIDController):
        """
        Initialize auto-tuner
        
        Args:
            controller: PID controller to tune
        """
        self.controller = controller
        self.oscillation_data = []
        self.tuning_active = False
        self.ku = None  # Ultimate gain
        self.tu = None  # Ultimate period
        
    def start_tuning(self, initial_gain: float = 1.0):
        """Start auto-tuning process"""
        # Set controller to P-only mode
        self.controller.set_gains(kp=initial_gain, ki=0, kd=0)
        self.oscillation_data = []
        self.tuning_active = True
        logger.info(f"Auto-tuning started with initial gain {initial_gain}")
        
    def update(self, measurement: float) -> bool:
        """
        Update tuning with new measurement
        
        Args:
            measurement: Current system measurement
            
        Returns:
            True if tuning is complete
        """
        if not self.tuning_active:
            return False
            
        self.oscillation_data.append((time.time(), measurement))
        
        # Need enough data to detect oscillations
        if len(self.oscillation_data) < 50:
            return False
            
        # Detect oscillations
        if self._detect_oscillation():
            self._calculate_gains()
            self.tuning_active = False
            return True
            
        # Increase gain if no oscillation
        if len(self.oscillation_data) > 100:
            current_kp = self.controller.gains.kp
            self.controller.set_gains(kp=current_kp * 1.5)
            self.oscillation_data = self.oscillation_data[-50:]  # Keep recent data
            logger.info(f"Increasing gain to {current_kp * 1.5}")
            
        return False
        
    def _detect_oscillation(self) -> bool:
        """Detect if system is oscillating"""
        if len(self.oscillation_data) < 20:
            return False
            
        # Extract measurements
        measurements = [m for _, m in self.oscillation_data[-20:]]
        
        # Simple peak detection
        peaks = []
        for i in range(1, len(measurements) - 1):
            if (measurements[i] > measurements[i-1] and 
                measurements[i] > measurements[i+1]):
                peaks.append(i)
                
        # Need at least 3 peaks for oscillation
        if len(peaks) >= 3:
            # Calculate period
            periods = [peaks[i+1] - peaks[i] for i in range(len(peaks)-1)]
            avg_period = np.mean(periods) * 0.02  # Convert to seconds
            
            # Check if periods are consistent
            if np.std(periods) < np.mean(periods) * 0.2:
                self.ku = self.controller.gains.kp
                self.tu = avg_period
                logger.info(f"Oscillation detected: Ku={self.ku}, Tu={self.tu}")
                return True
                
        return False
        
    def _calculate_gains(self):
        """Calculate PID gains using Ziegler-Nichols method"""
        if self.ku is None or self.tu is None:
            return
            
        # Ziegler-Nichols PID coefficients
        kp = 0.6 * self.ku
        ki = 2.0 * kp / self.tu
        kd = kp * self.tu / 8.0
        
        self.controller.set_gains(kp=kp, ki=ki, kd=kd)
        logger.info(f"Auto-tuning complete: P={kp:.3f}, I={ki:.3f}, D={kd:.3f}")