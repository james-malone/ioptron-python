"""Example: Park and unpark the mount."""
from ioptron import TelescopeController

HOST = '192.168.10.17'
PORT = 8080

with TelescopeController(HOST, PORT) as scope:
    scope.assign_init_values()

    # Park
    if scope.park():
        print("Mount parked successfully.")
    else:
        print("Park failed.")

    # Unpark
    scope.unpark()
    print(f"Is parked: {scope.parking.is_parked}")
