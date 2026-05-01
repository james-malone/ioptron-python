"""Example: Read time information from the mount."""
from ioptron import TelescopeController

HOST = '192.168.10.17'
PORT = 8080

with TelescopeController(HOST, PORT) as scope:
    scope.assign_init_values()
    scope.get_time_information()

    print(f"UTC offset (min): {scope.time.utc_offset}")
    print(f"DST:              {scope.time.dst}")
    print(f"Formatted time:   {scope.time.formatted}")

    # Sync mount time to computer time (uncomment to use)
    # scope.set_time()
    # scope.set_timezone_offset()
