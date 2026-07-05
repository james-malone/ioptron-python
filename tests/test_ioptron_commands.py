#!/usr/bin/env python3
"""
Unit tests for ioptron.py command formatting against the iOptron RS-232
Command Language v3.10 specification.

These tests mock the socket so no mount connection is needed. They verify
that every command sent to the mount matches the exact format from the spec.

Run:  python3 -m pytest test_ioptron_commands.py -v
  or: python3 test_ioptron_commands.py
"""

import os
import re
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure we can import from the same directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
IOPTRON_DIR = os.path.join(REPO_DIR, 'ioptron')
for p in (REPO_DIR, IOPTRON_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import utils
from ioptron import TelescopeController


def make_controller():
    """Create a TelescopeController with a mocked socket that records sent commands."""
    tc = TelescopeController.__new__(TelescopeController)
    tc.host = "127.0.0.1"
    tc.port = 8080
    tc.socket = MagicMock()
    tc.sent_commands = []

    original_send = tc.__class__.send

    def mock_send(self, command, read_until_char='#', timeout=10, retries=5, max_chars=None):
        self.sent_commands.append(command)
        return "1"  # Default success response

    tc.send = lambda *a, **kw: mock_send(tc, *a, **kw)
    return tc


def make_initialized_controller():
    """Create a controller with mount_config_data set for CEM120."""
    tc = make_controller()
    tc.mount_config_data = {
        'type': 'equatorial',
        'capabilities': {'encoders': False, 'pec': True, 'mechanical_zero': True},
        'tracking_rates': {0: 'sidereal', 1: 'lunar', 2: 'solar', 3: 'king', 4: 'custom'},
        'tracking_speeds': {1: 1, 2: 2, 3: 8, 4: 16, 5: 64, 6: 128, 7: 256, 8: 512, 9: 900},
        'pier_sides': {0: 'east', 1: 'west', 2: 'intermediate'},
        'counterweight_direction': {0: 'up', 1: 'normal'},
    }
    # Initialize required attributes
    from ioptron import (Altitude, Azimuth, DEC, RA, SystemStatus, Tracking,
                         Meredian, MovingSpeed, Parking, Pec, TimeSource,
                         TimeInfo, Hemisphere, Location, Guiding, Firmwares)
    tc.location = Location()
    tc.system_status = SystemStatus()
    tc.tracking = Tracking()
    tc.time_source = TimeSource()
    tc.hemisphere = Hemisphere()
    tc.moving_speed = MovingSpeed()
    tc.moving_speed.available_rates = tc.mount_config_data['tracking_speeds']
    tc.guiding = Guiding()
    tc.is_slewing = False
    tc.pec = Pec()
    tc.time = TimeInfo()
    tc.right_ascension = RA()
    tc.declination = DEC()
    tc.pier_side = None
    tc.counterweight_direction = None
    tc.altitude = Altitude()
    tc.azimuth = Azimuth()
    tc.meredian = Meredian()
    tc.parking = Parking()
    tc.last_update = 0
    tc.tracking.available_rates = tc.mount_config_data['tracking_rates']
    return tc


# ═══════════════════════════════════════════════════════════════════
# POSITION COMMANDS — :SRA, :Sd, :Sa, :Sz
# ═══════════════════════════════════════════════════════════════════
class TestSetCommandedRA(unittest.TestCase):
    """Spec: :SRATTTTTTTTT# — 9 digits, no sign, range [0, 129600000]"""

    def test_ra_zero(self):
        tc = make_controller()
        tc.set_commanded_right_ascension(0, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":SRA000000000#")

    def test_ra_12h(self):
        # 12h = 180° = 180 * 3600 * 100 = 64,800,000
        tc = make_controller()
        tc.set_commanded_right_ascension(12, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":SRA064800000#")

    def test_ra_23h_30m(self):
        # 23.5h = 352.5° = 352.5 * 3600 * 100 = 126,900,000
        tc = make_controller()
        tc.set_commanded_right_ascension(23, 30, 0)
        self.assertEqual(tc.sent_commands[-1], ":SRA126900000#")

    def test_ra_6h_15m_30s(self):
        # 6h 15m 30s = 6.25833...h = 93.875° = 93.875 * 360000 = 33,795,000
        tc = make_controller()
        tc.set_commanded_right_ascension(6, 15, 30)
        self.assertEqual(tc.sent_commands[-1], ":SRA033795000#")

    def test_ra_format_9_digits(self):
        tc = make_controller()
        tc.set_commanded_right_ascension(1, 0, 0)
        cmd = tc.sent_commands[-1]
        # Strip :SRA and #, check 9 digits
        payload = cmd[4:-1]
        self.assertEqual(len(payload), 9)
        self.assertTrue(payload.isdigit())

    def test_ra_max_value(self):
        # 24h = 360° = 129,600,000 (max)
        tc = make_controller()
        tc.set_commanded_right_ascension(24, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":SRA129600000#")


class TestSetCommandedDec(unittest.TestCase):
    """Spec: :SdsTTTTTTTT# — s=sign, 8 digits, range [-32400000, +32400000]"""

    def test_dec_zero(self):
        tc = make_controller()
        tc.set_commanded_declination(0, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sd+00000000#")

    def test_dec_positive_90(self):
        # 90° = 90 * 3600 * 100 = 32,400,000
        tc = make_controller()
        tc.set_commanded_declination(90, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sd+32400000#")

    def test_dec_negative_45(self):
        # -45° = -16,200,000
        tc = make_controller()
        tc.set_commanded_declination(-45, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sd-16200000#")

    def test_dec_positive_52_30(self):
        # 52° 30' = 52.5° = 18,900,000
        tc = make_controller()
        tc.set_commanded_declination(52, 30, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sd+18900000#")

    def test_dec_format_sign_plus_8_digits(self):
        tc = make_controller()
        tc.set_commanded_declination(10, 0, 0)
        cmd = tc.sent_commands[-1]
        # :Sd + sign + 8 digits + #
        self.assertTrue(cmd.startswith(":Sd"))
        self.assertTrue(cmd.endswith("#"))
        payload = cmd[3:-1]  # sign + digits
        self.assertIn(payload[0], ['+', '-'])
        self.assertEqual(len(payload[1:]), 8)
        self.assertTrue(payload[1:].isdigit())


class TestSetCommandedAlt(unittest.TestCase):
    """Spec: :SasTTTTTTTT# — s=sign, 8 digits"""

    def test_alt_positive(self):
        tc = make_controller()
        tc.set_commanded_altitude(45, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sa+16200000#")

    def test_alt_negative(self):
        tc = make_controller()
        tc.set_commanded_altitude(-10, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sa-03600000#")

    def test_alt_format(self):
        tc = make_controller()
        tc.set_commanded_altitude(0, 0, 0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":Sa"))
        payload = cmd[3:-1]
        self.assertIn(payload[0], ['+', '-'])
        self.assertEqual(len(payload[1:]), 8)


class TestSetCommandedAz(unittest.TestCase):
    """Spec: :SzTTTTTTTTT# — 9 digits, no sign, range [0, 129600000]"""

    def test_az_zero(self):
        tc = make_controller()
        tc.set_commanded_azimuth(0, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sz000000000#")

    def test_az_180(self):
        # 180° = 64,800,000
        tc = make_controller()
        tc.set_commanded_azimuth(180, 0, 0)
        self.assertEqual(tc.sent_commands[-1], ":Sz064800000#")

    def test_az_format_9_digits(self):
        tc = make_controller()
        tc.set_commanded_azimuth(90, 0, 0)
        cmd = tc.sent_commands[-1]
        payload = cmd[3:-1]
        self.assertEqual(len(payload), 9)
        self.assertTrue(payload.isdigit())


# ═══════════════════════════════════════════════════════════════════
# PULSE GUIDE COMMANDS — :ZS, :ZQ, :ZE, :ZC
# ═══════════════════════════════════════════════════════════════════
class TestPulseGuideCommands(unittest.TestCase):
    """Spec: :ZSXXXXX#, :ZQXXXXX#, :ZEXXXXX#, :ZCXXXXX# — 5 digits, milliseconds"""

    def test_ra_positive_5000ms(self):
        tc = make_controller()
        tc.move_ra_positive(5000)
        self.assertEqual(tc.sent_commands[-1], ":ZS05000#")

    def test_ra_negative_100ms(self):
        tc = make_controller()
        tc.move_ra_negative(100)
        self.assertEqual(tc.sent_commands[-1], ":ZQ00100#")

    def test_dec_positive_99999ms(self):
        tc = make_controller()
        tc.move_dec_positive(99999)
        self.assertEqual(tc.sent_commands[-1], ":ZE99999#")

    def test_dec_negative_0ms(self):
        tc = make_controller()
        tc.move_dec_negative(0)
        self.assertEqual(tc.sent_commands[-1], ":ZC00000#")

    def test_format_5_digits(self):
        tc = make_controller()
        tc.move_ra_positive(42)
        cmd = tc.sent_commands[-1]
        payload = cmd[3:-1]  # After :ZS, before #
        self.assertEqual(len(payload), 5)
        self.assertTrue(payload.isdigit())

    def test_rejects_negative(self):
        tc = make_controller()
        with self.assertRaises(AssertionError):
            tc.move_ra_positive(-1)

    def test_rejects_too_large(self):
        tc = make_controller()
        with self.assertRaises(AssertionError):
            tc.move_dec_negative(100000)


# ═══════════════════════════════════════════════════════════════════
# CARDINAL DIRECTION COMMANDS — :mn#, :me#, :ms#, :mw#
# ═══════════════════════════════════════════════════════════════════
class TestCardinalDirectionCommands(unittest.TestCase):
    """Spec: :mn# (Dec-), :me# (RA-), :ms# (Dec+), :mw# (RA+)"""

    def test_move_north(self):
        tc = make_controller()
        tc.move_north()
        self.assertEqual(tc.sent_commands[-1], ":mn#")

    def test_move_south(self):
        tc = make_controller()
        tc.move_south()
        self.assertEqual(tc.sent_commands[-1], ":ms#")

    def test_move_east(self):
        tc = make_controller()
        tc.move_east()
        self.assertEqual(tc.sent_commands[-1], ":me#")

    def test_move_west(self):
        tc = make_controller()
        tc.move_west()
        self.assertEqual(tc.sent_commands[-1], ":mw#")


# ═══════════════════════════════════════════════════════════════════
# STOP COMMANDS — :Q#, :qR#, :qD#
# ═══════════════════════════════════════════════════════════════════
class TestStopCommands(unittest.TestCase):

    def test_stop_all(self):
        tc = make_controller()
        tc.is_slewing = True
        tc.stop_all_movement()
        self.assertEqual(tc.sent_commands[-1], ":Q#")

    def test_stop_ew(self):
        tc = make_controller()
        tc.is_slewing = True
        tc.stop_e_or_w_movement()
        self.assertEqual(tc.sent_commands[-1], ":qR#")

    def test_stop_ns(self):
        tc = make_controller()
        tc.is_slewing = True
        tc.stop_n_or_s_movement()
        self.assertEqual(tc.sent_commands[-1], ":qD#")


# ═══════════════════════════════════════════════════════════════════
# TRACKING COMMANDS — :ST0#, :ST1#, :RT0-4#
# ═══════════════════════════════════════════════════════════════════
class TestTrackingCommands(unittest.TestCase):

    def test_start_tracking(self):
        tc = make_controller()
        tc.start_tracking()
        self.assertEqual(tc.sent_commands[-1], ":ST1#")

    def test_stop_tracking(self):
        tc = make_controller()
        tc.stop_tracking()
        self.assertEqual(tc.sent_commands[-1], ":ST0#")

    def test_set_tracking_rate_sidereal(self):
        tc = make_initialized_controller()
        tc.set_tracking_rate('sidereal')
        self.assertEqual(tc.sent_commands[-1], ":RT0#")

    def test_set_tracking_rate_lunar(self):
        tc = make_initialized_controller()
        tc.set_tracking_rate('lunar')
        self.assertEqual(tc.sent_commands[-1], ":RT1#")


# ═══════════════════════════════════════════════════════════════════
# SETTINGS COMMANDS
# ═══════════════════════════════════════════════════════════════════
class TestSetMeridianTreatment(unittest.TestCase):
    """Spec: :SMTnnn# — 1 digit code + 2 digit limit"""

    def test_stop_at_0(self):
        tc = make_initialized_controller()
        tc.set_meredian_treatment("stop", 0)
        self.assertEqual(tc.sent_commands[-1], ":SMT000#")

    def test_flip_at_10(self):
        tc = make_initialized_controller()
        tc.set_meredian_treatment("flip", 10)
        self.assertEqual(tc.sent_commands[-1], ":SMT110#")

    def test_flip_at_5(self):
        tc = make_initialized_controller()
        tc.set_meredian_treatment("flip", 5)
        self.assertEqual(tc.sent_commands[-1], ":SMT105#")

    def test_format_3_digits(self):
        tc = make_initialized_controller()
        tc.set_meredian_treatment("stop", 15)
        cmd = tc.sent_commands[-1]
        payload = cmd[4:-1]  # After :SMT, before #
        self.assertEqual(len(payload), 3)
        self.assertTrue(payload.isdigit())


class TestSetAltitudeLimit(unittest.TestCase):
    """Spec: :SALsnn# — sign + 2 digits, range [-89, +89]"""

    def test_positive_30(self):
        tc = make_initialized_controller()
        tc.set_altitude_limit(30)
        self.assertEqual(tc.sent_commands[-1], ":SAL+30#")

    def test_negative_5(self):
        tc = make_initialized_controller()
        tc.set_altitude_limit(-5)
        self.assertEqual(tc.sent_commands[-1], ":SAL-05#")

    def test_zero(self):
        tc = make_initialized_controller()
        tc.set_altitude_limit(0)
        self.assertEqual(tc.sent_commands[-1], ":SAL+00#")

    def test_format_sign_2_digits(self):
        tc = make_initialized_controller()
        tc.set_altitude_limit(7)
        cmd = tc.sent_commands[-1]
        payload = cmd[4:-1]  # After :SAL, before #
        self.assertIn(payload[0], ['+', '-'])
        self.assertEqual(len(payload[1:]), 2)
        self.assertTrue(payload[1:].isdigit())


class TestSetLatitude(unittest.TestCase):
    """Spec: :SLAsTTTTTTTT# — sign + 8 digits"""

    def test_positive_52(self):
        tc = make_initialized_controller()
        tc.set_latitude(52.0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLA+"))
        self.assertTrue(cmd.endswith("#"))
        payload = cmd[4:-1]  # sign + 8 digits
        self.assertEqual(len(payload), 9)  # sign + 8

    def test_negative_33(self):
        tc = make_initialized_controller()
        tc.set_latitude(-33.0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLA-"))

    def test_not_slo_command(self):
        """Latitude must use :SLA, not :SLO"""
        tc = make_initialized_controller()
        tc.set_latitude(52.0)
        cmd = tc.sent_commands[-1]
        self.assertFalse(cmd.startswith(":SLO"))
        self.assertTrue(cmd.startswith(":SLA"))


class TestSetLongitude(unittest.TestCase):
    """Spec: :SLOsTTTTTTTT# — sign + 8 digits"""

    def test_positive_east(self):
        tc = make_initialized_controller()
        tc.set_longitude(10.0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLO+"))

    def test_negative_west(self):
        tc = make_initialized_controller()
        tc.set_longitude(-2.35)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLO-"))

    def test_format(self):
        tc = make_initialized_controller()
        tc.set_longitude(0.0)
        cmd = tc.sent_commands[-1]
        payload = cmd[4:-1]
        self.assertEqual(len(payload), 9)  # sign + 8 digits


class TestSetTimezoneOffset(unittest.TestCase):
    """Spec: :SGsMMM# — sign + 3 digits"""

    def test_positive_60(self):
        tc = make_initialized_controller()
        tc.set_timezone_offset(60)
        self.assertEqual(tc.sent_commands[-1], ":SG+060#")

    def test_negative_300(self):
        tc = make_initialized_controller()
        tc.set_timezone_offset(-300)
        self.assertEqual(tc.sent_commands[-1], ":SG-300#")

    def test_zero(self):
        tc = make_initialized_controller()
        tc.set_timezone_offset(0)
        self.assertEqual(tc.sent_commands[-1], ":SG+000#")

    def test_format(self):
        tc = make_initialized_controller()
        tc.set_timezone_offset(60)
        cmd = tc.sent_commands[-1]
        payload = cmd[3:-1]  # After :SG, before #
        self.assertIn(payload[0], ['+', '-'])
        self.assertEqual(len(payload[1:]), 3)
        self.assertTrue(payload[1:].isdigit())


class TestSetCustomTrackingRate(unittest.TestCase):
    """Spec: :RRnnnnn# — 5 digits representing n.nnnn * sidereal"""

    def test_rate_1_0(self):
        tc = make_initialized_controller()
        tc.set_custom_tracking_rate(1.0)
        self.assertEqual(tc.sent_commands[-1], ":RR10000#")

    def test_rate_0_5(self):
        tc = make_initialized_controller()
        tc.set_custom_tracking_rate(0.5)
        self.assertEqual(tc.sent_commands[-1], ":RR05000#")

    def test_rate_1_5(self):
        tc = make_initialized_controller()
        tc.set_custom_tracking_rate(1.5)
        self.assertEqual(tc.sent_commands[-1], ":RR15000#")

    def test_format_5_digits(self):
        tc = make_initialized_controller()
        tc.set_custom_tracking_rate(1.0)
        cmd = tc.sent_commands[-1]
        payload = cmd[3:-1]
        self.assertEqual(len(payload), 5)
        self.assertTrue(payload.isdigit())


class TestSetGuidingRate(unittest.TestCase):
    """Spec: :RGnnnn# — 2 digits RA + 2 digits DEC"""

    def test_50_50(self):
        tc = make_initialized_controller()
        tc.set_guiding_rate(0.50, 0.50)
        self.assertEqual(tc.sent_commands[-1], ":RG5050#")

    def test_01_10(self):
        tc = make_initialized_controller()
        tc.set_guiding_rate(0.01, 0.10)
        self.assertEqual(tc.sent_commands[-1], ":RG0110#")

    def test_90_99(self):
        tc = make_initialized_controller()
        tc.set_guiding_rate(0.90, 0.99)
        self.assertEqual(tc.sent_commands[-1], ":RG9099#")

    def test_format_4_digits(self):
        tc = make_initialized_controller()
        tc.set_guiding_rate(0.50, 0.50)
        cmd = tc.sent_commands[-1]
        payload = cmd[3:-1]
        self.assertEqual(len(payload), 4)
        self.assertTrue(payload.isdigit())


class TestSetParkingPosition(unittest.TestCase):
    """Spec: :SPHTTTTTTTT# (8 digits alt), :SPATTTTTTTTT# (9 digits az)"""

    def test_parking_alt_format_8_digits(self):
        tc = make_initialized_controller()
        tc.set_parking_altitude(45, 0, 0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SPH"))
        payload = cmd[4:-1]
        self.assertEqual(len(payload), 8)
        self.assertTrue(payload.isdigit())

    def test_parking_az_format_9_digits(self):
        tc = make_initialized_controller()
        tc.set_parking_azimuth(180, 0, 0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SPA"))
        payload = cmd[4:-1]
        self.assertEqual(len(payload), 9)
        self.assertTrue(payload.isdigit())


class TestSetArrowSpeed(unittest.TestCase):
    """Spec: :SRn# — single digit 1-9"""

    def test_speed_5(self):
        tc = make_initialized_controller()
        tc.last_update = 0
        # Bypass update_status which tries to parse mock responses
        tc.update_status = lambda: None
        tc.set_arrow_button_movement_speed(5)
        self.assertEqual(tc.sent_commands[-1], ":SR5#")


class TestMiscCommands(unittest.TestCase):
    """Various simple commands"""

    def test_park(self):
        tc = make_initialized_controller()
        tc.park()
        self.assertEqual(tc.sent_commands[-1], ":MP1#")

    def test_unpark(self):
        tc = make_initialized_controller()
        tc.parking = type('P', (), {'is_parked': True})()
        tc.unpark()
        self.assertEqual(tc.sent_commands[-1], ":MP0#")

    def test_go_to_zero(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.go_to_zero_position()
        self.assertEqual(tc.sent_commands[-1], ":MH#")

    def test_stop_all(self):
        tc = make_controller()
        tc.is_slewing = True
        tc.stop_all_movement()
        self.assertEqual(tc.sent_commands[-1], ":Q#")

    def test_synchronize(self):
        tc = make_controller()
        tc.synchronize_mount()
        self.assertEqual(tc.sent_commands[-1], ":CM#")

    def test_set_zero_position(self):
        tc = make_controller()
        tc.set_current_position_as_zero()
        self.assertEqual(tc.sent_commands[-1], ":SZP#")

    def test_reset_settings(self):
        # Mock the status methods called after reset
        tc = make_initialized_controller()
        # Override methods that parse responses to avoid mock "1" being too short
        tc.get_all_kinds_of_status = lambda: None
        tc.get_time_information = lambda: None
        tc.get_ra_and_dec = lambda: None
        tc.get_alt_and_az = lambda: None
        tc.reset_settings(True)
        self.assertIn(":RAS#", tc.sent_commands)

    def test_set_hemisphere_north(self):
        tc = make_controller()
        tc.set_hemisphere('north')
        self.assertEqual(tc.sent_commands[-1], ":SHE1#")

    def test_set_hemisphere_south(self):
        tc = make_controller()
        tc.set_hemisphere('south')
        self.assertEqual(tc.sent_commands[-1], ":SHE0#")

    def test_set_dst_on(self):
        tc = make_initialized_controller()
        tc.get_time_information = lambda: None  # Avoid parsing mock "1"
        tc.set_daylight_savings(True)
        self.assertIn(":SDS1#", tc.sent_commands)

    def test_set_dst_off(self):
        tc = make_initialized_controller()
        tc.get_time_information = lambda: None
        tc.set_daylight_savings(False)
        self.assertIn(":SDS0#", tc.sent_commands)

    def test_set_max_speed_256(self):
        tc = make_controller()
        tc.set_max_slewing_speed('256x')
        self.assertEqual(tc.sent_commands[-1], ":MSR7#")

    def test_set_max_speed_512(self):
        tc = make_controller()
        tc.set_max_slewing_speed('512x')
        self.assertEqual(tc.sent_commands[-1], ":MSR8#")

    def test_set_max_speed_max(self):
        tc = make_controller()
        tc.set_max_slewing_speed('max')
        self.assertEqual(tc.sent_commands[-1], ":MSR9#")

    def test_pec_playback_enable(self):
        tc = make_initialized_controller()
        result = tc.enable_pec_playback(True)
        self.assertEqual(tc.sent_commands[-1], ":SPP1#")
        self.assertTrue(result)

    def test_pec_playback_disable(self):
        tc = make_initialized_controller()
        result = tc.enable_pec_playback(False)
        self.assertEqual(tc.sent_commands[-1], ":SPP0#")
        self.assertTrue(result)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING TESTS
# ═══════════════════════════════════════════════════════════════════
class TestParseGLS(unittest.TestCase):
    """Spec: :GLS# → sTTTTTTTTTTTTTTTTnnnnnn#
    sign+8 lon, 8 lat(+90°), gps, status, track, speed, time_src, hemisphere"""

    def test_parse_full_response(self):
        tc = make_initialized_controller()
        # GLS response: sTTTTTTTTTTTTTTTTnnnnnn
        # Longitude: -2.35° → -846000 in 0.01 arcsec → "-00846000" (sign + 8 digits = 9 chars)
        # Latitude: 52° + 90° = 142° → 51120000 (8 digits, no sign, +90 offset)
        # GPS: 2, Status: 1, Rate: 0, Speed: 5, TimeSource: 1, Hemisphere: 1
        response = "-00846000511200002105101"
        # Positions: [0:9]=lon, [9:17]=lat, [17]=gps, [18]=status, [19]=rate,
        #            [20]=speed, [21]=timesrc, [22]=hemisphere
        # That's 23 chars. Let me count: "-00846000" (9) + "51120000" (8) + "2105101" (7) = 24
        # Actually: lon=9, lat=8, gps=1, status=1, rate=1, speed=1, timesrc=1, hem=1 = 23
        response = "-0084600051120000210501"
        # Nope, need to be precise. The spec says sign + 22 digits = 23 chars total.
        # lon: sign+8 = 9 chars → response[0:9]
        # lat: 8 chars → response[9:17]
        # gps: 1 char → response[17:18]
        # status: 1 char → response[18:19]
        # rate: 1 char → response[19:20]
        # speed: 1 char → response[20:21]
        # timesrc: 1 char → response[21:22]
        # hemisphere: 1 char → response[22:23]
        # Total: 9+8+1+1+1+1+1+1 = 23 chars
        response = "-00846000" + "51120000" + "2" + "1" + "0" + "5" + "1" + "1"
        tc.send = lambda *args, **kw: response
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '1')
        self.assertTrue(tc.tracking.is_tracking)
        self.assertEqual(tc.hemisphere.location, 'n')


class TestParseGEP(unittest.TestCase):
    """Spec: :GEP# → sTTTTTTTTTTTTTTTTTnn#
    sign+8 dec, 9 ra, pier, pointing"""

    def test_parse_dec_positive(self):
        tc = make_initialized_controller()
        # GEP response: sTTTTTTTTTTTTTTTTTnn
        # Dec +45° = +16200000 (sign+8 = 9 chars)
        # RA 6h = 6*15° = 90° = 90*3600*100 = 32400000 (9 chars)
        # pier=1(west), cw=1(normal)
        response = "+16200000" + "032400000" + "1" + "1"
        tc.send = lambda *args, **kw: response
        tc.get_ra_and_dec()
        self.assertEqual(tc.declination.degrees, 45)
        self.assertEqual(tc.pier_side, 'west')


class TestParseGMT(unittest.TestCase):
    """Spec: :GMT# → nnn# — 1 digit code + 2 digit limit"""

    def test_parse_stop_at_0(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "000"
        tc.get_meredian_treatment()
        self.assertEqual(tc.meredian.code, 0)
        self.assertEqual(tc.meredian.degree_limit, 0)

    def test_parse_flip_at_10(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "110"
        tc.get_meredian_treatment()
        self.assertEqual(tc.meredian.code, 1)
        self.assertEqual(tc.meredian.degree_limit, 10)


# New tests appended below; __main__ block moved to end of file


def make_encoder_controller():
    """Create a controller configured as an equatorial mount WITH encoders (e.g. CEM70EC)."""
    tc = make_initialized_controller()
    tc.mount_config_data['capabilities']['encoders'] = True
    tc.mount_config_data['capabilities']['pec'] = False
    return tc


def make_altaz_controller():
    """Create a controller configured as an alt-az mount (non-equatorial)."""
    tc = make_initialized_controller()
    tc.mount_config_data['type'] = 'altaz'
    return tc


# ═══════════════════════════════════════════════════════════════════
# DATACLASS UNIT TESTS — Tracking, Meredian, Altitude
# ═══════════════════════════════════════════════════════════════════
class TestTrackingDataclass(unittest.TestCase):
    """Test Tracking.current_rate() branches."""

    def test_current_rate_not_tracking(self):
        from ioptron import Tracking
        t = Tracking()
        t.is_tracking = False
        self.assertEqual(t.current_rate(), "not tracking")

    def test_current_rate_code_set(self):
        from ioptron import Tracking
        t = Tracking()
        t.is_tracking = True
        t.code = 0
        t.available_rates = {0: 'sidereal', 1: 'lunar'}
        self.assertEqual(t.current_rate(), 'sidereal')

    def test_current_rate_code_none(self):
        from ioptron import Tracking
        t = Tracking()
        t.is_tracking = True
        t.code = None
        self.assertIsNone(t.current_rate())


class TestMeredianDataclass(unittest.TestCase):
    """Test Meredian.description() branches."""

    def test_description_stop(self):
        from ioptron import Meredian
        m = Meredian(code=0)
        self.assertEqual(m.description(), "Stop at meredian")

    def test_description_flip(self):
        from ioptron import Meredian
        m = Meredian(code=1)
        self.assertEqual(m.description(), "Flip at meredian with custom limit")

    def test_description_none(self):
        from ioptron import Meredian
        m = Meredian(code=None)
        self.assertEqual(m.description(), "Unknown or not set.")

    def test_description_unknown_code(self):
        from ioptron import Meredian
        m = Meredian(code=99)
        self.assertEqual(m.description(), "Unknown or not set.")


class TestAltitudeDataclass(unittest.TestCase):
    """Test Altitude.get_limit_str() padding."""

    def test_limit_str_single_digit(self):
        from ioptron import Altitude
        a = Altitude(limit=5)
        self.assertEqual(a.get_limit_str(), "005")

    def test_limit_str_two_digits(self):
        from ioptron import Altitude
        a = Altitude(limit=30)
        self.assertEqual(a.get_limit_str(), "030")

    def test_limit_str_three_digits(self):
        from ioptron import Altitude
        a = Altitude(limit=89)
        # zfill(3) on "89" → "089"
        self.assertEqual(a.get_limit_str(), "089")

    def test_limit_str_negative(self):
        from ioptron import Altitude
        a = Altitude(limit=-5)
        # str(-5) = "-5", zfill(3) = "-05" (zfill pads after sign to total width 3)
        self.assertEqual(a.get_limit_str(), "-05")

    def test_limit_str_negative_large(self):
        from ioptron import Altitude
        a = Altitude(limit=-89)
        self.assertEqual(a.get_limit_str(), "-89")


# ═══════════════════════════════════════════════════════════════════
# COMPREHENSIVE GLS STATUS PARSING — all status codes 0-7
# ═══════════════════════════════════════════════════════════════════
class TestParseGLSAllStatusCodes(unittest.TestCase):
    """Test get_all_kinds_of_status() with every status code 0-7."""

    def _make_gls_response(self, gps='2', status='0', rate='0', speed='5',
                           time_src='1', hemisphere='1'):
        """Build a 23-char GLS response with the given field values.
        Lon = +00360000 (1 degree), Lat = 65160000 (90.1 deg, i.e. 0.1 after -90 offset)."""
        lon = "+00360000"  # 9 chars
        lat = "65160000"   # 8 chars
        return lon + lat + gps + status + rate + speed + time_src + hemisphere

    def test_status_0_stopped_non_zero(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='0')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '0')
        self.assertIn("stopped at non-zero", tc.system_status.description)
        self.assertFalse(tc.is_slewing)
        self.assertFalse(tc.tracking.is_tracking)

    def test_status_1_tracking_pec_disabled(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='1')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '1')
        self.assertFalse(tc.is_slewing)
        self.assertTrue(tc.tracking.is_tracking)
        self.assertFalse(tc.pec.enabled)

    def test_status_2_slewing(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='2')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '2')
        self.assertTrue(tc.is_slewing)
        self.assertFalse(tc.tracking.is_tracking)

    def test_status_3_auto_guiding(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='3')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '3')
        self.assertFalse(tc.is_slewing)
        self.assertTrue(tc.tracking.is_tracking)

    def test_status_4_meridian_flipping(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='4')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '4')
        self.assertTrue(tc.is_slewing)

    def test_status_5_tracking_pec_enabled(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='5')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '5')
        self.assertFalse(tc.is_slewing)
        self.assertTrue(tc.tracking.is_tracking)
        self.assertTrue(tc.pec.enabled)

    def test_status_6_parked(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='6')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '6')
        self.assertFalse(tc.is_slewing)
        self.assertFalse(tc.tracking.is_tracking)
        self.assertTrue(tc.parking.is_parked)

    def test_status_7_stopped_at_zero(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(status='7')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.system_status.code, '7')
        self.assertFalse(tc.is_slewing)
        self.assertFalse(tc.tracking.is_tracking)

    # GPS states
    def test_gps_state_0_not_available(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(gps='0')
        tc.get_all_kinds_of_status()
        self.assertFalse(tc.location.gps_available)

    def test_gps_state_1_available_not_locked(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(gps='1')
        tc.get_all_kinds_of_status()
        self.assertTrue(tc.location.gps_available)
        self.assertFalse(tc.location.gps_locked)

    def test_gps_state_2_locked(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(gps='2')
        tc.get_all_kinds_of_status()
        self.assertTrue(tc.location.gps_available)
        self.assertTrue(tc.location.gps_locked)

    # Tracking rates
    def test_tracking_rate_parsed(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(rate='2')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.tracking.code, 2)

    def test_tracking_rate_4_custom(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(rate='4')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.tracking.code, 4)

    # Moving speeds
    def test_moving_speed_parsed(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(speed='3')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.moving_speed.code, '3')

    # Time sources
    def test_time_source_1_rs232(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(time_src='1')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.time_source.code, '1')
        self.assertIn("RS232", tc.time_source.description)

    def test_time_source_2_hand_controller(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(time_src='2')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.time_source.code, '2')
        self.assertIn("hand controller", tc.time_source.description)

    def test_time_source_3_gps(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(time_src='3')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.time_source.code, '3')
        self.assertIn("gps", tc.time_source.description)

    # Hemispheres
    def test_hemisphere_0_south(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(hemisphere='0')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.hemisphere.location, 's')

    def test_hemisphere_1_north(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: self._make_gls_response(hemisphere='1')
        tc.get_all_kinds_of_status()
        self.assertEqual(tc.hemisphere.location, 'n')


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_alt_and_az
# ═══════════════════════════════════════════════════════════════════
class TestParseGAC(unittest.TestCase):
    """Test get_alt_and_az() parsing of :GAC# response.
    Response format: 9 chars altitude + 9 chars azimuth (both in 0.01 arcsec)."""

    def test_parse_alt_and_az(self):
        tc = make_initialized_controller()
        # Alt = 16200000 (45 deg in 0.01 arcsec), Az = 064800000 (180 deg)
        response = "+16200000" + "064800000"
        tc.send = lambda *args, **kw: response
        tc.get_alt_and_az()
        self.assertEqual(tc.altitude.arcseconds, 16200000.0)
        self.assertEqual(tc.azimuth.arcseconds, 64800000.0)
        # DMS should be set
        self.assertIsNotNone(tc.altitude.degrees)
        self.assertIsNotNone(tc.azimuth.degrees)

    def test_parse_alt_zero_az_zero(self):
        tc = make_initialized_controller()
        response = "+00000000" + "000000000"
        tc.send = lambda *args, **kw: response
        tc.get_alt_and_az()
        self.assertEqual(tc.altitude.arcseconds, 0.0)
        self.assertEqual(tc.azimuth.arcseconds, 0.0)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_altitude_limit
# ═══════════════════════════════════════════════════════════════════
class TestParseGAL(unittest.TestCase):
    """Test get_altitude_limit() parsing of :GAL# response.
    Response format: snn (sign + 2 digits)."""

    def test_positive_limit(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "+30"
        result = tc.get_altitude_limit()
        self.assertEqual(result, 30)
        self.assertEqual(tc.altitude.limit, 30)

    def test_negative_limit(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "-05"
        result = tc.get_altitude_limit()
        self.assertEqual(result, -5)
        self.assertEqual(tc.altitude.limit, -5)

    def test_zero_limit(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "+00"
        result = tc.get_altitude_limit()
        self.assertEqual(result, 0)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_ra_and_dec (extended)
# ═══════════════════════════════════════════════════════════════════
class TestParseGEPExtended(unittest.TestCase):
    """Extended tests for get_ra_and_dec() — pier side, counterweight, truncated responses."""

    def test_pier_side_east(self):
        tc = make_initialized_controller()
        # Dec=0, RA=0, pier=0(east), cw=0(up)
        response = "+00000000" + "000000000" + "0" + "0"
        tc.send = lambda *args, **kw: response
        tc.get_ra_and_dec()
        self.assertEqual(tc.pier_side, 'east')
        self.assertEqual(tc.counterweight_direction, 'up')

    def test_pier_side_west(self):
        tc = make_initialized_controller()
        response = "+00000000" + "000000000" + "1" + "1"
        tc.send = lambda *args, **kw: response
        tc.get_ra_and_dec()
        self.assertEqual(tc.pier_side, 'west')
        self.assertEqual(tc.counterweight_direction, 'normal')

    def test_pier_side_intermediate(self):
        tc = make_initialized_controller()
        response = "+00000000" + "000000000" + "2" + "0"
        tc.send = lambda *args, **kw: response
        tc.get_ra_and_dec()
        self.assertEqual(tc.pier_side, 'intermediate')

    def test_truncated_response_no_pier_side(self):
        """When response is only 18 chars (dec+ra), pier_side fields are empty strings."""
        tc = make_initialized_controller()
        # Only dec (9) + ra (9) = 18 chars, no pier/cw fields
        response = "+00000000" + "000000000"
        tc.send = lambda *args, **kw: response
        tc.pier_side = 'previous_value'
        tc.get_ra_and_dec()
        # pier_side slice [18:19] returns "" which is not .isdigit(), so pier_side unchanged
        self.assertEqual(tc.pier_side, 'previous_value')

    def test_negative_declination(self):
        tc = make_initialized_controller()
        # Dec = -45 deg = -16200000
        response = "-16200000" + "000000000" + "1" + "1"
        tc.send = lambda *args, **kw: response
        tc.get_ra_and_dec()
        self.assertEqual(tc.declination.arcseconds, -16200000.0)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_time_information
# ═══════════════════════════════════════════════════════════════════
class TestParseGUT(unittest.TestCase):
    """Test get_time_information() parsing of :GUT# response.
    Response format: sMMM + D + 13-digit J2K = 18 chars total.
    sMMM = signed 3-digit UTC offset in minutes, D = DST flag (0/1),
    13 digits = J2000 time in 0.001 seconds."""

    def test_parse_time_info(self):
        tc = make_initialized_controller()
        # UTC offset = +060 (UTC+1), DST = 0, J2K = 0000770000000 (arbitrary)
        response = "+060" + "0" + "0000770000000"
        tc.send = lambda *args, **kw: response
        tc.get_time_information()
        self.assertEqual(tc.time.utc_offset, 60)
        self.assertFalse(tc.time.dst)
        self.assertIsNotNone(tc.time.unix_utc)

    def test_parse_time_dst_on(self):
        tc = make_initialized_controller()
        response = "-300" + "1" + "0000770000000"
        tc.send = lambda *args, **kw: response
        tc.get_time_information()
        self.assertEqual(tc.time.utc_offset, -300)
        self.assertTrue(tc.time.dst)

    def test_parse_time_stale_byte_retry(self):
        """When response doesn't start with +/-, the code retries."""
        tc = make_initialized_controller()
        call_count = [0]
        def mock_send(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return "1+06000000770000000"  # 19 chars, starts with '1' not +/-
            return "+060" + "0" + "0000770000000"
        tc.send = mock_send
        tc.get_time_information()
        self.assertEqual(call_count[0], 2)
        self.assertEqual(tc.time.utc_offset, 60)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_custom_tracking_rate
# ═══════════════════════════════════════════════════════════════════
class TestParseGTR(unittest.TestCase):
    """Test get_custom_tracking_rate() parsing of :GTR# response.
    Response: 5 digits representing n.nnnn * 10000."""

    def test_parse_rate_1_0(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "10000"
        tc.get_custom_tracking_rate()
        self.assertEqual(tc.tracking.custom, '1.0000')

    def test_parse_rate_0_5(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "05000"
        tc.get_custom_tracking_rate()
        self.assertEqual(tc.tracking.custom, '0.5000')

    def test_parse_rate_1_5(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "15000"
        tc.get_custom_tracking_rate()
        self.assertEqual(tc.tracking.custom, '1.5000')


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_guiding_rate
# ═══════════════════════════════════════════════════════════════════
class TestParseAG(unittest.TestCase):
    """Test get_guiding_rate() parsing of :AG# response.
    Response: 4 digits — 2 for RA rate, 2 for DEC rate (each * 100)."""

    def test_parse_50_50(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "5050"
        tc.get_guiding_rate()
        self.assertAlmostEqual(tc.guiding.right_ascention_rate, 0.50)
        self.assertAlmostEqual(tc.guiding.declination_rate, 0.50)

    def test_parse_01_99(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0199"
        tc.get_guiding_rate()
        self.assertAlmostEqual(tc.guiding.right_ascention_rate, 0.01)
        self.assertAlmostEqual(tc.guiding.declination_rate, 0.99)

    def test_parse_90_10(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "9010"
        tc.get_guiding_rate()
        self.assertAlmostEqual(tc.guiding.right_ascention_rate, 0.90)
        self.assertAlmostEqual(tc.guiding.declination_rate, 0.10)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_pec_integrity
# ═══════════════════════════════════════════════════════════════════
class TestParsePECIntegrity(unittest.TestCase):
    """Test get_pec_integrity() parsing of :GPE# response."""

    def test_pec_incomplete(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        tc.get_pec_integrity()
        self.assertFalse(tc.pec.integrity_complete)

    def test_pec_complete(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        tc.get_pec_integrity()
        self.assertTrue(tc.pec.integrity_complete)

    def test_pec_integrity_encoder_mount_returns_early(self):
        """Encoder mounts should return early without sending command."""
        tc = make_encoder_controller()
        tc.send = lambda *args, **kw: "1"
        tc.get_pec_integrity()
        # pec.integrity_complete should remain None (not set)
        self.assertIsNone(tc.pec.integrity_complete)

    def test_pec_integrity_altaz_mount_returns_early(self):
        """Alt-az mounts should return early without sending command."""
        tc = make_altaz_controller()
        tc.send = lambda *args, **kw: "1"
        tc.get_pec_integrity()
        self.assertIsNone(tc.pec.integrity_complete)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_pec_recording_status
# ═══════════════════════════════════════════════════════════════════
class TestParsePECRecording(unittest.TestCase):
    """Test get_pec_recording_status() parsing of :GPR# response."""

    def test_pec_not_recording(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        tc.get_pec_recording_status()
        self.assertFalse(tc.pec.recording)

    def test_pec_recording(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        tc.get_pec_recording_status()
        self.assertTrue(tc.pec.recording)

    def test_pec_recording_encoder_mount_returns_early(self):
        tc = make_encoder_controller()
        tc.send = lambda *args, **kw: "1"
        tc.get_pec_recording_status()
        self.assertIsNone(tc.pec.recording)

    def test_pec_recording_altaz_mount_returns_early(self):
        tc = make_altaz_controller()
        tc.send = lambda *args, **kw: "1"
        tc.get_pec_recording_status()
        self.assertIsNone(tc.pec.recording)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_max_slewing_speed
# ═══════════════════════════════════════════════════════════════════
class TestParseGSR(unittest.TestCase):
    """Test get_max_slewing_speed() parsing of :GSR# response."""

    def test_speed_7_returns_256(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "7"
        result = tc.get_max_slewing_speed()
        self.assertEqual(result, 256)

    def test_speed_8_returns_512(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "8"
        result = tc.get_max_slewing_speed()
        self.assertEqual(result, 512)

    def test_speed_9_returns_mount_max(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "9"
        result = tc.get_max_slewing_speed()
        # CEM120 max is 900
        self.assertEqual(result, 900)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_meredian_treatment (extended)
# ═══════════════════════════════════════════════════════════════════
class TestParseGMTExtended(unittest.TestCase):
    """Extended tests for get_meredian_treatment() — truncated/garbled responses."""

    def test_non_equatorial_returns_early(self):
        tc = make_altaz_controller()
        tc.send = lambda *args, **kw: "000"
        tc.get_meredian_treatment()
        # meredian should remain at defaults (None)
        self.assertIsNone(tc.meredian.code)
        self.assertIsNone(tc.meredian.degree_limit)

    def test_garbled_code_non_digit(self):
        """If code field is not a digit, meredian.code should not be set."""
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "x10"
        tc.get_meredian_treatment()
        self.assertIsNone(tc.meredian.code)
        # degrees "10" is still digit
        self.assertEqual(tc.meredian.degree_limit, 10)

    def test_garbled_degrees_non_digit(self):
        """If degrees field is not a digit, meredian.degree_limit should not be set."""
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1xx"
        tc.get_meredian_treatment()
        self.assertEqual(tc.meredian.code, 1)
        self.assertIsNone(tc.meredian.degree_limit)

    def test_empty_response(self):
        """Empty response should not crash."""
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: ""
        tc.get_meredian_treatment()
        self.assertIsNone(tc.meredian.code)
        self.assertIsNone(tc.meredian.degree_limit)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_parking_position
# ═══════════════════════════════════════════════════════════════════
class TestParseGPC(unittest.TestCase):
    """Test get_parking_position() parsing of :GPC# response.
    Response: 8 digits altitude + 9 digits azimuth."""

    def test_parse_parking_position(self):
        tc = make_initialized_controller()
        # Alt = 16200000 (45 deg), Az = 064800000 (180 deg)
        response = "16200000" + "064800000"
        tc.send = lambda *args, **kw: response
        tc.get_parking_position()
        self.assertEqual(tc.parking.altitude.arcseconds, 16200000.0)
        self.assertEqual(tc.parking.azimuth.arcseconds, 64800000.0)
        self.assertIsNotNone(tc.parking.altitude.degrees)
        self.assertIsNotNone(tc.parking.azimuth.degrees)

    def test_parse_parking_zero(self):
        tc = make_initialized_controller()
        response = "00000000" + "000000000"
        tc.send = lambda *args, **kw: response
        tc.get_parking_position()
        self.assertEqual(tc.parking.altitude.arcseconds, 0.0)
        self.assertEqual(tc.parking.azimuth.arcseconds, 0.0)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_ra_guiding_filter_status
# ═══════════════════════════════════════════════════════════════════
class TestParseGGF(unittest.TestCase):
    """Test get_ra_guiding_filter_status() — only for encoder mounts."""

    def test_filter_disabled(self):
        tc = make_encoder_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.get_ra_guiding_filter_status()
        self.assertFalse(result)
        self.assertFalse(tc.guiding.ra_filter_enabled)
        self.assertTrue(tc.guiding.has_ra_filter)

    def test_filter_enabled(self):
        tc = make_encoder_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.get_ra_guiding_filter_status()
        self.assertTrue(result)
        self.assertTrue(tc.guiding.ra_filter_enabled)

    def test_non_encoder_mount_returns_none(self):
        """Non-encoder eq mount should return None."""
        tc = make_initialized_controller()  # encoders=False
        result = tc.get_ra_guiding_filter_status()
        self.assertIsNone(result)

    def test_altaz_mount_returns_none(self):
        tc = make_altaz_controller()
        result = tc.get_ra_guiding_filter_status()
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSING — get_coordinate_memory
# ═══════════════════════════════════════════════════════════════════
class TestParseQAP(unittest.TestCase):
    """Test get_coordinate_memory() parsing of :QAP# response."""

    def test_memory_0(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.get_coordinate_memory()
        self.assertEqual(result, "0")
        self.assertEqual(tc.tracking.memory_store, "0")

    def test_memory_1(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.get_coordinate_memory()
        self.assertEqual(result, "1")

    def test_memory_2(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "2"
        result = tc.get_coordinate_memory()
        self.assertEqual(result, "2")


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — _move_in_cardinal_direction response handling
# ═══════════════════════════════════════════════════════════════════
class TestCardinalDirectionResponse(unittest.TestCase):
    """Test _move_in_cardinal_direction response — returns True on '1', False otherwise."""

    def test_move_north_success(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.move_north()
        self.assertTrue(result)

    def test_move_always_returns_true(self):
        """Spec says :mn# etc have no response - method always returns True."""
        tc = make_controller()
        self.assertTrue(tc.move_north())
        self.assertTrue(tc.move_south())
        self.assertTrue(tc.move_east())
        self.assertTrue(tc.move_west())


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — move_to_defined_alt_and_az
# ═══════════════════════════════════════════════════════════════════
class TestMoveToDefinedAltAz(unittest.TestCase):
    """Test move_to_defined_alt_and_az() response handling."""

    def test_success(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.move_to_defined_alt_and_az()
        self.assertTrue(result)

    def test_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.move_to_defined_alt_and_az()
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — park response handling
# ═══════════════════════════════════════════════════════════════════


class TestSlewToRaDec(unittest.TestCase):
    """Test slew_to_ra_dec() — Spec: :MS1# (normal/counterweight-down position)"""

    def test_command_format(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.slew_to_ra_dec()
        self.assertEqual(tc.sent_commands[-1], ":MS1#")

    def test_success_sets_slewing(self):
        tc = make_controller()
        tc.is_slewing = False
        result = tc.slew_to_ra_dec()
        self.assertTrue(result)
        self.assertTrue(tc.is_slewing)

    def test_failure_below_limit(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.send = lambda *a, **kw: "0"
        result = tc.slew_to_ra_dec()
        self.assertFalse(result)
        self.assertFalse(tc.is_slewing)


class TestSlewToRaDecCounterweightUp(unittest.TestCase):
    """Test slew_to_ra_dec_counterweight_up() — Spec: :MS2# (counterweight-up)"""

    def test_command_format(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.slew_to_ra_dec_counterweight_up()
        self.assertEqual(tc.sent_commands[-1], ":MS2#")

    def test_success_sets_slewing(self):
        tc = make_controller()
        tc.is_slewing = False
        result = tc.slew_to_ra_dec_counterweight_up()
        self.assertTrue(result)
        self.assertTrue(tc.is_slewing)

    def test_failure_below_limit(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.send = lambda *a, **kw: "0"
        result = tc.slew_to_ra_dec_counterweight_up()
        self.assertFalse(result)
        self.assertFalse(tc.is_slewing)

class TestParkResponse(unittest.TestCase):
    """Test park() response — '1' means success, anything else means failure."""

    def test_park_success(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.park()
        self.assertTrue(result)
        self.assertTrue(tc.parking.is_parked)

    def test_park_failure(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.park()
        self.assertFalse(result)
        self.assertFalse(tc.parking.is_parked)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — enable_pec_playback mount type guards
# ═══════════════════════════════════════════════════════════════════
class TestEnablePecPlaybackGuards(unittest.TestCase):
    """Test enable_pec_playback() returns False for non-eq and encoder mounts."""

    def test_non_equatorial_returns_false(self):
        tc = make_altaz_controller()
        result = tc.enable_pec_playback(True)
        self.assertFalse(result)

    def test_encoder_mount_returns_false(self):
        tc = make_encoder_controller()
        result = tc.enable_pec_playback(True)
        self.assertFalse(result)

    def test_equatorial_no_encoder_enable(self):
        tc = make_initialized_controller()
        result = tc.enable_pec_playback(True)
        self.assertTrue(result)

    def test_equatorial_no_encoder_disable(self):
        tc = make_initialized_controller()
        result = tc.enable_pec_playback(False)
        self.assertTrue(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_meredian_treatment mount type guard
# ═══════════════════════════════════════════════════════════════════
class TestSetMeridianTreatmentGuard(unittest.TestCase):
    """Test set_meredian_treatment() returns False for non-equatorial mounts."""

    def test_altaz_returns_false(self):
        tc = make_altaz_controller()
        result = tc.set_meredian_treatment("stop", 0)
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_guiding_rate boundary values
# ═══════════════════════════════════════════════════════════════════
class TestSetGuidingRateBoundary(unittest.TestCase):
    """Test set_guiding_rate() at boundary values."""

    def test_min_ra_min_dec(self):
        tc = make_initialized_controller()
        tc.set_guiding_rate(0.01, 0.10)
        self.assertEqual(tc.sent_commands[-1], ":RG0110#")

    def test_max_ra_max_dec(self):
        tc = make_initialized_controller()
        tc.set_guiding_rate(0.90, 0.99)
        self.assertEqual(tc.sent_commands[-1], ":RG9099#")

    def test_ra_below_min_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_guiding_rate(0.00, 0.50)

    def test_dec_below_min_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_guiding_rate(0.50, 0.09)

    def test_ra_above_max_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_guiding_rate(0.91, 0.50)

    def test_dec_above_max_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_guiding_rate(0.50, 1.00)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_latitude / set_longitude boundary values
# ═══════════════════════════════════════════════════════════════════
class TestSetLatLongBoundary(unittest.TestCase):
    """Test set_latitude and set_longitude at boundary values."""

    def test_latitude_positive_90(self):
        tc = make_initialized_controller()
        tc.set_latitude(90.0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLA+"))

    def test_latitude_negative_90(self):
        tc = make_initialized_controller()
        tc.set_latitude(-90.0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLA-"))

    def test_latitude_out_of_range_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_latitude(91.0)

    def test_latitude_below_range_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_latitude(-91.0)

    def test_longitude_positive_180(self):
        tc = make_initialized_controller()
        tc.set_longitude(180.0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLO+"))

    def test_longitude_negative_180(self):
        tc = make_initialized_controller()
        tc.set_longitude(-180.0)
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SLO-"))

    def test_longitude_out_of_range_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_longitude(181.0)

    def test_longitude_below_range_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_longitude(-181.0)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_altitude_limit boundary values
# ═══════════════════════════════════════════════════════════════════
class TestSetAltitudeLimitBoundary(unittest.TestCase):
    """Test set_altitude_limit at boundary values."""

    def test_max_positive(self):
        tc = make_initialized_controller()
        tc.set_altitude_limit(89)
        self.assertEqual(tc.sent_commands[-1], ":SAL+89#")

    def test_max_negative(self):
        tc = make_initialized_controller()
        tc.set_altitude_limit(-89)
        self.assertEqual(tc.sent_commands[-1], ":SAL-89#")

    def test_above_max_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_altitude_limit(90)

    def test_below_min_raises(self):
        tc = make_initialized_controller()
        with self.assertRaises(AssertionError):
            tc.set_altitude_limit(-90)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_ra_guiding_filter_status
# ═══════════════════════════════════════════════════════════════════
class TestSetRAGuidingFilter(unittest.TestCase):
    """Test set_ra_guiding_filter_status() — only for encoder mounts."""

    def test_enable_on_encoder_mount(self):
        tc = make_encoder_controller()
        result = tc.set_ra_guiding_filter_status(True)
        self.assertTrue(result)
        self.assertTrue(tc.guiding.ra_filter_enabled)

    def test_disable_on_encoder_mount(self):
        tc = make_encoder_controller()
        result = tc.set_ra_guiding_filter_status(False)
        self.assertTrue(result)
        self.assertFalse(tc.guiding.ra_filter_enabled)

    def test_non_encoder_returns_none(self):
        tc = make_initialized_controller()  # encoders=False
        result = tc.set_ra_guiding_filter_status(True)
        self.assertIsNone(result)

    def test_altaz_returns_none(self):
        tc = make_altaz_controller()
        result = tc.set_ra_guiding_filter_status(True)
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — _toggle_pec_recording
# ═══════════════════════════════════════════════════════════════════
class TestTogglePecRecording(unittest.TestCase):
    """Test _toggle_pec_recording() mount type guards."""

    def test_start_recording_eq_mount(self):
        tc = make_initialized_controller()
        tc._toggle_pec_recording(True)
        self.assertIn(":SPR1#", tc.sent_commands)

    def test_stop_recording_eq_mount(self):
        tc = make_initialized_controller()
        tc._toggle_pec_recording(False)
        self.assertIn(":SPR0#", tc.sent_commands)

    def test_encoder_mount_no_command_sent(self):
        tc = make_encoder_controller()
        tc._toggle_pec_recording(True)
        # No SPR command should be sent
        spr_commands = [c for c in tc.sent_commands if 'SPR' in c]
        self.assertEqual(len(spr_commands), 0)

    def test_altaz_mount_no_command_sent(self):
        tc = make_altaz_controller()
        tc._toggle_pec_recording(True)
        spr_commands = [c for c in tc.sent_commands if 'SPR' in c]
        self.assertEqual(len(spr_commands), 0)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — refresh_status throttling
# ═══════════════════════════════════════════════════════════════════
class TestRefreshStatusThrottle(unittest.TestCase):
    """Test refresh_status() throttling — returns False if called within 1 second."""

    def test_throttle_returns_false(self):
        import time as time_mod
        tc = make_initialized_controller()
        tc.last_update = time_mod.time()  # Just updated
        result = tc.refresh_status()
        self.assertFalse(result)

    def test_stale_update_refreshes(self):
        import time as time_mod
        tc = make_initialized_controller()
        tc.last_update = time_mod.time() - 2  # 2 seconds ago
        # Override the get_* methods to avoid parsing mock "1"
        tc.get_all_kinds_of_status = lambda: None
        tc.get_alt_and_az = lambda: None
        tc.get_ra_and_dec = lambda: None
        tc.get_time_information = lambda: None
        result = tc.refresh_status()
        self.assertTrue(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — parse_moving_speed
# ═══════════════════════════════════════════════════════════════════
class TestParseMovingSpeed(unittest.TestCase):
    """Test parse_moving_speed() returns correct string."""

    def test_rate_1(self):
        tc = make_initialized_controller()
        result = tc.parse_moving_speed(1)
        self.assertEqual(result, "1x")

    def test_rate_9(self):
        tc = make_initialized_controller()
        result = tc.parse_moving_speed(9)
        self.assertEqual(result, "900x")


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — synchronize_mount response
# ═══════════════════════════════════════════════════════════════════
class TestSynchronizeResponse(unittest.TestCase):
    """Test synchronize_mount() response handling."""

    def test_success(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.synchronize_mount()
        self.assertTrue(result)

    def test_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.synchronize_mount()
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_current_position_as_zero response
# ═══════════════════════════════════════════════════════════════════
class TestSetZeroPositionResponse(unittest.TestCase):
    """Test set_current_position_as_zero() response handling."""

    def test_success(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.set_current_position_as_zero()
        self.assertTrue(result)

    def test_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_current_position_as_zero()
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — start_tracking / stop_tracking response
# ═══════════════════════════════════════════════════════════════════
class TestTrackingResponse(unittest.TestCase):
    """Test start_tracking/stop_tracking response handling."""

    def test_start_tracking_success(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.start_tracking()
        self.assertTrue(result)

    def test_start_tracking_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.start_tracking()
        self.assertFalse(result)

    def test_stop_tracking_success(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.stop_tracking()
        self.assertTrue(result)

    def test_stop_tracking_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.stop_tracking()
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_tracking_rate response
# ═══════════════════════════════════════════════════════════════════
class TestSetTrackingRateResponse(unittest.TestCase):
    """Test set_tracking_rate() response handling."""

    def test_success(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.set_tracking_rate('sidereal')
        self.assertTrue(result)

    def test_failure(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_tracking_rate('sidereal')
        self.assertFalse(result)

    def test_all_rates(self):
        """Test all supported tracking rates."""
        tc = make_initialized_controller()
        for rate_name in ['sidereal', 'lunar', 'solar', 'king', 'custom']:
            tc.send = lambda *args, **kw: "1"
            result = tc.set_tracking_rate(rate_name)
            self.assertTrue(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — _set_commanded_axis_from_dms response handling
# ═══════════════════════════════════════════════════════════════════
class TestSetCommandedAxisResponse(unittest.TestCase):
    """Test _set_commanded_axis_from_dms returns False when response is not '1'."""

    def test_ra_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_commanded_right_ascension(0, 0, 0)
        self.assertFalse(result)

    def test_dec_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_commanded_declination(0, 0, 0)
        self.assertFalse(result)

    def test_alt_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_commanded_altitude(0, 0, 0)
        self.assertFalse(result)

    def test_az_failure(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_commanded_azimuth(0, 0, 0)
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_meredian_treatment response
# ═══════════════════════════════════════════════════════════════════
class TestSetMeridianTreatmentResponse(unittest.TestCase):
    """Test set_meredian_treatment() response handling."""

    def test_success(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.set_meredian_treatment("stop", 0)
        self.assertTrue(result)

    def test_failure(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_meredian_treatment("stop", 0)
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_parking_altitude / set_parking_azimuth response
# ═══════════════════════════════════════════════════════════════════
class TestSetParkingResponse(unittest.TestCase):
    """Test set_parking_altitude/azimuth response handling."""

    def test_parking_alt_success(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.set_parking_altitude(45, 0, 0)
        self.assertTrue(result)

    def test_parking_alt_failure(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_parking_altitude(45, 0, 0)
        self.assertFalse(result)

    def test_parking_az_success(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.set_parking_azimuth(180, 0, 0)
        self.assertTrue(result)

    def test_parking_az_failure(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_parking_azimuth(180, 0, 0)
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — set_latitude / set_longitude response
# ═══════════════════════════════════════════════════════════════════
class TestSetLatLongResponse(unittest.TestCase):
    """Test set_latitude/set_longitude response handling."""

    def test_latitude_success(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.set_latitude(52.0)
        self.assertTrue(result)

    def test_latitude_failure(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_latitude(52.0)
        self.assertFalse(result)

    def test_longitude_success(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "1"
        result = tc.set_longitude(10.0)
        self.assertTrue(result)

    def test_longitude_failure(self):
        tc = make_initialized_controller()
        tc.send = lambda *args, **kw: "0"
        result = tc.set_longitude(10.0)
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — unpark
# ═══════════════════════════════════════════════════════════════════
class TestUnpark(unittest.TestCase):
    """Test unpark() always sets is_parked to False."""

    def test_unpark_sets_not_parked(self):
        tc = make_initialized_controller()
        tc.parking.is_parked = True
        result = tc.unpark()
        self.assertFalse(result)  # unpark returns self.parking.is_parked which is False
        self.assertFalse(tc.parking.is_parked)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — go_to_zero_position sets is_slewing
# ═══════════════════════════════════════════════════════════════════
class TestGoToZero(unittest.TestCase):
    """Test go_to_zero_position() sets is_slewing."""

    def test_sets_slewing(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.go_to_zero_position()
        self.assertTrue(tc.is_slewing)


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — reset_settings with False does nothing
# ═══════════════════════════════════════════════════════════════════
class TestResetSettingsGuard(unittest.TestCase):
    """Test reset_settings(False) does not send any commands."""

    def test_false_does_nothing(self):
        tc = make_initialized_controller()
        tc.reset_settings(False)
        self.assertEqual(len(tc.sent_commands), 0)




# ═══════════════════════════════════════════════════════════════════
# FIRMWARE AND VERSION PARSING
# ═══════════════════════════════════════════════════════════════════
class TestFirmwareParsing(unittest.TestCase):
    """Test get_main_firmwares, get_motor_firmwares, get_mount_version."""

    def test_get_main_firmwares(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "210101xxxxxx"
        result = tc.get_main_firmwares()
        self.assertEqual(result, ("210101", "xxxxxx"))

    def test_get_main_firmwares_with_hc(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "210101200501"
        result = tc.get_main_firmwares()
        self.assertEqual(result, ("210101", "200501"))

    def test_get_motor_firmwares(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "210101210101"
        result = tc.get_motor_firmwares()
        self.assertEqual(result, ("210101", "210101"))

    def test_get_mount_version(self):
        tc = make_controller()
        tc.send = lambda *args, **kw: "0120"
        result = tc.get_mount_version()
        self.assertEqual(result, "0120")


class TestGoToMechanicalZero(unittest.TestCase):
    """Test go_to_mechanical_zero_position()."""

    def test_supported_mount(self):
        tc = make_initialized_controller()
        tc.mount_config_data['mechanical_zero'] = True
        tc.is_slewing = False
        tc.go_to_mechanical_zero_position()
        self.assertIn(":MSH#", tc.sent_commands)
        self.assertTrue(tc.is_slewing)

    def test_unsupported_mount(self):
        tc = make_initialized_controller()
        tc.mount_config_data['mechanical_zero'] = False
        tc.is_slewing = False
        tc.go_to_mechanical_zero_position()
        self.assertNotIn(":MSH#", tc.sent_commands)
        self.assertFalse(tc.is_slewing)


class TestPecRecordingMethods(unittest.TestCase):
    """Test start_recording_pec and stop_recording_pec return values."""

    def test_start_recording_success(self):
        tc = make_initialized_controller()
        result = tc.start_recording_pec()
        self.assertTrue(result)

    def test_stop_recording_success(self):
        tc = make_initialized_controller()
        result = tc.stop_recording_pec()
        self.assertTrue(result)

    def test_start_recording_non_eq_returns_false(self):
        tc = make_altaz_controller()
        result = tc.start_recording_pec()
        self.assertFalse(result)


class TestUpdateStatus(unittest.TestCase):
    """Test update_status() calls get_* methods when stale."""

    def test_stale_calls_get_methods(self):
        import time as time_mod
        tc = make_initialized_controller()
        tc.last_update = time_mod.time() - 2
        calls = []
        tc.get_all_kinds_of_status = lambda: calls.append('gls')
        tc.get_time_information = lambda: calls.append('gut')
        tc.get_ra_and_dec = lambda: calls.append('gep')
        tc.update_status()
        self.assertIn('gls', calls)
        self.assertIn('gut', calls)
        self.assertIn('gep', calls)

    def test_recent_skips_get_methods(self):
        import time as time_mod
        tc = make_initialized_controller()
        tc.last_update = time_mod.time()
        calls = []
        tc.get_all_kinds_of_status = lambda: calls.append('gls')
        tc.update_status()
        self.assertEqual(len(calls), 0)


class TestSetTime(unittest.TestCase):
    """Test set_time() sends :SUT command with 13-digit J2K time."""

    def test_set_time_command_format(self):
        tc = make_initialized_controller()
        tc.set_time()
        cmd = tc.sent_commands[-1]
        self.assertTrue(cmd.startswith(":SUT"))
        self.assertTrue(cmd.endswith("#"))
        payload = cmd[4:-1]
        self.assertEqual(len(payload), 13)
        self.assertTrue(payload.isdigit())



# ═══════════════════════════════════════════════════════════════════
# REFACTORING VERIFICATION — is_home, stop commands, update_status
# ═══════════════════════════════════════════════════════════════════
class TestIsHomeTracking(unittest.TestCase):
    """Test that is_home is set correctly by get_all_kinds_of_status."""

    def _make_gls(self, status='7'):
        return "+00360000" + "65160000" + "2" + status + "0" + "5" + "1" + "1"

    def test_status_7_sets_is_home_true(self):
        tc = make_initialized_controller()
        tc.is_home = False
        tc.send = lambda *a, **kw: self._make_gls(status='7')
        tc.get_all_kinds_of_status()
        self.assertTrue(tc.is_home)

    def test_status_0_sets_is_home_false(self):
        tc = make_initialized_controller()
        tc.is_home = True
        tc.send = lambda *a, **kw: self._make_gls(status='0')
        tc.get_all_kinds_of_status()
        self.assertFalse(tc.is_home)

    def test_status_1_sets_is_home_false(self):
        tc = make_initialized_controller()
        tc.is_home = True
        tc.send = lambda *a, **kw: self._make_gls(status='1')
        tc.get_all_kinds_of_status()
        self.assertFalse(tc.is_home)


class TestStopCommandsDoNotAffectSlewing(unittest.TestCase):
    """Per spec, :qR# and :qD# only stop arrow-button movement,
    not GoTo slews. is_slewing should NOT be changed."""

    def test_stop_ew_preserves_slewing_true(self):
        tc = make_controller()
        tc.is_slewing = True
        tc.stop_e_or_w_movement()
        self.assertTrue(tc.is_slewing)

    def test_stop_ew_preserves_slewing_false(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.stop_e_or_w_movement()
        self.assertFalse(tc.is_slewing)

    def test_stop_ns_preserves_slewing_true(self):
        tc = make_controller()
        tc.is_slewing = True
        tc.stop_n_or_s_movement()
        self.assertTrue(tc.is_slewing)

    def test_stop_ns_preserves_slewing_false(self):
        tc = make_controller()
        tc.is_slewing = False
        tc.stop_n_or_s_movement()
        self.assertFalse(tc.is_slewing)


class TestSetArrowSpeedNoUpdateStatus(unittest.TestCase):
    """set_arrow_button_movement_speed should NOT call update_status."""

    def test_no_update_status_call(self):
        tc = make_initialized_controller()
        update_called = [False]
        original_update = tc.update_status
        tc.update_status = lambda: update_called.__setitem__(0, True)
        tc.set_arrow_button_movement_speed(5)
        self.assertFalse(update_called[0])


class TestUpdateStatusIncludesAltAz(unittest.TestCase):
    """update_status should call get_alt_and_az (was previously missing)."""

    def test_calls_get_alt_and_az(self):
        import time as time_mod
        tc = make_initialized_controller()
        tc.last_update = time_mod.time() - 2
        calls = []
        tc.get_all_kinds_of_status = lambda: calls.append('gls')
        tc.get_time_information = lambda: calls.append('gut')
        tc.get_ra_and_dec = lambda: calls.append('gep')
        tc.get_alt_and_az = lambda: calls.append('gac')
        tc.update_status()
        self.assertIn('gac', calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
