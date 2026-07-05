import socket
import select
from dataclasses import dataclass, field
try:
    from ioptron import utils
except ImportError:
    import utils
import time
import logging
try:
    from ioptron.const import LOGLEVEL
except ImportError:
    from const import LOGLEVEL
import os

# Data classes
@dataclass
class Altitude:
    """An altitude position. Contains the arcseconds and DMS."""
    arcseconds: float = None
    degrees: float = None
    minutes: int = None
    seconds: float = None
    limit: int = None

    def get_limit_str(self):
        """Get the altitude limit, appropriately padded."""
        return str(self.limit).zfill(3)

@dataclass
class Azimuth:
    """An azimuth position. Contains the arcseconds and DMS."""
    arcseconds: float = None
    degrees: float = None
    minutes: int = None
    seconds: float = None

@dataclass
class DEC:
    """Information about a declination value."""
    arcseconds: float = None
    degrees: int = None
    minutes: int = None
    seconds: float = None

@dataclass
class Firmwares:
    """Information on the firmware istalled on the mount and components."""
    mainboard: str = None
    hand_controller: str = None
    right_ascention: str = None
    declination: str = None

@dataclass
class Location:
    """Holds location information along with GPS data."""
    gps_available: bool = False
    gps_locked: bool = False
    longitude: float = None
    latitude: float = None

@dataclass
class Guiding:
    """Informationa bout the RA and dec guiding rate. Can be 0.01 - 0.99.
    Represents the rate * siderial rate."""
    right_ascention_rate: float = None
    declination_rate: float = None
    ra_filter_enabled: bool = None
    has_ra_filter: bool = False

@dataclass
class RA:
    """Right ascension (RA) data."""
    arcseconds: float = None
    hours: int = None
    minutes: int = None
    seconds: float = None
    degrees: float = None

@dataclass
class SystemStatus:
    """System status information."""
    code: int = None
    description: str = None

@dataclass
class Tracking:
    """Holds tracking and rate information for the mount."""
    code: int = None
    custom: float = 1.0000
    available_rates: dict = field(default_factory=dict)
    is_tracking: bool = False
    memory_store: int = None

    def current_rate(self):
        """Return a string description of the current rate."""
        if self.is_tracking is False:
            return "not tracking"
        if self.code is not None:
            return self.available_rates[self.code]
        # Not set, return none
        return None

@dataclass
class Meredian:
    """Holds meredian-related information."""
    code: int = None
    degree_limit: int = None

    def description(self):
        """Get the text description of the meredian treatment."""
        if self.code == 0:
            return "Stop at meredian"
        if self.code == 1:
            return "Flip at meredian with custom limit"
        else:
            return "Unknown or not set."

@dataclass
class MovingSpeed:
    """Information about the moving speed of the mount."""
    code: int = None
    multiplier: int = None
    description: str = None
    button_rate: int = None
    available_rates: dict = None

@dataclass
class Parking:
    """Contains information and location of parking."""
    is_parked: bool = None
    altitude: Altitude = field(default_factory=Altitude)
    azimuth: Azimuth = field(default_factory=Azimuth)

@dataclass
class Pec:
    """Holds information related to the periodic error correction (PEC.)"""
    integrity_complete: bool = None
    enabled: bool = None
    recording: bool = None

@dataclass
class TimeSource:
    """Keeps track of the source of time. May be removed in the future."""
    code: int = None
    description: str = "unset"

@dataclass
class TimeInfo:
    """Time related information."""
    utc_offset: int = None
    dst: bool = None
    julian_date: int = None
    unix_utc: float = None
    unix_offset: float = None
    formatted: str = None

@dataclass
class Hemisphere:
    """Holds information about the hemisphere of the mount."""
    code: int = None
    location: str = None

