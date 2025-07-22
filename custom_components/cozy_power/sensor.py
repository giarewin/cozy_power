"""Sensor platform for Cozy Power."""
from datetime import timedelta
import async_timeout
import asyncio
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .cozylife_device import CozyLifeDevice

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)
TIMEOUT = 5

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    config = entry.data
    ip = config[CONF_IP_ADDRESS]
    device = CozyLifeDevice(ip)
    sensor = CozyPowerSensor(config, entry.entry_id, device)
    async_add_entities([sensor])

    async def refresh_state(_now=None):
        try:
            async with async_timeout.timeout(TIMEOUT):
                await hass.async_add_executor_job(sensor.update)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout while updating Cozy Power sensor")
        except Exception as e:
            _LOGGER.error(f"Error updating Cozy Power sensor: {e}")

    await refresh_state()
    async_track_time_interval(hass, refresh_state, SCAN_INTERVAL)

class CozyPowerSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, config, entry_id, device):
        self._device = device
        self._ip = config[CONF_IP_ADDRESS]
        base_name = config.get(CONF_NAME, f"Cozy Power {self._ip}")
        self._attr_name = f"{base_name}"
        self._attr_unique_id = f"cozy_power_{self._ip}"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ip)},
            name=base_name,
            manufacturer="CozyLife",
            model="Smart Plug",
            sw_version="1.0",
        )
        self._state = None
        self._available = True
        self._error_count = 0
        self._max_errors = 3
        self.update()

    def update(self):
        try:
            data = self._device.query_state()
            if data and "28" in data:
                self._state = float(data["28"])
                self._available = True
                self._error_count = 0
            else:
                self._handle_error("No power data received")
        except Exception as e:
            self._handle_error(f"Failed to update sensor: {e}")

    def _handle_error(self, msg):
        self._error_count += 1
        if self._error_count >= self._max_errors:
            self._available = False
            _LOGGER.error(f"{msg}. Marking device unavailable.")
        else:
            _LOGGER.warning(f"{msg}. Retry count: {self._error_count}/{self._max_errors}")

    @property
    def available(self):
        return self._available

    @property
    def native_value(self):
        return self._state
