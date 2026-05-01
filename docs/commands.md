# iOptron RS-232 Command Language v3.10 — Implementation Status

All 47 commands from the [iOptron RS-232 Command Language v3.10](https://www.ioptron.com/v/ASCOM/RS-232_Command_Language2014V310.pdf) specification are implemented and tested.

## Get Information and Settings
| Command | Method | Status |
|---------|--------|--------|
| `:GLS#` | `get_all_kinds_of_status()` | ✅ Implemented + tested |
| `:GUT#` | `get_time_information()` | ✅ Implemented + tested |
| `:GEP#` | `get_ra_and_dec()` | ✅ Implemented + tested |
| `:GAC#` | `get_alt_and_az()` | ✅ Implemented + tested |
| `:GTR#` | `get_custom_tracking_rate()` | ✅ Implemented + tested |
| `:GPC#` | `get_parking_position()` | ✅ Implemented + tested |
| `:GSR#` | `get_max_slewing_speed()` | ✅ Implemented + tested |
| `:GAL#` | `get_altitude_limit()` | ✅ Implemented + tested |
| `:AG#` | `get_guiding_rate()` | ✅ Implemented + tested |
| `:GMT#` | `get_meredian_treatment()` | ✅ Implemented + tested |
| `:GGF#` | `get_ra_guiding_filter_status()` | ✅ Implemented + tested |
| `:GPE#` | `get_pec_integrity()` | ✅ Implemented + tested |
| `:GPR#` | `get_pec_recording_status()` | ✅ Implemented + tested |

## Change Settings
| Command | Method | Status |
|---------|--------|--------|
| `:RT0-4#` | `set_tracking_rate()` | ✅ Implemented + tested |
| `:SRn#` | `set_arrow_button_movement_speed()` | ✅ Implemented + tested |
| `:SGF0/1#` | `set_ra_guiding_filter_status()` | ✅ Implemented + tested |
| `:SGsMMM#` | `set_timezone_offset()` | ✅ Implemented + tested |
| `:SDS0/1#` | `set_daylight_savings()` | ✅ Implemented + tested |
| `:SUTX...#` | `set_time()` | ✅ Implemented + tested |
| `:SLOsT...#` | `set_longitude()` | ✅ Implemented + tested |
| `:SLAsT...#` | `set_latitude()` | ✅ Implemented + tested |
| `:SHE0/1#` | `set_hemisphere()` | ✅ Implemented + tested |
| `:MSRn#` | `set_max_slewing_speed()` | ✅ Implemented + tested |
| `:SALsnn#` | `set_altitude_limit()` | ✅ Implemented + tested |
| `:RGnnnn#` | `set_guiding_rate()` | ✅ Implemented + tested |
| `:SMTnnn#` | `set_meredian_treatment()` | ✅ Implemented + tested |
| `:RAS#` | `reset_settings()` | ✅ Implemented + tested |

## Mount Motion
| Command | Method | Status |
|---------|--------|--------|
| `:MS1#` | `slew_to_ra_dec()` | ✅ Implemented + tested |
| `:MS2#` | `slew_to_ra_dec_counterweight_up()` | ✅ Implemented + tested |
| `:MSS#` | `move_to_defined_alt_and_az()` | ✅ Implemented + tested |
| `:Q#` | `stop_all_movement()` | ✅ Implemented + tested |
| `:ST0/1#` | `stop_tracking()` / `start_tracking()` | ✅ Implemented + tested |
| `:ZSXXXXX#` | `move_ra_positive()` | ✅ Implemented + tested |
| `:ZQXXXXX#` | `move_ra_negative()` | ✅ Implemented + tested |
| `:ZEXXXXX#` | `move_dec_positive()` | ✅ Implemented + tested |
| `:ZCXXXXX#` | `move_dec_negative()` | ✅ Implemented + tested |
| `:mn/me/ms/mw#` | `move_north/east/south/west()` | ✅ Implemented + tested |
| `:MP1#` | `park()` | ✅ Implemented + tested |
| `:MP0#` | `unpark()` | ✅ Implemented + tested |
| `:MH#` | `go_to_zero_position()` | ✅ Implemented + tested |
| `:MSH#` | `go_to_mechanical_zero_position()` | ✅ Implemented + tested |
| `:SPR0/1#` | `start_recording_pec()` / `stop_recording_pec()` | ✅ Implemented + tested |
| `:SPP0/1#` | `enable_pec_playback()` | ✅ Implemented + tested |
| `:RRnnnnn#` | `set_custom_tracking_rate()` | ✅ Implemented + tested |
| `:qR#` | `stop_e_or_w_movement()` | ✅ Implemented + tested |
| `:qD#` | `stop_n_or_s_movement()` | ✅ Implemented + tested |

## Position
| Command | Method | Status |
|---------|--------|--------|
| `:CM#` | `synchronize_mount()` | ✅ Implemented + tested |
| `:QAP#` | `get_coordinate_memory()` | ✅ Implemented + tested |
| `:SRAT...#` | `set_commanded_right_ascension()` | ✅ Implemented + tested |
| `:SdsT...#` | `set_commanded_declination()` | ✅ Implemented + tested |
| `:SasT...#` | `set_commanded_altitude()` | ✅ Implemented + tested |
| `:SzT...#` | `set_commanded_azimuth()` | ✅ Implemented + tested |
| `:SZP#` | `set_current_position_as_zero()` | ✅ Implemented + tested |
| `:SPAT...#` | `set_parking_azimuth()` | ✅ Implemented + tested |
| `:SPHT...#` | `set_parking_altitude()` | ✅ Implemented + tested |

## Miscellaneous
| Command | Method | Status |
|---------|--------|--------|
| `:FW1#` | `get_main_firmwares()` | ✅ Implemented + tested |
| `:FW2#` | `get_motor_firmwares()` | ✅ Implemented + tested |
| `:MountInfo#` | `get_mount_version()` | ✅ Implemented + tested |