class TelescopeController:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None        
        logging.basicConfig(filename='iotty.log', format='%(asctime)s - %(message)s',\
            level=LOGLEVEL)

    def __enter__(self):
        self.socket = socket.create_connection((self.host, self.port))
        logging.debug("Mount connected.")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.socket:
            self.socket.close()
            logging.debug("Mount disconnected.")

    @staticmethod
    def _validate_response(response, command, expected_len=None, starts_with=None):
        """Validate a mount response. Returns True if the response looks valid,
        False if it appears garbled (e.g. from another client's interleaved commands).
        Logs a warning on invalid responses."""
        if response is None:
            logging.warning("%s: no response received", command)
            return False
        if expected_len is not None and len(response) < expected_len:
            logging.warning("%s: response too short (%d < %d): %s",
                            command, len(response), expected_len, response)
            return False
        if starts_with is not None:
            if not any(response.startswith(p) for p in starts_with):
                logging.warning("%s: unexpected response start: %s",
                                command, response[:20])
                return False
        return True


    def send(self, command, read_until_char='#', timeout=10, retries=5, max_chars=None):
        buffer_size = 1024
        logging.debug("Sending -> %s", str(command))

        if self.socket is None:
            logging.debug("Socket is not connected.")
            return None

        for attempt in range(retries):
            response = b''  # Reset response each attempt
            try:
                logging.debug("Attempt -> %s", str(attempt))
                # Clear any stale data from the receive buffer.
                # Loop until no data arrives for 0.1s.
                self.socket.settimeout(0)
                while True:
                    ready = select.select([self.socket], [], [], 0.1)
                    if ready[0]:
                        stale = self.socket.recv(buffer_size)
                        if stale:
                            logging.debug("Drained stale bytes: %s", stale)
                    else:
                        break

                self.socket.settimeout(timeout)

                # Send command
                self.socket.sendall(command.encode())

                # Read response
                if read_until_char or max_chars is not None:
                    i = 0
                    while True:
                        part = self.socket.recv(1)
                        if not part:
                            break  # Connection closed
                        response += part
                        i += 1
                        if part.decode() == read_until_char or max_chars == i:
                            break
                else:
                    response = self.socket.recv(buffer_size)

                time.sleep(0.2)  # Throttle to avoid flooding the mount

                if len(response) > 0:
                    decoded = response.decode()
                    # Remove only the trailing terminator, not all occurrences
                    if decoded.endswith(read_until_char):
                        decoded = decoded[:-1]
                    logging.debug("Response <- %s", decoded)
                    return decoded

            except socket.timeout:
                logging.warning("Timeout on attempt %d for command %s",
                                attempt + 1, command)
            except socket.error as e:
                if e.errno != 11:  # EAGAIN (non-blocking) is expected
                    logging.error("Socket error on command %s: %s", command, e)
                break

        # All retries exhausted — return whatever we got
        decoded = response.decode()
        logging.warning("All retries exhausted for %s, returning: %s",
                        command, decoded)
        return decoded

    def assign_init_values(self):
        # Assign default values
        self.location = Location()
        main_fw_info = self.get_main_firmwares()
        motor_fw_info = self.get_motor_firmwares()
        self.mount_version = self.get_mount_version()
        self.firmware = Firmwares(mainboard=main_fw_info[0], hand_controller=main_fw_info[1], \
            right_ascention=motor_fw_info[0], declination=motor_fw_info[1])
        self.hand_controller_attached = False if 'xx' in self.firmware.hand_controller else True
        self.system_status = SystemStatus()
        self.tracking = Tracking()
        self.time_source = TimeSource()
        self.hemisphere = Hemisphere()
        self.moving_speed = MovingSpeed()
        self.guiding = Guiding()
        self.is_slewing = False
        self.is_home = None
        self.pec = Pec()
        self.mount_config_data = \
            utils.parse_mount_config_file(f'{os.path.dirname(os.path.abspath(__file__))}/mount_values.yaml', self.mount_version)

        # Time information
        self.time = TimeInfo()

        # Direction information
        self.right_ascension = RA()
        self.declination = DEC()
        self.pier_side = None
        self.counterweight_direction = None
        self.altitude = Altitude()
        self.azimuth = Azimuth()
        self.meredian = Meredian()

        # Parking
        self.parking = Parking()

        # Set the update time to null
        self.last_update = 0


    def enable_pec_playback(self, enabled: bool):
        """Enable or disable PEC playback, toggled by the supplied boolean.
        Setting to True enables PEC playback, setting to False disables playback.
        Only available on eq mounts without encoders. Returns True when command sent
        and response is received, otherwise returns False."""
        if self.mount_config_data['type'] != "equatorial" or \
            self.mount_config_data['capabilities']['encoders'] is True:
            return False
        if enabled is True:
            self.send(":SPP1#")
            return True
        if enabled is False:
            self.send(":SPP0#")
            return True
        return False

    def get_all_kinds_of_status(self):
        """Get (a lot) of status from the mount. Get location, GPS state, status, movement
        and tracking information, and time data."""
        response_data = self.send(":GLS#")
        # GLS response: sign + 22 digits = 23 chars. Must start with + or -
        if not self._validate_response(response_data, ":GLS#",
                                       expected_len=23, starts_with=['+', '-']):
            return

        # Parse latitude and longitude
        # Longitude: sign + 8 digits in 0.01 arcsec. int() handles the +/- sign.
        self.location.longitude = utils.convert_arc_seconds_to_degrees(int(response_data[0:9]))
        # Latitude: 8 digits (no sign), value is actual latitude + 90° to keep it positive.
        self.location.latitude = utils.convert_arc_seconds_to_degrees(\
            int(response_data[9:17])) - 90 # Val is +90

        # Parse GPS state
        gps_state = response_data[17:18]
        if gps_state == '0':
            self.location.gps_available = False
        elif gps_state == '1':
            self.location.gps_available = True
            self.location.gps_locked = False
        elif gps_state == '2':
            self.location.gps_available = True
            self.location.gps_locked = True

        # Parse the system status
        # TODO: Refactor using YAML config
        status_code = response_data[18:19]
        self.system_status.code = status_code
        self.parking.is_parked = False
        self.is_home = False
        if status_code == '0':
            self.system_status.description = "stopped at non-zero position"
            self.is_slewing = False
            self.tracking.is_tracking = False
        elif status_code == '1':
            self.system_status.description = "tracking with periodic error correction disabled"
            self.is_slewing = False
            self.tracking.is_tracking = True
            self.pec.enabled = False
        elif status_code == '2':
            self.system_status.description = "slewing"
            self.is_slewing = True
            self.tracking.is_tracking = False
        elif status_code == '3':
            self.system_status.description = "auto-guiding"
            self.is_slewing = False
            self.tracking.is_tracking = True
        elif status_code == '4':
            self.system_status.description = "meridian flipping"
            self.is_slewing = True
        elif status_code == '5':
            self.system_status.description = "tracking with periodic error correction enabled"
            self.is_slewing = False
            self.tracking.is_tracking = True
            self.pec.enabled = True
        elif status_code == '6':
            self.system_status.description = "parked"
            self.is_slewing = False
            self.tracking.is_tracking = False
            self.parking.is_parked = True
        elif status_code == '7':
            self.system_status.description = "stopped at zero position (home position)"
            self.is_slewing = False
            self.tracking.is_tracking = False
            self.is_home = True

        # Parse tracking rate
        tracking_rate = response_data[19:20]
        if tracking_rate.isdigit():
            self.tracking.code = int(tracking_rate)
        self.tracking.available_rates = self.mount_config_data['tracking_rates']

        # Parse moving speed
        moving_speed = response_data[20:21]
        if moving_speed.isdigit():
            self.moving_speed.code = moving_speed
            self.moving_speed.available_rates = self.mount_config_data['tracking_speeds']
            self.moving_speed.description = self.parse_moving_speed(int(moving_speed))

        # Parse the time source
        time_source = response_data[21:22]
        if time_source:
            self.time_source.code = time_source
            if time_source == '1':
                self.time_source.description = "local port - RS232 or ethernet"
            elif time_source == '2':
                self.time_source.description = "hand controller"
            elif time_source == '3':
                self.time_source.description = "gps"

        # Parse the hemisphere
        hemisphere = response_data[22:23]
        if hemisphere:
            logging.info("HEMCODE:  --  " + hemisphere)
            self.hemisphere.code = hemisphere
            if hemisphere == '0':
                self.hemisphere.location = 's'
            if hemisphere == '1':
                self.hemisphere.location = 'n'

    def get_alt_and_az(self):
        """Get the altitude and azimuth of the mount's current direction."""
        returned_data = self.send(':GAC#')
        # GAC response: sign + 17 digits = 18 chars. Must start with + or -
        if not self._validate_response(returned_data, ":GAC#",
                                       expected_len=18, starts_with=['+', '-']):
            return

        # Altitude
        altitude = returned_data[0:9]
        self.altitude.arcseconds = float(altitude)
        self._set_dataclass_dms_from_arcseconds(self.altitude)

        # Azimuth
        azimuth = returned_data[9:18]
        self.azimuth.arcseconds = float(azimuth)
        self._set_dataclass_dms_from_arcseconds(self.azimuth)

    def get_altitude_limit(self):
        """Get the altitude limit currently set. Applies to tracking and slewing. Motion will
        stop if it exceeds this value. Spec response: snn# (sign + 2 digits)."""
        returned_data = self.send(':GAL#')
        # Response is sign + 2 digits, e.g. "+30" or "-05". int() handles the sign.
        self.altitude.limit = int(returned_data[0:3])
        return self.altitude.limit

    def get_coordinate_memory(self):
        """Get the number of available positions for most recently defined RA and DEC
        that do not exceed limits (altitude, mechanical, and flip.) Will return an int
        between 0 and 2. Only returns a value on eq mounts, otherwise None.
        Spec response: "0#", "1#", or "2#"."""
        returned_data = self.send(':QAP#')
        self.tracking.memory_store = returned_data[0:1]
        return self.tracking.memory_store

    def get_custom_tracking_rate(self):
        """Get the custom tracking rate, if it is set. Otherwise will be 1.000."""
        returned_data = self.send(':GTR#')
        if returned_data is None or len(returned_data) < 5:
            logging.warning("GTR response too short: %s", returned_data)
            return
        # Set the value and strip the control '#' at the end (response is d{5})
        self.tracking.custom = format((float(returned_data[:5]) * 0.0001), '.4f')

    def get_guiding_rate(self):
        """Get the current RA and DEC guiding rates. They are 0.01 - 0.99 * siderial."""
        returned_data = self.send(':AG#')
        if returned_data is None or len(returned_data) < 4:
            logging.warning("AG response too short: %s", returned_data)
            return
        # Convert values to 0.01 - 0.9
        self.guiding.right_ascention_rate = float(returned_data[0:2]) * 0.01
        self.guiding.declination_rate = float(returned_data[2:4])*  0.01

    def get_pec_integrity(self):
        """Get the integrity of the PEC. Returns (and sets) if it is complete or incomplete.
        Only available with eq mounts without encoders"""
        if self.mount_config_data['type'] != "equatorial" or \
            self.mount_config_data['capabilities']['encoders'] is True:
            return
        # Continue - is an EQ mount without encoders
        returned_data = self.send(':GPE#')
        if returned_data == "0":
            self.pec.integrity_complete = False
        if returned_data == "1":
            self.pec.integrity_complete = True

    def get_pec_recording_status(self):
        """Get the status of the PEC recording. Returns (and sets) if it is stopped or recording.
        Only available with eq mounts without encoders"""
        if self.mount_config_data['type'] != "equatorial" or \
            self.mount_config_data['capabilities']['encoders'] is True:
            return
        # Continue - is an EQ mount without encoders
        returned_data = self.send(':GPR#')
        if returned_data == "0":
            self.pec.recording = False
        if returned_data == "1":
            self.pec.recording = True

    def get_max_slewing_speed(self):
        """Get the maximum slewing speed for this mount and returns a factor of siderial (eg 8x)."""
        returned_data = self.send(':GSR#')
        

        # Response depends on mount model
        if returned_data == "7":
            return 256
        if returned_data == "8":
            return 512
        if returned_data == "9":
            return self.mount_config_data['tracking_speeds'][9]

    def get_meredian_treatment(self):
        """Get the treatment of the meredian - stop below limit or flip at limit along
        with the position limit in degrees past meredian. Only used for equitorial mounts."""
        # This works for eq mounts only
        if self.mount_config_data['type'] != 'equatorial':
            return
        # This is an eq mount
        returned_data = self.send(':GMT#')
        if returned_data is None or len(returned_data) < 3:
            logging.warning("GMT response too short: %s", returned_data)
            return
        
        code = returned_data[0:1]
        degrees = returned_data[1:3]
        if code.isdigit():
            self.meredian.code = int(code)
        if degrees.isdigit():
            self.meredian.degree_limit = int(degrees)

    def get_main_firmwares(self):
        """Get the firmware(s) of the mount and hand controller, if it is attached, otherwise
        a null value (xxxxxx) is used for the HC firmware."""
        returned_data = self.send(':FW1#')
        
        main_fw = returned_data[0:6]
        hc_fw = returned_data[6:12]
        return (main_fw, hc_fw)

    def get_motor_firmwares(self):
        """Get the firmware of the motors (ra and dec)."""
        returned_data = self.send(':FW2#')
        
        right_asc = returned_data[0:6]
        dec = returned_data[6:12]
        return (right_asc, dec)

    def get_mount_version(self):
        """Get the model / version of the mount. Returns the model number."""
        returned_data = self.send(':MountInfo#', max_chars=4)
        return returned_data

    def get_parking_position(self):
        """Get the current parking position of the mount. """
        returned_data = self.send(':GPC#')
        if returned_data is None or len(returned_data) < 17:
            logging.warning("GPC response too short: %s", returned_data)
            return

        # Altitude
        altitude = returned_data[0:8]
        self.parking.altitude.arcseconds = float(altitude)
        self._set_dataclass_dms_from_arcseconds(self.parking.altitude)

        # Azimuth
        azimuth = returned_data[8:17]
        self.parking.azimuth.arcseconds = float(azimuth)
        self._set_dataclass_dms_from_arcseconds(self.parking.azimuth)

    def get_ra_and_dec(self):
        """Get the RA and DEC of the telescope's current pointing position."""
        returned_data = self.send(':GEP#')
        # GEP response: sign + 19 digits = 20 chars. Must start with + or -
        if not self._validate_response(returned_data, ":GEP#",
                                       expected_len=18, starts_with=['+', '-']):
            return

        # RA
        right_asc = returned_data[9:18]
        self.right_ascension.arcseconds = float(right_asc)
        self.right_ascension.degrees = \
            utils.convert_arc_seconds_to_degrees(self.right_ascension.arcseconds)
        hms = utils.convert_arc_seconds_to_hms(right_asc)
        self.right_ascension.hours = hms[0]
        self.right_ascension.minutes = hms[1]
        self.right_ascension.seconds = hms[2]

        # Declination
        declination = returned_data[0:9]
        self.declination.arcseconds = float(declination)
        dms = utils.convert_arc_seconds_to_dms(self.declination.arcseconds)
        self.declination.degrees = dms[0]
        self.declination.minutes = dms[1]
        self.declination.seconds = dms[2]

        # The following only works for eq mounts
        if self.mount_config_data['type'] == "equatorial":
            # Pier side
            pier_side = returned_data[18:19]
            if pier_side.isdigit():
                self.pier_side = self.mount_config_data['pier_sides'][int(pier_side)]

            # Counterweight direction
            counterweight_direction = returned_data[19:20]
            if counterweight_direction.isdigit():
                self.counterweight_direction = \
                    self.mount_config_data['counterweight_direction'][int(counterweight_direction)]

    def get_ra_guiding_filter_status(self):
        """Get the status of the RA guiding filter for mounts with encoders."""
        # Only available for eq mounts with encoders
        if self.mount_config_data['type'] != "equatorial" or \
            self.mount_config_data['capabilities']['encoders'] is False:
            return None
        self.guiding.has_ra_filter = True
        returned_data = self.send(':GGF#')
        
        if returned_data == "0":
            self.guiding.ra_filter_enabled = False
        if returned_data == "1":
            self.guiding.ra_filter_enabled = True
        return self.guiding.ra_filter_enabled

    def get_time_information(self):
        """Get all time information from the mount, including it's time,
        timezone, and DST setting."""
        response_data = self.send(':GUT#')
        # GUT response: sign + 17 digits = 18 chars. Must start with + or -
        if not self._validate_response(response_data, ":GUT#",
                                       expected_len=18, starts_with=['+', '-']):
            # One retry — stale byte from previous command is common
            response_data = self.send(':GUT#')
            if not self._validate_response(response_data, ":GUT# (retry)",
                                           expected_len=18, starts_with=['+', '-']):
                return
        self.time.utc_offset = int(response_data[0:4])
        self.time.dst = False if response_data[4:5] == '0' else True
        self.time.julian_date = int(response_data[5:18].lstrip("0"))
        self.time.unix_utc = utils.convert_j2k_to_unix_utc(\
            self.time.julian_date, self.time.utc_offset)
        self.time.unix_offset = utils.offset_utc_time(self.time.unix_utc, self.time.utc_offset)
        self.time.formatted = utils.convert_unix_to_formatted(self.time.unix_offset)


    def go_to_zero_position(self):
        """Go to the mount's zero position."""
        self.send(':MH#')
        self.is_slewing = True
        # Get the response; do nothing with it
        

    def go_to_mechanical_zero_position(self):
        """Search and go to the *mechanical* zero position.
        Only supported by some mounts."""
        ## TODO: This is a good place to log a WARN
        # ['0040', '0041', '0043', '0044', '0070', '0071','0120', '0121', '0122']
        if self.mount_config_data['mechanical_zero'] is True:
            self.send(':MSH#')
            self.is_slewing = True
            # Get the response; do nothing with it
            
        # Maybe worth throwing an exception

    def move_dec_negative(self, milliseconds: int = 0):
        """Move the mount in the DEC- position at the current guiding rate for
        the given number of milliseconds (0-99999), with zero milliseconds being the
        default. Will return True once command is sent."""
        return self._move_in_direction_for_n_seconds('dec-', milliseconds)

    def move_dec_positive(self, milliseconds: int = 0):
        """Move the mount in the DEC+ position at the current guiding rate for
        the given number of milliseconds (0-99999), with zero milliseconds being the
        default. Will return True once command is sent."""
        return self._move_in_direction_for_n_seconds('dec+', milliseconds)

    def move_east(self):
        """Commands the mount to move to the east. Mount will continue moving
        until a stop command (stop_all_movement or stop_n_s_movement") is issued.
        This command is similar to the up "right" button on the hand controller.
        Returns True when command is sent and response received, otherwise will
        return False."""
        return self._move_in_cardinal_direction('east')

    def _move_in_cardinal_direction(self, direction: str):
        """PRIVATE method to move the mount in the supplied cardinal direction.
        Returns True when command is sent. Spec says these commands have no response."""
        directions = {'north': "mn", 'east': 'me', 'south': 'ms', 'west': 'mw'}
        assert direction.lower() in directions
        move_command = ":" + directions[direction.lower()] + "#"
        self.send(move_command)
        return True

    def _move_in_direction_for_n_seconds(self, direction: str, milliseconds: int):
        """PRIVATE method to move in a direction (RA, DEC +/-) for a given number
        of milliseconds. This method is to be used by methods that implement movement in
        a specific direction. Given direction must be in [ra+, ra-, dec+, dec-].
        Returns True once command is sent."""
        # Validate the arguments
        directions = {'ra+': "ZS", 'ra-': 'ZQ', 'dec+': 'ZE', 'dec-': 'ZC'}
        assert direction.lower() in directions
        assert 0 <= milliseconds <= 99999
        # Form and send the move command
        move_command = ":" + directions[direction.lower()] + str(milliseconds).zfill(5) + "#"
        self.send(move_command)
         # No output is returned
        return True

    def move_ra_negative(self, milliseconds: int = 0):
        """Move the mount in the RA- position at the current guiding rate for
        the given number of milliseconds (0-99999), with zero milliseconds being the
        default. Will return True once command is sent."""
        return self._move_in_direction_for_n_seconds('ra-', milliseconds)

    def move_ra_positive(self, milliseconds: int = 0):
        """Move the mount in the RA+ position at the current guiding rate for
        the given number of milliseconds (0-99999), with zero milliseconds being the
        default. Will return True once command is sent."""
        return self._move_in_direction_for_n_seconds('ra+', milliseconds)

    def move_south(self):
        """Commands the mount to move to the south. Mount will continue moving
        until a stop command (stop_all_movement or stop_n_s_movement") is issued.
        This command is similar to the up "down" button on the hand controller.
        Returns True when command is sent and response received, otherwise will
        return False."""
        return self._move_in_cardinal_direction('south')

    def move_to_defined_alt_and_az(self):
        """Commands the mount to slew to the most recently defined ALT and AZ.
        Spec: :MSS# — response "1" if accepted, "0" if below altitude limit or
        exceeds mechanical limits. After slewing, tracking will be stopped.
        Returns True when command accepted, False otherwise."""
        if self.send(":MSS#", '+') == '1':
            self.is_slewing = True
            return True
        return False

    def slew_to_ra_dec(self):
        """Commands the mount to slew to the most recently defined RA and DEC
        in the normal (counterweight-down) position.
        Spec: :MS1# — response "1" if accepted, "0" if below altitude limit or
        exceeds mechanical limits. After slewing, tracking will be enabled
        automatically. A pair of RA and DEC must be defined before this command.
        Returns True when command accepted, False otherwise."""
        if self.send(":MS1#", '+') == '1':
            self.is_slewing = True
            return True
        return False

    def slew_to_ra_dec_counterweight_up(self):
        """Commands the mount to slew to the most recently defined RA and DEC
        in the counterweight-up position.
        Spec: :MS2# — response "1" if accepted, "0" if below altitude limit or
        exceeds mechanical limits. After slewing, tracking will be enabled
        automatically. Only available in equatorial mounts.
        Returns True when command accepted, False otherwise."""
        if self.send(":MS2#", '+') == '1':
            self.is_slewing = True
            return True
        return False

    def move_north(self):
        """Commands the mount to move to the north. Mount will continue moving
        until a stop command (stop_all_movement or stop_n_s_movement") is issued.
        This command is similar to the up "arrow" button on the hand controller.
        Returns True when command is sent and response received, otherwise will
        return False."""
        return self._move_in_cardinal_direction('north')

    def move_west(self):
        """Commands the mount to move to the west. Mount will continue moving
        until a stop command (stop_all_movement or stop_n_s_movement") is issued.
        This command is similar to the up "left" button on the hand controller.
        Returns True when command is sent and response received, otherwise will
        return False."""
        return self._move_in_cardinal_direction('west')

    def park(self):
        """Park the mount at the most recently defined parking position.
        Returns a true if successful or false if parking failed."""
        
        response = self.send(':MP1#', max_chars=1)
        if response == "1":
            # Mount parked OK
            self.parking.is_parked = True
        else:
            # Mount was mot parked OK
            self.parking.is_parked = False
        return self.parking.is_parked

    def parse_moving_speed(self, rate):
        """Return the mount's current tracking speed in factors of sidarial rate."""
        return str(self.mount_config_data['tracking_speeds'][rate]) + 'x'

    def reset_settings(self, confirm: bool):
        """Reset all settings to default. Only applies if True is specified to indicate
        the reset is really wanted. Does not reset any time-based information."""
        if confirm is True:
            self.send(':RAS#')
            self.get_all_kinds_of_status()
            self.get_time_information()
            self.get_ra_and_dec()
            self.get_alt_and_az()

    def refresh_status(self):
        """Performs a refresh of the 4 basic mount status commands. These are the 4 updates
        the iOptron driver performs very refresh cycle. Only perform if last update > 1
        second ago to avoid flooding the mount."""
        # Return false if last update was recent
        if time.time() - self.last_update < 1:
            return False
        self.get_all_kinds_of_status()
        self.get_alt_and_az()
        self.get_ra_and_dec()
        self.get_time_information()
        self.last_update = time.time()
        return True

    def set_altitude_limit(self, limit: int):
        """Set the altitude limit, in degrees. Applies to tracking and slewing. Motion will
        stop if it exceeds this value. Limit is +/- 89 degrees.
        Spec: :SALsnn# where s is sign and nn is 2 digits.
        Returns True after command sent."""
        assert -89 <= limit <= 89
        self.altitude.limit = limit
        sign = "+" if limit >= 0 else "-"
        digits = str(abs(limit)).zfill(2)
        set_command = ":SAL" + sign + digits + "#"
        self.send(set_command)
        return True

    def set_arrow_button_movement_speed(self, rate):
        """Set the movement speed when the N-S-E-W buttons are used. Rate must be
        a code from the mount's available_rates (e.g. 5 for 64x). This value is
        wiped and replaced by the default (64x) on the next powerup.
        Returns True after command is sent."""
        assert rate in self.moving_speed.available_rates
        self.moving_speed.button_rate = rate
        movement_command = ":SR" + str(rate) + "#"
        self.send(movement_command)
        return True

    def _set_commanded_axis_from_dms(self, degrees, minutes, seconds, axis):
        """Defines the commanded axis to the specified degrees, minutes, and seconds
        (or hours, minutes, seconds for RA). Will convert the value to the mount's
        0.01-arcsecond protocol format and send it.
        Returns True when command is sent and response received, otherwise returns False."""
        command_dict = {'ra': 'SRA', 'dec': 'Sd', 'alt': 'Sa', 'az': 'Sz'}
        assert axis in command_dict

        if axis == 'ra':
            # RA input is HMS (hours, minutes, seconds of time).
            # Convert to decimal hours, then to degrees (* 15), then to
            # 0.01-arcsecond units.  Range [0, 129600000], 9 digits, no sign.
            decimal_hours = degrees + (minutes / 60.0) + (seconds / 3600.0)
            decimal_degrees = decimal_hours * 15.0
            arcsec_val = int(decimal_degrees * 3600.0 * 100.0)
            arcseconds = str(arcsec_val).zfill(9)
            axis_command = ":" + command_dict[axis] + arcseconds + "#"
        elif axis in ('dec', 'alt'):
            # Dec/Alt input is DMS.  Sign + 8 digits, range [-32400000, +32400000].
            arcsec_val = utils.convert_dms_to_arc_seconds(degrees, minutes, seconds)
            sign = "+" if arcsec_val >= 0 else "-"
            arcseconds = str(abs(int(arcsec_val))).zfill(8)
            axis_command = ":" + command_dict[axis] + sign + arcseconds + "#"
        elif axis == 'az':
            # Az input is DMS.  9 digits, no sign, range [0, 129600000].
            arcsec_val = utils.convert_dms_to_arc_seconds(degrees, minutes, seconds)
            arcseconds = str(abs(int(arcsec_val))).zfill(9)
            axis_command = ":" + command_dict[axis] + arcseconds + "#"

        if self.send(axis_command,'+') == '1':
            return True
        return False

    def set_commanded_altitude(self, degrees, minutes, seconds):
        """Set the commanded right altitude (ALT). Will return True when command is sent
        and response is received, otherwise will return False. Slew or calibrate commands
        operate based on the most recently defined value."""
        return self._set_commanded_axis_from_dms(degrees, minutes, seconds, 'alt')

    def set_commanded_azimuth(self, degrees, minutes, seconds):
        """Set the commanded right azimuth (AZI). Will return True when command is sent
        and response is received, otherwise will return False. Slew or calibrate commands
        operate based on the most recently defined value."""
        return self._set_commanded_axis_from_dms(degrees, minutes, seconds, 'az')

    def set_commanded_declination(self, degrees, minutes, seconds):
        """Set the commanded right declination (DEC). Will return True when command is sent
        and response is received, otherwise will return False. Slew or calibrate commands
        operate based on the most recently defined value."""
        return self._set_commanded_axis_from_dms(degrees, minutes, seconds, 'dec')

    def set_commanded_right_ascension(self, degrees, minutes, seconds):
        """Set the commanded right ascension (RA). Will return True when command is sent and
        response is received, otherwise will return False. Slew or calibrate commands operate
        based on the most recently defined value."""
        return self._set_commanded_axis_from_dms(degrees, minutes, seconds, 'ra')

    def set_current_position_as_zero(self):
        """Set the current position as the zero position. Returns True when command is sent and
        a response is received. Otherwise returns False."""
        szp_command = ":SZP#"
        if self.send(szp_command,'+') == '1':
            return True
        return False

    def set_guiding_rate(self, right_ascention: float, declination: float):
        """Set the current RA and DEC guiding rates. The valid range for RA is 0.01 - 0.90,
        for DEC is 0.10 - 0.99. These values will be used to set the guiding rate * siderial.
        For example 0.50 will be 0.50 * siderial guiding.
        Spec: :RGnnnn# where first nn = RA rate * 100, last nn = DEC rate * 100.
        Only works for equitorial mounts. Returns true once command is sent
        and a response received."""
        assert self.mount_config_data['type'] == 'equatorial' # only works on EQ mounts
        assert 0.01 <= right_ascention <= 0.90
        assert 0.10 <= declination <= 0.99
        self.guiding.right_ascention_rate = round(right_ascention, 2)
        self.guiding.declination_rate = round(declination, 2)
        ra_digits = str(int(round(self.guiding.right_ascention_rate * 100))).zfill(2)
        dec_digits = str(int(round(self.guiding.declination_rate * 100))).zfill(2)
        guiding_rate_command = ":RG" + ra_digits + dec_digits + "#"
        returned_data = self.send(guiding_rate_command,'+')
        assert returned_data == '1'
        return True

    def set_ra_guiding_filter_status(self, enabled: bool):
        """Set the status of the RA guiding filter for eq mounts with encoders.
        This command may or may not be saved on mount restart - the docs are unclear.
        Returns True after the command is sent."""
        # Only available for eq mounts with encoders
        if self.mount_config_data['type'] != "equatorial" or \
            self.mount_config_data['capabilities']['encoders'] is False:
            return None
        if enabled is True:
            self.guiding.ra_filter_enabled = True
            self.send(":SGF1#")
        if enabled is False:
            self.guiding.ra_filter_enabled = False
            self.send(":SGF0#")
        # Get the response; do nothing with it
        
        return True

    def set_custom_tracking_rate(self, rate):
        """Set a custom tracking rate to n.nnnn of the siderial rate. Only used
        when 'custom' tracking rate is being used. Spec: :RRnnnnn# where the
        value represents n.nnnn * sidereal. Returns True after command is sent."""
        # Convert rate (e.g. 1.0000) to 5-digit integer (e.g. 10000)
        rate_int = int(round(float(rate) * 10000))
        send_command = ":RR" + str(rate_int).zfill(5) + "#"
        self.send(send_command)
        return True

    def _set_dataclass_dms_from_arcseconds(self, data_class):
        """PRIVATE: Set DMS for a given dataclass like Altitude and Azimuth given
        their pre-set arcseconds value. Intended to keep code DRY."""
        dms = utils.convert_arc_seconds_to_dms(data_class.arcseconds)
        data_class.degrees = dms[0]
        data_class.minutes = dms[1]
        data_class.seconds = dms[2]

    def set_daylight_savings(self, dst: bool):
        """Enables daylight savings time when true, disables it when false."""
        if dst is True:
            self.send(':SDS1#')
        else:
            self.send(':SDS0#')
        # Get the response; do nothing with it
        

        # Update time information after setting
        self.get_time_information()

    def set_hemisphere(self, direction: str):
        """Set the mount's hemisphere. Supplied argument must be 'north', 'south', or
        'n' or 's'. Returns True after command is sent."""
        assert direction.lower() in ['north', 'south', 'n', 's']
        hemisphere = 0 if direction[0:1] == 's' else 1
        command = ":SHE" + str(hemisphere) + "#"
        self.send(command)
        
        return True

    def set_latitude(self, latitude: float):
        """Set the latitude of the mount in degrees. Values range from +/- 90.
        North is positive, south is negative. Returns True when command is sent and
        response reveived, otherwise False is returned."""
        assert -90.0 <= latitude <= 90.0
        self.location.latitude = latitude
        arcsec_val = int(utils.convert_degrees_to_arc_seconds(self.location.latitude))
        sign = "+" if arcsec_val >= 0 else "-"
        arcseconds = str(abs(arcsec_val)).zfill(8)
        lat_command = ":SLA" + sign + arcseconds + "#"
        if self.send(lat_command,'+') == '1':
            return True
        return False

    def set_longitude(self, longitude: float):
        """Set the longitude of the mount in degrees. Values range from +/- 180.
        East is positive, west is negative. Returns True when command is sent and
        response reveived, otherwise False is returned."""
        assert -180.0 <= longitude <= 180.0
        self.location.longitude = longitude
        arcsec_val = int(utils.convert_degrees_to_arc_seconds(self.location.longitude))
        sign = "+" if arcsec_val >= 0 else "-"
        arcseconds = str(abs(arcsec_val)).zfill(8)
        long_command = ":SLO" + sign + arcseconds + "#"
        if self.send(long_command,'+') == '1':
            return True
        return False

    def set_max_slewing_speed(self, speed: str):
        """Set the maximum slewing speed. Input is the maximum siderial
        rate desired. Must be '256x', '512x', or 'max'. The max rate
        will depend on the mount. Returns True once command is sent."""
        assert speed in ['256x', '512x', 'max']
        # Set to max by default
        speed_bit = '9'
        if speed == '256x':
            speed_bit = '7'
        if speed == '512x':
            speed_bit = '8'
        speed_command = ":MSR" + speed_bit + "#"
        self.send(speed_command)
        # Get the response; do nothing with it
        
        return True

    def set_meredian_treatment(self, treatment: str, limit: int):
        """Set the treatment of the meredian. First argument is whether to
        'stop' or 'flip'. Second argument is the limit, in degrees (nn) to apply
        the behavior to. Will return True once command is sent and response received.
        Only works for equitorial mounts; will return False otherwise."""
        # This works for eq mounts only
        if self.mount_config_data['type'] != 'equatorial':
            return False # only works on EQ mounts
        # Validate arguments
        assert treatment.lower() in ['stop', 'flip']
        assert 0 <= limit <= 90
        # This is an eq mount
        self.meredian.code = 1 if treatment.lower() == 'flip' else 0
        self.meredian.degree_limit = limit
        treatment_cmd = ":SMT" + str(self.meredian.code) + str(limit).zfill(2) + "#"
        if self.send(treatment_cmd, '+') == '1':
            return True
        return False

    def set_parking_altitude(self, degrees: int, minutes: int, seconds: float):
        """Set the parking altitude. Takes a position in integer degrees, minutes, and seconds.
        Returns True when command is sent and response received. Returns False otherwise."""
        arcseconds = str(utils.convert_dms_to_arc_seconds(degrees, minutes, seconds)).zfill(8)
        park_alt_command = ":SPH" + arcseconds + "#"
        if self.send(park_alt_command, '+') == '1':
            return True
        return False

    def set_parking_azimuth(self, degrees: int, minutes: int, seconds: int):
        """Set the parking azimuth. Takes a position in integer degrees, minutes, and seconds.
        Spec: :SPATTTTTTTTT# — 9 digits for azimuth.
        Returns True when command is sent and response received. Returns False otherwise."""
        arcseconds = str(utils.convert_dms_to_arc_seconds(degrees, minutes, seconds)).zfill(9)
        park_az_command = ":SPA" + arcseconds + "#"
        if self.send(park_az_command, '+') == '1':
            return True
        return False

    def set_time(self):
        """Set the current time on the moint to the current computer's time. Sets to UTC."""
        j2k_time = str(utils.get_utc_time_in_j2k()).zfill(13)
        time_command = ":SUT" + j2k_time + "#"
        self.send(time_command)

    def set_timezone_offset(self, offset = utils.get_utc_offset_min()):
        """Sets the time zone offset on the mount to the computer's TZ offset.
        Spec: :SGsMMM# where s is sign and MMM is 3-digit minutes."""
        sign = "+" if offset >= 0 else "-"
        tz_digits = str(abs(int(offset))).zfill(3)
        tz_command = ":SG" + sign + tz_digits + "#"
        self.send(tz_command)

    def set_tracking_rate(self, rate):
        """Set the tracking rate of the mount.
        Rate must be one supported by the mount (tracking.available_rates)
        Returns True once command is sent and response reveived, otherwise
        False is returned."""
        assert rate in (list(self.tracking.available_rates.values()))
        reverse = dict((v,k) for k,v in self.tracking.available_rates.items())
        rate_command = ":RT" + str(reverse[rate]) + "#"
        if self.send(rate_command, '+') == '1':
            return True
        return False

    def _toggle_pec_recording(self, turn_on: bool):
        """PRIVATE method for toggling PEC recording on and off."""
        if self.mount_config_data['type'] == 'equatorial' and \
            self.mount_config_data['capabilities']['pec'] is True and \
            self.mount_config_data['capabilities']['encoders'] is False:
            # Default is off
            pec_command = ":SPR1#" if turn_on is True else ":SPR0#"
            return self.send(pec_command)
        else:
            logging.warning("PEC recording not usable with this mount")
            return None

    def start_recording_pec(self):
        """Start recording the periodic error. Only used in eq mounts without encoders.
        Returns True if command was sent and response received, otherwise will return False."""
        result = self._toggle_pec_recording(True)
        if result == '1':
            return True
        return False

    def stop_recording_pec(self):
        """Stop recording the periodic error. Only used in eq mounts without encoders.
        Returns True if command was sent and response received, otherwise will return False."""
        
        if self._toggle_pec_recording(False) == '1':
            return True
        return False

    def start_tracking(self):
        """Commands the mount to start tracking. Returns True when command is sent and
        received, otherwise returns False."""
        tracking_command = ":ST1#"
        if self.send(tracking_command, '+') == '1':
            return True
        return False

    def stop_all_movement(self):
        """Stop all slewing no matter the source of slewing or the direction(s)."""
        self.send(':Q#')
        self.is_slewing = False

    def stop_e_or_w_movement(self):
        """Stop movement in the east or west directions started by :me#/:mw# commands.
        Per spec, does NOT affect GoTo slewing or tracking."""
        self.send(':qR#')

    def stop_n_or_s_movement(self):
        """Stop movement in the north or south directions started by :mn#/:ms# commands.
        Per spec, does NOT affect GoTo slewing or tracking."""
        self.send(':qD#')

    def stop_tracking(self):
        """Commands the mount to stop tracking. Returns True when command is sent and
        received, otherwise returns False."""
        tracking_command = ":ST0#"
        
        if self.send(tracking_command, '+') == '1':
            return True
        return False

    def synchronize_mount(self):
        """Synchrolizes the mount. The most recently defined RA and DEC, or ALT and AZ
        become the commanded values. Ignored is slewing is in progress. Only useful for
        initial calibration; not to be used when tracking. Returns True once command
        is sent and response received. Otherwise False is returned."""
        
        if self.send(":CM#") == '1':
            return True
        return False

    def unpark(self):
        """Unpark the moint. If the mount is unparked already, this does nothing. """
        self.send(':MP0#',max_chars=1)
        # Always returns a 1
        self.parking.is_parked = False
        return self.parking.is_parked

    def update_status(self):
        """Call the update commands to get the latest status of the mount.
        Only perform if last update > 1 second ago to avoid flooding."""
        current_time = time.time()
        if current_time - self.last_update > 1:
            self.get_all_kinds_of_status()
            self.get_time_information()
            self.get_ra_and_dec()
            self.get_alt_and_az()
        # Apply the latest update time
        self.last_update = time.time()