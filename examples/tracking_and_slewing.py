"""Example: Start/stop tracking and slew to coordinates."""
from ioptron import TelescopeController

HOST = '192.168.10.17'
PORT = 8080

with TelescopeController(HOST, PORT) as scope:
    scope.assign_init_values()

    # Start sidereal tracking
    scope.start_tracking()
    scope.get_all_kinds_of_status()
    print(f"Tracking: {scope.tracking.current_rate()}")

    # Set a target and slew (RA in hours/min/sec, Dec in deg/min/sec)
    scope.set_commanded_right_ascension(12, 30, 0)
    scope.set_commanded_declination(45, 0, 0)
    if scope.slew_to_ra_dec():
        print("Slewing to target...")
    else:
        print("Slew rejected (below altitude limit or mechanical limit).")

    # Stop tracking
    scope.stop_tracking()
