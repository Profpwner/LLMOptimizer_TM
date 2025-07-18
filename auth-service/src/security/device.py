"""Device fingerprinting service for enhanced security."""

import hashlib
import json
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from user_agents import parse

from ..models.security import DeviceFingerprint


class DeviceFingerprintService:
    """Service for device fingerprinting and tracking."""
    
    def __init__(self):
        self.fingerprint_components = [
            'user_agent',
            'accept_language',
            'accept_encoding',
            'screen_resolution',
            'color_depth',
            'timezone',
            'plugins',
            'fonts',
            'canvas_fingerprint',
            'webgl_fingerprint',
            'audio_fingerprint'
        ]
    
    def generate_fingerprint(self, device_data: Dict[str, any]) -> str:
        """Generate a device fingerprint from collected data."""
        # Sort keys for consistent hashing
        sorted_data = {k: device_data.get(k, '') for k in sorted(self.fingerprint_components) if k in device_data}
        
        # Create fingerprint string
        fingerprint_string = json.dumps(sorted_data, sort_keys=True)
        
        # Generate hash
        fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
        
        return fingerprint_hash
    
    def parse_user_agent(self, user_agent_string: str) -> Dict[str, str]:
        """Parse user agent string to extract device information."""
        user_agent = parse(user_agent_string)
        
        return {
            'browser': user_agent.browser.family,
            'browser_version': user_agent.browser.version_string,
            'os': user_agent.os.family,
            'os_version': user_agent.os.version_string,
            'device_type': self._get_device_type(user_agent),
            'device_name': user_agent.device.family if user_agent.device.family != 'Other' else None,
            'is_mobile': user_agent.is_mobile,
            'is_tablet': user_agent.is_tablet,
            'is_pc': user_agent.is_pc,
            'is_bot': user_agent.is_bot
        }
    
    def calculate_trust_score(
        self,
        fingerprint: str,
        user_id: str,
        ip_address: str,
        location: Dict[str, any],
        existing_fingerprints: List[DeviceFingerprint]
    ) -> Tuple[int, List[str]]:
        """Calculate trust score for a device fingerprint."""
        score = 50  # Start with neutral score
        factors = []
        
        # Check if fingerprint exists for user
        known_fingerprint = None
        for fp in existing_fingerprints:
            if fp.fingerprint == fingerprint:
                known_fingerprint = fp
                break
        
        if known_fingerprint:
            # Known device
            score += 30
            factors.append("known_device")
            
            # Check usage frequency
            if known_fingerprint.seen_count > 10:
                score += 10
                factors.append("frequently_used")
            
            # Check if trusted
            if known_fingerprint.is_trusted:
                score += 20
                factors.append("trusted_device")
            
            # Check location consistency
            if known_fingerprint.locations:
                location_match = any(
                    loc.get('country') == location.get('country') and
                    loc.get('city') == location.get('city')
                    for loc in known_fingerprint.locations
                )
                if location_match:
                    score += 5
                    factors.append("consistent_location")
                else:
                    score -= 10
                    factors.append("new_location")
        else:
            # New device
            score -= 20
            factors.append("new_device")
            
            # Check if user has many devices
            if len(existing_fingerprints) > 5:
                score -= 10
                factors.append("many_devices")
        
        # Location-based scoring
        suspicious_countries = ['XX', 'A1', 'A2']  # Anonymous proxy indicators
        if location.get('country_code') in suspicious_countries:
            score -= 30
            factors.append("suspicious_location")
        
        # Time-based scoring (detect unusual login times)
        current_hour = datetime.utcnow().hour
        if 2 <= current_hour <= 5:  # Late night hours
            score -= 5
            factors.append("unusual_time")
        
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        return score, factors
    
    def is_suspicious_pattern(
        self,
        user_id: str,
        fingerprint: str,
        ip_address: str,
        recent_attempts: List[Dict[str, any]]
    ) -> Tuple[bool, List[str]]:
        """Detect suspicious patterns in device usage."""
        suspicious_indicators = []
        
        # Check for rapid device switching
        recent_fingerprints = set()
        for attempt in recent_attempts[-10:]:  # Last 10 attempts
            if attempt.get('device_fingerprint'):
                recent_fingerprints.add(attempt['device_fingerprint'])
        
        if len(recent_fingerprints) > 3:
            suspicious_indicators.append("rapid_device_switching")
        
        # Check for impossible travel
        if len(recent_attempts) >= 2:
            last_attempt = recent_attempts[-1]
            time_diff = (datetime.utcnow() - last_attempt['timestamp']).total_seconds() / 3600  # hours
            
            if time_diff < 2:  # Less than 2 hours
                last_location = last_attempt.get('location', {})
                current_location = self._get_location_from_ip(ip_address)
                
                if (last_location.get('country') != current_location.get('country') and
                    last_location.get('country') and current_location.get('country')):
                    suspicious_indicators.append("impossible_travel")
        
        # Check for automated behavior
        if self._detect_automation_patterns(recent_attempts):
            suspicious_indicators.append("automated_behavior")
        
        # Check for credential stuffing patterns
        if self._detect_credential_stuffing(recent_attempts):
            suspicious_indicators.append("credential_stuffing_pattern")
        
        return len(suspicious_indicators) > 0, suspicious_indicators
    
    def _get_device_type(self, user_agent) -> str:
        """Determine device type from user agent."""
        if user_agent.is_mobile:
            return "mobile"
        elif user_agent.is_tablet:
            return "tablet"
        elif user_agent.is_pc:
            return "desktop"
        elif user_agent.is_bot:
            return "bot"
        else:
            return "unknown"
    
    def _get_location_from_ip(self, ip_address: str) -> Dict[str, any]:
        """Get location from IP address (placeholder - integrate with GeoIP service)."""
        # In production, integrate with MaxMind GeoIP or similar service
        return {
            'country': 'US',
            'country_code': 'US',
            'city': 'Unknown',
            'region': 'Unknown',
            'lat': 0.0,
            'lng': 0.0
        }
    
    def _detect_automation_patterns(self, recent_attempts: List[Dict[str, any]]) -> bool:
        """Detect patterns indicating automated access."""
        if len(recent_attempts) < 5:
            return False
        
        # Check for consistent time intervals
        timestamps = [attempt['timestamp'] for attempt in recent_attempts[-5:]]
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)
        
        # If intervals are too consistent, might be automated
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
            
            # Low variance in intervals suggests automation
            if variance < 10:  # Less than 10 seconds variance
                return True
        
        return False
    
    def _detect_credential_stuffing(self, recent_attempts: List[Dict[str, any]]) -> bool:
        """Detect credential stuffing attack patterns."""
        if len(recent_attempts) < 10:
            return False
        
        # Check for multiple failed attempts from different IPs
        failed_ips = set()
        for attempt in recent_attempts[-20:]:  # Last 20 attempts
            if not attempt.get('success', True):
                failed_ips.add(attempt.get('ip_address'))
        
        # Multiple IPs with failed attempts might indicate credential stuffing
        return len(failed_ips) > 5
    
    @staticmethod
    def sanitize_fingerprint_data(data: Dict[str, any]) -> Dict[str, any]:
        """Sanitize fingerprint data for storage."""
        # Remove sensitive information
        sanitized = data.copy()
        sensitive_keys = ['password', 'token', 'cookie', 'session']
        
        for key in list(sanitized.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                del sanitized[key]
        
        return sanitized