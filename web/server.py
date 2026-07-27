#!/usr/bin/env python3
"""
Web monitoring server for Betafly Stabilization System
Provides real-time status and control interface
"""

import json
import time
import threading
import logging
import io
import base64
import sys
import os
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
from PIL import Image

from src.stabilizer import Stabilizer, StabilizerConfig

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'betafly-secret-key-change-in-production'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global stabilizer instance
stabilizer: Optional[Stabilizer] = None
monitoring_thread = None
streaming_thread = None
monitoring_active = False


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current system status"""
    if stabilizer:
        status = stabilizer.get_status()
        status['timestamp'] = datetime.now().isoformat()
        return jsonify(status)
    return jsonify({'error': 'Stabilizer not initialized'}), 503


@app.route('/api/control/stabilization', methods=['POST'])
def control_stabilization():
    """Enable/disable stabilization"""
    if not stabilizer:
        return jsonify({'error': 'Stabilizer not initialized'}), 503
        
    data = request.json
    enable = data.get('enable', False)
    stabilizer.enable_stabilization(enable)
    
    return jsonify({'success': True, 'enabled': enable})


@app.route('/api/control/reset', methods=['POST'])
def reset_tracking():
    """Reset tracking reference"""
    if not stabilizer:
        return jsonify({'error': 'Stabilizer not initialized'}), 503
        
    stabilizer.reset_tracking()
    return jsonify({'success': True})


@app.route('/api/control/pid', methods=['POST'])
def update_pid():
    """Update PID gains"""
    if not stabilizer:
        return jsonify({'error': 'Stabilizer not initialized'}), 503
        
    data = request.json
    axis = data.get('axis')
    kp = float(data.get('kp', 0))
    ki = float(data.get('ki', 0))
    kd = float(data.get('kd', 0))
    
    stabilizer.set_pid_gains(axis, kp, ki, kd)
    
    return jsonify({
        'success': True,
        'axis': axis,
        'gains': {'kp': kp, 'ki': ki, 'kd': kd}
    })


@app.route('/api/control/servo', methods=['POST'])
def control_servo():
    """Manual servo control"""
    if not stabilizer:
        return jsonify({'error': 'Stabilizer not initialized'}), 503
        
    data = request.json
    pan = data.get('pan')
    tilt = data.get('tilt')
    
    if stabilizer.servos:
        stabilizer.servos.set_angle(pan, tilt)
        return jsonify({'success': True, 'pan': pan, 'tilt': tilt})
        
    return jsonify({'error': 'Servos not initialized'}), 503


@app.route('/api/capture')
def capture_frame():
    """Capture current frame"""
    if not stabilizer or not stabilizer.camera:
        return jsonify({'error': 'Camera not initialized'}), 503
        
    frame = stabilizer.camera.get_frame()
    if frame is None:
        return jsonify({'error': 'No frame available'}), 503
        
    # Draw tracking features if available
    if stabilizer.tracker:
        frame = stabilizer.tracker.draw_features(frame)
        
    # Convert to JPEG
    img = Image.fromarray(frame)
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=80)
    
    # Encode as base64
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return jsonify({
        'success': True,
        'image': f'data:image/jpeg;base64,{img_str}',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """Get or update configuration"""
    if request.method == 'GET':
        if stabilizer:
            return jsonify(stabilizer.config.__dict__)
        return jsonify({'error': 'Stabilizer not initialized'}), 503
        
    else:  # POST
        if not stabilizer:
            return jsonify({'error': 'Stabilizer not initialized'}), 503
            
        data = request.json
        for key, value in data.items():
            if hasattr(stabilizer.config, key):
                setattr(stabilizer.config, key, value)
                
        # Save configuration
        config_file = 'config/config.json'
        stabilizer.config.to_json(config_file)
        
        return jsonify({'success': True, 'config': stabilizer.config.__dict__})


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Betafly monitoring'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('start_monitoring')
def start_monitoring():
    """Start sending real-time updates"""
    global monitoring_active
    monitoring_active = True
    emit('monitoring_started', {'status': 'active'})


@socketio.on('stop_monitoring')
def stop_monitoring():
    """Stop sending real-time updates"""
    global monitoring_active
    monitoring_active = False
    emit('monitoring_stopped', {'status': 'inactive'})


def monitoring_loop():
    """Background thread for sending real-time updates"""
    global monitoring_active
    
    while True:
        if monitoring_active and stabilizer:
            try:
                # Get current status
                status = stabilizer.get_status()
                
                # Emit to all connected clients
                socketio.emit('status_update', status)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                
        time.sleep(0.1)  # 10Hz update rate


def video_stream_generator():
    """Generate video stream frames"""
    while True:
        if stabilizer and stabilizer.camera:
            frame = stabilizer.camera.get_frame(timeout=0.1)
            if frame is not None:
                # Draw tracking features
                if stabilizer.tracker:
                    frame = stabilizer.tracker.draw_features(frame)
                    
                # Add status overlay
                stats = stabilizer.get_status()['stats']
                cv2.putText(frame, f"FPS: {stats['tracking_fps']:.1f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Confidence: {stats['tracking_confidence']:.2f}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                           
                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                frame_data = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                       
        time.sleep(0.05)  # 20 FPS max


@app.route('/video_feed')
def video_feed():
    """Video streaming endpoint"""
    return Response(video_stream_generator(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


def initialize_stabilizer(config_file: str = None):
    """Initialize stabilizer instance"""
    global stabilizer
    
    try:
        # Load configuration
        if config_file and os.path.exists(config_file):
            config = StabilizerConfig.from_json(config_file)
        else:
            config = StabilizerConfig()
            
        # Create stabilizer
        stabilizer = Stabilizer(config)
        
        # Set callbacks for web interface
        def frame_callback(frame, tracking_result):
            # Could emit frame via websocket if needed
            pass
            
        def status_callback(status):
            if monitoring_active:
                socketio.emit('status_update', status)
                
        stabilizer.frame_callback = frame_callback
        stabilizer.status_callback = status_callback
        
        # Initialize hardware
        if stabilizer.initialize():
            stabilizer.start()
            logger.info("Stabilizer initialized and started")
            return True
        else:
            logger.error("Failed to initialize stabilizer")
            return False
            
    except Exception as e:
        logger.error(f"Stabilizer initialization error: {e}")
        return False


def run_server(host='0.0.0.0', port=8080, config_file=None):
    """Run the web server"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize stabilizer
    if not initialize_stabilizer(config_file):
        logger.error("Failed to initialize stabilizer, running in demo mode")
        
    # Start monitoring thread
    global monitoring_thread
    monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitoring_thread.start()
    
    logger.info(f"Starting web server on {host}:{port}")
    
    # Run Flask app with SocketIO
    socketio.run(app, host=host, port=port, debug=False)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Betafly Web Monitoring Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host address')
    parser.add_argument('--port', type=int, default=8080, help='Port number')
    parser.add_argument('--config', default='config/config.json', help='Config file')
    
    args = parser.parse_args()
    
    run_server(args.host, args.port, args.config)