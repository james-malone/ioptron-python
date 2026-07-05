"""Example: Read and set location information."""
from ioptron import TelescopeController

HOST = '192.168.10.17'
PORT = 8080

with TelescopeController(HOST, PORT) as scope:
    scope.assign_init_values()
    scope.get_all_kinds_of_status()

    print(f"Current latitude:  {scope.location.latitude}")
    print(f"Current longitude: {scope.location.longitude}")

    # Set location (uncomment to use)
    # scope.set_latitude(52.0)
    # scope.set_longitude(-2.35)
    # scope.set_hemisphere('north')
