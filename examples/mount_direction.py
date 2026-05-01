"""Example: Read current pointing position and move the mount."""
from ioptron import TelescopeController
import time

HOST = '192.168.10.17'
PORT = 8080

with TelescopeController(HOST, PORT) as scope:
    scope.assign_init_values()

    # Read current position
    scope.get_ra_and_dec()
    print(f"RA:  {scope.right_ascension.hours}h {scope.right_ascension.minutes}m "
          f"{scope.right_ascension.seconds:.1f}s")
    print(f"Dec: {scope.declination.degrees}° {scope.declination.minutes}' "
          f"{scope.declination.seconds:.1f}\"")
    print(f"Pier side: {scope.pier_side}")

    scope.get_alt_and_az()
    print(f"Alt: {scope.altitude.degrees}° {scope.altitude.minutes}' "
          f"{scope.altitude.seconds:.1f}\"")
    print(f"Az:  {scope.azimuth.degrees}° {scope.azimuth.minutes}' "
          f"{scope.azimuth.seconds:.1f}\"")

    # Move west for 2 seconds then stop (uncomment to use)
    # scope.move_west()
    # time.sleep(2)
    # scope.stop_e_or_w_movement()
