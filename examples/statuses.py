"""Example: Read all mount status information."""
from ioptron import TelescopeController

HOST = '192.168.10.17'
PORT = 8080

with TelescopeController(HOST, PORT) as scope:
    scope.assign_init_values()
    scope.get_all_kinds_of_status()

    print(f"Latitude:  {scope.location.latitude}")
    print(f"Longitude: {scope.location.longitude}")
    print(f"GPS available: {scope.location.gps_available}")
    print(f"GPS locked:    {scope.location.gps_locked}")
    print(f"System status: {scope.system_status.description}")
    print(f"Is slewing:    {scope.is_slewing}")
    print(f"Is tracking:   {scope.tracking.is_tracking}")
    print(f"Is parked:     {scope.parking.is_parked}")
    print(f"Is home:       {scope.is_home}")
    print(f"Tracking rate: {scope.tracking.current_rate()}")
    print(f"Moving speed:  {scope.moving_speed.description}")
    print(f"Time source:   {scope.time_source.description}")
    print(f"Hemisphere:    {scope.hemisphere.location}")
