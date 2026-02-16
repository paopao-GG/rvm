#!/usr/bin/env python3
"""
RVM Shared Utilities
Common functions used across the RVM system
"""

import ipaddress
from typing import Optional


def format_time(seconds: int) -> str:
    """
    Format seconds as MM:SS.

    Args:
        seconds: Total seconds to format

    Returns:
        Formatted time string like "5:30" or "0:45"
    """
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def validate_ip_address(ip: str) -> bool:
    """
    Validate that a string is a valid IP address.

    Args:
        ip: IP address string to validate

    Returns:
        True if valid IP address, False otherwise
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_mac_address(mac: str) -> bool:
    """
    Validate that a string is a valid MAC address format.

    Args:
        mac: MAC address string to validate (format: XX:XX:XX:XX:XX:XX)

    Returns:
        True if valid MAC format, False otherwise
    """
    if not mac or mac == "UNKNOWN":
        return False

    # Check format: XX:XX:XX:XX:XX:XX
    parts = mac.split(':')
    if len(parts) != 6:
        return False

    for part in parts:
        if len(part) != 2:
            return False
        try:
            int(part, 16)
        except ValueError:
            return False

    return True
