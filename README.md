# NOAA Tides and Currents Custom Component for Home Assistant
The NOAA Tides custom component provides real-time tidal and environmental data from NOAA's CO-OPS API. This component replaces the legacy NOAA Tides [core component](https://www.home-assistant.io/integrations/noaa_tides/), offering enhanced configurability, automatic sensor detection, and improved data handling.

## Installation

1. Clone this repository to your local machine.
2. Copy the `noaa_tides` folder to your Home Assistant `custom_components` directory.
3. Restart Home Assistant.

## Configuration

To configure the NOAA Tides integration, follow these steps:

1. Go to the Home Assistant UI.
2. Navigate to `Configuration` > `Integrations`.
3. Click on `Add Integration` and search for `NOAA Tides`.
4. Follow the prompts to enter your configuration details.

Different stations support different features (products/datums/sensors). Available features are automatically pulled from a given station during configuration.
[Station finder](https://tidesandcurrents.noaa.gov/map/index.html?type=datums).
<!-- [Buoy finder](https://www.ndbc.noaa.gov/obs.shtml?type=oceans&status=r&pgm=IOOS%20Partners|International%20Partners|Marine%20METAR|NDBC%20Meteorological%2FOcean|NERRS|NOS%2FCO-OPS&op=&ls=n)) -->

## Sample configuration

![Configuration step 1](/images/config1.png)
![Configuration step 2](/images/config2.png)
![Configuration step 3](/images/config3.png)

## Usage

Once configured, the NOAA Tides integration will create a device/hub for the station and sensor entities that provide tide data, and other station data. You can use these sensors in your automations, scripts, and dashboards.

Tide factor is used to create a sinusoidal wave graph to represent the tide level when a station doesn't offer a water level sensor.

Tide percentage creates a linear graph and is useful for making something like a tide clock.


## Sensors:

* **Automatic Sensor Detection:** During setup, the component auto-detects and pulls available sensors based on the selected station ID.
* **Tide State Sensor:** Displays the upcoming tide type and time.
  * **Attributes:** NOAA predicted tide levels. previous tide details, calculated tide factor & percentage.
* **Water Level Sensor:** Reports the current water level relative to the selected station.
* **Water Temperature Sensor:** Provides real-time water temperature readings.
* **Air Temperature Sensor:** Reports atmospheric temperature data.

![Device page](/images/device_page.png)
![Tide state](/images/tide_state.png)
