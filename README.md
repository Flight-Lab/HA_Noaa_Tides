# NOAA Tides and Currents Custom Component for Home Assistant
The NOAA Tides custom component provides real-time tidal and environmental data from NOAA's CO-OPS API. This component replaces the legacy NOAA Tides [core component](https://www.home-assistant.io/integrations/noaa_tides/), offering enhanced configurability, automatic sensor detection, and improved data handling.

## Installation

1. Copy the `noaa_tides` directory into `<home assistant directory>/custom_components/`


## Sample configuration

![Configuration step 1](/images/config1.png)
![Configuration step 2](/images/config2.png)
![Configuration step 3](/images/config3.png)


Different stations support different features (products/datums/sensors). Available features are automatically pulled from a given station during configuration.
[Station finder](https://tidesandcurrents.noaa.gov/map/index.html?type=datums).
<!-- [Buoy finder](https://www.ndbc.noaa.gov/) -->


## Features:

* **Automatic Sensor Detection:** During setup, the component auto-detects and pulls available sensors based on the selected station ID.
* **Tide State Sensor:** Displays the upcoming tide type and time.
  * **Attributes:** NOAA predicted tide levels. previous tide details, calculated tide factor & percentage.
* **Water Level Sensor:** Reports the current water level relative to the selected station.
* **Water Temperature Sensor:** Provides real-time water temperature readings.
* **Air Temperature Sensor:** Reports atmospheric temperature data.

![Device page](/images/device-page.png)
![Tide state](/images/tide-state.png)
