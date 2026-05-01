"""Example: Read and set guiding rates."""
from ioptron import TelescopeController

HOST = '192.168.10.17'
PORT = 8080

with TelescopeController(HOST, PORT) as scope:
    scope.assign_init_values()
    scope.get_guiding_rate()

    print(f"RA guiding rate:  {scope.guiding.right_ascention_rate}")
    print(f"DEC guiding rate: {scope.guiding.declination_rate}")

    # Set guiding rates (0.01 - 0.90 for RA, 0.10 - 0.99 for DEC)
    # scope.set_guiding_rate(0.50, 0.50)
