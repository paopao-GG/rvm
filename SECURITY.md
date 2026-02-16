# Security Considerations for RVM System

## Overview

This document outlines known security limitations and considerations for the RVM (Reverse Vending Machine) WiFi portal system.

## Current Security Model

The system uses **MAC address-based authentication** to identify and authorize users. This approach has known limitations but may be acceptable depending on your deployment context.

## Known Limitations

### 1. MAC Address Spoofing (CRITICAL)

**Risk Level:** HIGH

**Description:**
MAC addresses can be trivially spoofed on most devices. A malicious user could:
- Observe another user's MAC address
- Change their device's MAC to impersonate that user
- Gain unauthorized access to accumulated WiFi time

**Mitigation Options:**
- **For Educational/Controlled Environments:** Document the limitation and rely on social trust
- **For Production Deployments:** Implement additional authentication:
  - SMS verification
  - Captcha challenges
  - Device fingerprinting
  - Session tokens with expiration
  - Rate limiting per MAC

**Current Status:** Documented but not mitigated. Comment added in code.

### 2. IP Address Validation

**Risk Level:** MEDIUM (Mitigated)

**Description:**
The system uses client IP addresses in subprocess commands for MAC address lookup.

**Mitigation:**
- ✅ IP addresses are validated using `ipaddress.ip_address()` before use in commands
- ✅ Uses subprocess with list arguments (prevents shell injection)
- ✅ Removed arp command (simplified to `ip neigh` only)

**Status:** MITIGATED as of latest version

### 3. No CSRF Protection

**Risk Level:** MEDIUM

**Description:**
Flask routes accepting POST requests do not have CSRF tokens. An attacker could:
- Craft malicious pages that trigger actions on behalf of authenticated users
- Lock/unlock machines without user consent

**Mitigation Options:**
- Implement Flask-WTF with CSRF protection
- Add origin header validation
- Require explicit user confirmation for state-changing operations

**Current Status:** Documented, not implemented (acceptable for captive portal use case)

### 4. iptables Commands Run as Root

**Risk Level:** LOW

**Description:**
The portal must run with sudo to execute iptables commands.

**Mitigation:**
- Commands use validated MAC addresses only (no user input)
- MAC addresses are validated before use
- subprocess.run() with list arguments prevents command injection

**Current Status:** Acceptable - proper input validation in place

### 5. Session Hijacking

**Risk Level:** MEDIUM

**Description:**
Sessions are tied to MAC addresses with no additional session tokens. If a MAC is spoofed, the attacker gains full session access.

**Mitigation Options:**
- Generate random session tokens stored in database
- Require periodic re-authentication
- Implement session expiry on inactivity

**Current Status:** Documented, relies on MAC address trust model

## Recommendations by Deployment Type

### Educational/Prototype Environment (Current)
✅ **Current security is acceptable** with the following caveats:
- Document limitations for users
- Trust that users won't exploit MAC spoofing
- Use in controlled environments (schools, labs)
- Monitor for unusual activity

### Production/Public Deployment
⚠️ **Additional security required:**

1. **Required:**
   - Implement SMS or email verification
   - Add CSRF protection to all POST endpoints
   - Implement rate limiting (max bottles per hour)
   - Add session tokens independent of MAC

2. **Recommended:**
   - Device fingerprinting (User-Agent + MAC + other signals)
   - Captcha on session start
   - Admin dashboard for monitoring abuse
   - Logging and alerting for suspicious patterns

3. **Optional:**
   - Payment integration instead of free WiFi
   - Physical token/card system
   - Camera-based user identification

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do not** open a public GitHub issue
2. Contact the maintainers privately
3. Provide detailed reproduction steps
4. Allow reasonable time for fixes before public disclosure

## Changelog

- **2024-02-16:** Initial security documentation created
  - IP validation added
  - MAC spoofing limitation documented
  - Security comment added to portal.py startup
