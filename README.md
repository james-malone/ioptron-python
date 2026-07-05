# ioptron-python

A Python library for controlling iOptron equatorial and alt-az mounts over TCP/IP (or serial via a network bridge). Implements the complete [iOptron RS-232 Command Language v3.10](https://www.ioptron.com/v/ASCOM/RS-232_Command_Language2014V310.pdf) specification.

## Supported Mounts

All mounts covered by the v3.10 command spec:

- CEM120, CEM120-EC, CEM120-EC2
- CEM70, CEM70-EC, CEM70G, CEM70G-EC
- GEM45, GEM45-EC, GEM45G, GEM45G-EC
- CEM40, CEM40-EC, CEM40G, CEM40G-EC
- GEM28, GEM28-EC
- CEM26, CEM26-EC

Developed and tested against a **CEM120** over Ethernet.

## Features

- **Full spec coverage** — all 47 commands from the v3.10 spec are implemented
- **TCP socket communication** — connects over Ethernet or WiFi (no serial driver needed)
- **Context manager** — use `with TelescopeController(host, port) as scope:` for automatic connection management
- **Response validation** — guards against garbled/truncated responses from the mount (common when multiple clients are connected)
- **Mount-specific configuration** — reads mount capabilities from YAML config (tracking speeds, pier sides, encoder support, etc.)
- **254 unit tests** at 88% code coverage — every command format verified against the spec

## Quick Start

```python
from ioptron import TelescopeController

with TelescopeController('192.168.10.17', 8080) as scope:
    scope.assign_init_values()

    # Read status
    scope.get_all_kinds_of_status()
    print(f"Status: {scope.system_status.description}")
    print(f"Tracking: {scope.tracking.current_rate()}")

    # Read position
    scope.get_ra_and_dec()
    print(f"RA:  {scope.right_ascension.hours}h {scope.right_ascension.minutes}m")
    print(f"Dec: {scope.declination.degrees}° {scope.declination.minutes}'")
    print(f"Pier side: {scope.pier_side}")

    # Slew to a target
    scope.set_commanded_right_ascension(12, 30, 0)   # 12h 30m 0s
    scope.set_commanded_declination(45, 0, 0)         # +45° 0' 0"
    scope.slew_to_ra_dec()

    # Park
    scope.park()
```

## Installation

```bash
git clone https://github.com/robbrad/ioptron-python.git
cd ioptron-python
pip install -r requirements.txt
```

### Requirements

- Python 3.7+
- `pyyaml`

## Usage

### Connection

The mount must be reachable over TCP. If using the iOptron WiFi adapter or an Ethernet-to-serial bridge, connect to its IP and port:

```python
from ioptron import TelescopeController

with TelescopeController('192.168.10.17', 8080) as scope:
    scope.assign_init_values()
    # ... use scope
```

### Reading Status

```python
scope.get_all_kinds_of_status()   # Location, GPS, system status, tracking, speed
scope.get_ra_and_dec()            # RA, Dec, pier side, counterweight direction
scope.get_alt_and_az()            # Altitude and azimuth
scope.get_time_information()      # UTC offset, DST, time
scope.get_meredian_treatment()    # Meridian flip behaviour and limit
```

### Movement

```python
# GoTo slew (set target first, then slew)
scope.set_commanded_right_ascension(hours, minutes, seconds)
scope.set_commanded_declination(degrees, minutes, seconds)
scope.slew_to_ra_dec()                    # Normal position
scope.slew_to_ra_dec_counterweight_up()   # Counterweight-up position

# Arrow-button movement (runs until stopped)
scope.move_north()    # Dec-
scope.move_south()    # Dec+
scope.move_east()     # RA-
scope.move_west()     # RA+
scope.stop_n_or_s_movement()
scope.stop_e_or_w_movement()
scope.stop_all_movement()

# Pulse guiding (timed, in milliseconds)
scope.move_ra_positive(5000)    # RA+ for 5 seconds
scope.move_dec_negative(1000)   # Dec- for 1 second

# Tracking
scope.start_tracking()
scope.stop_tracking()
scope.set_tracking_rate('sidereal')  # sidereal, lunar, solar, king, custom
```

### Settings

```python
scope.set_altitude_limit(10)                    # +/- 89 degrees
scope.set_meredian_treatment('flip', 10)        # flip at 10° past meridian
scope.set_guiding_rate(0.50, 0.50)              # RA and Dec guiding rates
scope.set_arrow_button_movement_speed(5)        # 1-9 (64x sidereal)
scope.set_latitude(52.0)
scope.set_longitude(-2.35)
scope.set_hemisphere('north')
scope.set_time()                                # Sync to computer time
scope.set_timezone_offset()                     # Sync timezone
```

## Project Structure

```
ioptron-python/
├── ioptron/
│   ├── __init__.py              # Package init, exports TelescopeController
│   ├── ioptron.py               # Main controller class + data classes
│   ├── utils.py                 # Coordinate conversion utilities
│   ├── const.py                 # Constants (log level)
│   └── mount_values.yaml        # Mount-specific configuration
├── tests/
│   └── test_ioptron_commands.py # 254 unit tests (run with: python -m pytest tests/)
├── examples/
│   ├── statuses.py              # Read all mount status
│   ├── parking.py               # Park and unpark
│   ├── tracking_and_slewing.py  # Tracking and GoTo slew
│   ├── mount_direction.py       # Read position and move
│   ├── location.py              # Read/set location
│   ├── guiding.py               # Read/set guiding rates
│   └── times_and_dates.py       # Read/set time
├── docs/
│   ├── commands.md              # Full command implementation status
│   └── notes.md                 # Development notes
├── requirements.txt
├── LICENSE.md                   # GPLv3
└── README.md
```

## Running Tests

```bash
python -m pytest tests/ -v
```

Or without pytest:

```bash
python tests/test_ioptron_commands.py
```

## Specification

This library implements the [iOptron® Mount RS-232 Command Language v3.10](https://www.ioptron.com/v/ASCOM/RS-232_Command_Language2014V310.pdf) (January 4, 2021). All 47 commands are implemented with format-verified unit tests. See [docs/commands.md](docs/commands.md) for the full implementation matrix.

## Multi-Client Warning

The iOptron mount has a single command/response buffer. If multiple clients (e.g. this library + NINA + PHD2 + Home Assistant) send commands simultaneously, responses can get interleaved and garbled. The library includes response validation to handle this gracefully, but for reliable operation, only one client should actively poll the mount at a time.

## Citations and Sources

This project has used parts of other OSS projects, or has implemented ideas shown in them, including:

* [python-lx200](https://github.com/telescopio-montemayor/python-lx200)
* [onstep-python](https://github.com/kbahey/onstep-python)

This project implements the following open specification:

* [iOptron® Mount RS-232 Command Language v3.10](https://www.ioptron.com/v/ASCOM/RS-232_Command_Language2014V310.pdf) (January 4, 2021)

## License

GPLv3 — see [LICENSE.md](LICENSE.md).
