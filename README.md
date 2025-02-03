# NOAA Tides and Currents Custom Component for Home Assistant
The NOAA Tides custom component provides real-time tidal and environmental data from NOAA's CO-OPS API. This component replaces the legacy Home Assistant core NOAA Tides integration, offering enhanced configurability, automatic sensor detection, and improved data handling.

## Features:
* Automatic Sensor Detection: During setup, the component auto-detects and pulls available sensors based on the selected station ID.
* Tide State Sensor: Displays the upcoming tide type and time, along with attributes such as previous tide details, tide factor, and predicted tide levels.
* Water Level Sensor: Reports the current water level relative to the selected station.
* Water Temperature Sensor: Provides real-time water temperature readings.
* Air Temperature Sensor: Reports atmospheric temperature data.
