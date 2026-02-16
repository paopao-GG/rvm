#!/usr/bin/env python3
"""
HX711 Load Cell Amplifier Driver for Raspberry Pi 5
Uses gpiozero (lgpio backend) — no RPi.GPIO dependency.

Bit-bangs the HX711 24-bit ADC protocol:
  1. Wait for DT (DOUT) to go LOW (data ready)
  2. Pulse SCK (PD_SCK) 24 times, reading DT each time
  3. One extra pulse for gain=128 on Channel A (25 total)
  4. Convert 24-bit two's complement to signed integer
"""

import time
import logging

from gpiozero import DigitalInputDevice, DigitalOutputDevice

logger = logging.getLogger(__name__)

# Default calibration scale factor (raw units per gram).
# Calibrate with a known weight: place weight, read raw, divide by grams.
SCALE_FACTOR = 420  # typical for 5kg load cell + HX711 at gain 128


class HX711:
    """HX711 24-bit ADC driver using gpiozero."""

    def __init__(self, dt_pin=5, sck_pin=6, gain=128):
        """
        Args:
            dt_pin: BCM pin for HX711 DOUT (data out)
            sck_pin: BCM pin for HX711 PD_SCK (clock)
            gain: Channel A gain — 128 (default) or 64. Channel B is 32.
        """
        self.dt = DigitalInputDevice(dt_pin)
        self.sck = DigitalOutputDevice(sck_pin, initial_value=False)
        self.offset = 0  # tare offset (raw value at zero load)
        self.scale = SCALE_FACTOR

        # gain determines extra SCK pulses after 24 data bits
        if gain == 128:
            self._gain_pulses = 1  # 25 total
        elif gain == 64:
            self._gain_pulses = 3  # 27 total
        elif gain == 32:
            self._gain_pulses = 2  # 26 total (channel B)
        else:
            self._gain_pulses = 1

        logger.info("HX711: initialized (DT=GPIO%d, SCK=GPIO%d, gain=%d)", dt_pin, sck_pin, gain)

        # Do one dummy read to set the gain register
        try:
            self.read_raw()
        except TimeoutError:
            logger.warning("HX711: initial read timed out (sensor may not be connected)")

    def _wait_ready(self, timeout=2.0):
        """Wait for HX711 to signal data ready (DT goes LOW)."""
        start = time.time()
        while self.dt.value == 1:
            if time.time() - start > timeout:
                raise TimeoutError("HX711 not ready (DT stayed HIGH)")
            time.sleep(0.001)

    def read_raw(self):
        """Read a single 24-bit raw value from the HX711.

        Returns:
            Signed integer (24-bit two's complement).

        Raises:
            TimeoutError: If HX711 doesn't become ready within 2 seconds.
        """
        self._wait_ready()

        # Read 24 data bits (MSB first)
        value = 0
        for _ in range(24):
            self.sck.on()
            time.sleep(0.000001)  # 1 us pulse
            value = (value << 1) | self.dt.value
            self.sck.off()
            time.sleep(0.000001)

        # Extra pulses to set gain for next reading
        for _ in range(self._gain_pulses):
            self.sck.on()
            time.sleep(0.000001)
            self.sck.off()
            time.sleep(0.000001)

        # Convert 24-bit two's complement to signed
        if value & 0x800000:
            value -= 0x1000000

        return value

    def read_average(self, times=5):
        """Read multiple values and return the average.

        Args:
            times: Number of readings to average.

        Returns:
            Average raw value as float.
        """
        readings = []
        for _ in range(times):
            try:
                readings.append(self.read_raw())
            except TimeoutError:
                logger.warning("HX711: timeout during average read, skipping sample")
        if not readings:
            raise TimeoutError("HX711: all readings timed out")
        return sum(readings) / len(readings)

    def tare(self, times=10):
        """Set current weight as zero reference.

        Args:
            times: Number of readings to average for tare.
        """
        self.offset = self.read_average(times)
        logger.info("HX711: tared (offset=%d)", self.offset)

    def get_grams(self, times=3):
        """Read weight in grams (relative to tare).

        Args:
            times: Number of readings to average.

        Returns:
            Weight in grams (float). May be negative if lighter than tare.
        """
        raw = self.read_average(times)
        return (raw - self.offset) / self.scale

    def get_raw_change(self, baseline, times=3):
        """Get the raw value change from a baseline.

        Args:
            baseline: Previous raw reading to compare against.
            times: Number of readings to average.

        Returns:
            Change in raw units (positive = heavier).
        """
        current = self.read_average(times)
        return current - baseline

    def weight_changed(self, baseline, threshold_grams=5, times=3):
        """Check if weight has increased above a threshold.

        Args:
            baseline: Previous raw reading to compare against.
            threshold_grams: Minimum weight change in grams.
            times: Number of readings to average.

        Returns:
            True if weight increased by more than threshold.
        """
        change = self.get_raw_change(baseline, times)
        change_grams = change / self.scale
        logger.info("HX711: weight change = %.1fg (threshold = %dg)", change_grams, threshold_grams)
        return change_grams > threshold_grams

    def power_down(self):
        """Put HX711 into power-down mode (SCK HIGH for >60us)."""
        self.sck.on()
        time.sleep(0.0001)  # 100 us

    def power_up(self):
        """Wake HX711 from power-down mode."""
        self.sck.off()
        time.sleep(0.001)

    def cleanup(self):
        """Release GPIO resources."""
        try:
            self.sck.off()
            self.dt.close()
            self.sck.close()
            logger.info("HX711: GPIO cleaned up")
        except Exception as e:
            logger.warning("HX711: cleanup error: %s", e)
