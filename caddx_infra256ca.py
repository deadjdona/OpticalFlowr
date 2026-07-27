"""
Caddx Infra 256CA driver with AI Box streaming support.

The 256CA variant forwards optical flow deltas through an external "AI Box"
that communicates over USB serial or TCP. This module normalizes that stream so
the rest of the stabilization stack can treat it like a regular optical flow
sensor.
"""

import json
import logging
import socket
import threading
import time
import re
from typing import Optional, Tuple

try:
    import serial  # type: ignore
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class CaddxInfra256CA:
    """
    Reader for the Caddx Infra 256CA + AI Box combo.

    The AI Box periodically streams motion packets that contain delta X/Y,
    surface quality, and (optionally) a height estimate. Packets can be JSON,
    CSV, or key/value lines; this class attempts to parse all of them.
    """

    KEY_ALIASES = {
        "dx": {"dx", "delta_x", "x", "vx"},
        "dy": {"dy", "delta_y", "y", "vy"},
        "quality": {"quality", "squal", "sq"},
        "height": {"height", "height_m", "alt", "altitude", "h"},
    }

    def __init__(
        self,
        rotation: int = 0,
        connection: str = "auto",
        serial_port: str = "/dev/ttyUSB0",
        serial_baudrate: int = 921600,
        tcp_host: Optional[str] = None,
        tcp_port: int = 8899,
        data_format: str = "auto",
        data_timeout: float = 0.25,
        height_scale: float = 1.0,
        height_smoothing: float = 0.2,
    ):
        """
        Args:
            rotation: Sensor rotation in degrees (0, 90, 180, 270)
            connection: 'serial', 'tcp', or 'auto' (choose based on host value)
            serial_port: Serial device when using USB (e.g. /dev/ttyUSB0)
            serial_baudrate: Baud rate for serial connection
            tcp_host: Host/IP of the AI Box when using TCP/Ethernet
            tcp_port: TCP port exposed by the AI Box
            data_format: 'auto', 'json', or 'csv'
            data_timeout: Time (s) before data is considered stale
            height_scale: Multiplier applied to height data coming from AI Box
            height_smoothing: Low-pass filter factor for height updates (0-1)
        """

        if height_smoothing < 0.0 or height_smoothing > 1.0:
            raise ValueError("height_smoothing must be between 0 and 1")

        self.rotation = rotation
        self.serial_port = serial_port
        self.serial_baudrate = serial_baudrate
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.data_format = data_format.lower()
        self.data_timeout = max(0.05, data_timeout)
        self.height_scale = height_scale
        self.height_smoothing = height_smoothing

        connection = connection.lower()
        if connection not in ("serial", "tcp", "auto"):
            connection = "auto"
        if connection == "auto":
            connection = "tcp" if tcp_host else "serial"
        if connection == "serial" and not SERIAL_AVAILABLE:
            raise RuntimeError(
                "pyserial is required for Caddx Infra 256CA serial mode. "
                "Install with: pip install pyserial"
            )
        if connection == "tcp" and not tcp_host:
            raise RuntimeError("tcp_host must be provided when connection='tcp'")
        self.connection = connection

        self._serial = None
        self._socket = None
        self._socket_stream = None

        self._lock = threading.Lock()
        self._last_motion: Tuple[int, int] = (0, 0)
        self._last_quality: int = 0
        self._last_height_raw: Optional[float] = None
        self._height_filtered: Optional[float] = None
        self._last_update_time = 0.0

        self._running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True
        )
        self._reader_thread.start()

        logger.info(
            "Caddx Infra 256CA AI Box initialized (connection=%s)", self.connection
        )

    # ------------------------------------------------------------------ Public API
    def get_motion(self) -> Tuple[int, int]:
        """Return the latest motion deltas (int, int)."""
        with self._lock:
            if time.time() - self._last_update_time > self.data_timeout:
                return (0, 0)
            return self._last_motion

    def get_surface_quality(self) -> int:
        """Best-effort surface quality metric from AI Box."""
        with self._lock:
            return self._last_quality

    def get_height_estimate(self) -> Optional[float]:
        """Return smoothed height estimate if the AI Box provides one."""
        with self._lock:
            return self._height_filtered

    def shutdown(self):
        """Stop reader thread and close any open connections."""
        self._running = False
        if self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.5)
        self._close_connections()
        logger.info("Caddx Infra 256CA AI Box reader stopped")

    # ---------------------------------------------------------------- Internal helpers
    def _reader_loop(self):
        """Continuously read from AI Box and parse motion packets."""
        while self._running:
            try:
                if self.connection == "serial":
                    if not self._serial:
                        self._open_serial()
                    line = self._serial.readline() if self._serial else b""
                else:
                    if not self._socket_stream:
                        self._open_tcp()
                    line = (
                        self._socket_stream.readline()
                        if self._socket_stream
                        else ""
                    )

                if not line:
                    time.sleep(0.05)
                    continue

                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="ignore")

                self._process_line(line.strip())

            except Exception as exc:
                logger.warning("AI Box read error: %s", exc)
                self._close_connections()
                time.sleep(0.5)

    def _open_serial(self):
        """Attempt to open serial device."""
        try:
            self._serial = serial.Serial(
                self.serial_port,
                self.serial_baudrate,
                timeout=1.0,
            )
            logger.info(
                "Connected to AI Box over serial %s @ %d baud",
                self.serial_port,
                self.serial_baudrate,
            )
        except Exception as exc:
            self._serial = None
            logger.error("Failed to open AI Box serial %s: %s", self.serial_port, exc)
            time.sleep(1.0)

    def _open_tcp(self):
        """Attempt to open TCP socket."""
        try:
            self._socket = socket.create_connection(
                (self.tcp_host, self.tcp_port), timeout=3.0
            )
            self._socket_stream = self._socket.makefile("r")
            logger.info(
                "Connected to AI Box over TCP %s:%d", self.tcp_host, self.tcp_port
            )
        except Exception as exc:
            self._socket = None
            self._socket_stream = None
            logger.error(
                "Failed to connect to AI Box TCP %s:%d: %s",
                self.tcp_host,
                self.tcp_port,
                exc,
            )
            time.sleep(1.0)

    def _close_connections(self):
        """Close any open serial or TCP handles."""
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        if self._socket_stream:
            try:
                self._socket_stream.close()
            except Exception:
                pass
            self._socket_stream = None
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    # ---------------------------------------------------------------- Parsing
    def _process_line(self, line: str):
        if not line:
            return

        packet = self._parse_packet(line)
        if not packet:
            logger.debug("Ignored AI Box line: %s", line)
            return

        dx = packet.get("dx")
        dy = packet.get("dy")
        quality = packet.get("quality")
        height = packet.get("height")

        with self._lock:
            if dx is not None and dy is not None:
                rotated = self._apply_rotation(int(dx), int(dy))
                self._last_motion = rotated
                self._last_update_time = time.time()

            if quality is not None:
                self._last_quality = max(0, min(255, int(quality)))

            if height is not None:
                scaled = float(height) * self.height_scale
                self._last_height_raw = scaled
                if self._height_filtered is None:
                    self._height_filtered = scaled
                else:
                    alpha = self.height_smoothing
                    self._height_filtered = (
                        (1 - alpha) * self._height_filtered + alpha * scaled
                    )

    def _parse_packet(self, line: str) -> Optional[dict]:
        """Parse JSON or CSV/KeyValue packet into a dict."""
        data = None
        if self.data_format in ("auto", "json") and line.startswith("{"):
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError:
                data = None

        if data is None:
            data = self._parse_key_value(line)

        if not data:
            return None

        result = {}
        for key, aliases in self.KEY_ALIASES.items():
            for alias in aliases:
                if alias in data:
                    result[key] = data[alias]
                    break

        # If CSV without headers was provided, map positions.
        if not result and isinstance(data, list):
            if len(data) >= 2:
                result["dx"] = data[0]
                result["dy"] = data[1]
            if len(data) >= 3:
                result["quality"] = data[2]
            if len(data) >= 4:
                result["height"] = data[3]

        cleaned = {}
        for key, value in result.items():
            try:
                if key in ("dx", "dy"):
                    cleaned[key] = int(float(value))
                elif key == "quality":
                    cleaned[key] = int(float(value))
                elif key == "height":
                    cleaned[key] = float(value)
            except (ValueError, TypeError):
                continue

        return cleaned if cleaned else None

    def _parse_key_value(self, line: str):
        """Parse CSV or key/value entries; returns dict or list of floats."""
        separators = re.split(r"[;,]", line)
        parts = [p.strip() for p in separators if p.strip()]

        if not parts:
            return None

        # Detect key/value style tokens
        has_pairs = any((":" in part) or ("=" in part) for part in parts)

        if has_pairs:
            data = {}
            for part in parts:
                if ":" in part:
                    key, value = part.split(":", 1)
                elif "=" in part:
                    key, value = part.split("=", 1)
                else:
                    continue
                data[key.strip().lower()] = value.strip()
            return data

        # Plain CSV numbers
        values = []
        for part in parts:
            try:
                values.append(float(part))
            except ValueError:
                return None
        return values

    def _apply_rotation(self, x: int, y: int) -> Tuple[int, int]:
        """Apply sensor rotation (clockwise) to deltas."""
        rotation = self.rotation % 360
        if rotation == 0:
            return (x, y)
        if rotation == 90:
            return (y, -x)
        if rotation == 180:
            return (-x, -y)
        if rotation == 270:
            return (-y, x)
        return (x, y)

