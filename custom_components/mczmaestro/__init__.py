# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022-2024 Matthieu Bourgain (Aohzan), originally Apache-2.0, modified by lucensius
# Copyright (C) 2026 lucensius
"""MCZ Maestro integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CHRONO, CONTROLLER, COORDINATOR, DOMAIN, MANAGER, UNDO_UPDATE_LISTENER
from .manager import ChronoManager
from .maestro import CONNECTION_ERRORS, MaestroController
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MCZ Maestro from a config entry."""
    config = entry.data

    controller = await hass.async_add_executor_job(
        MaestroController, config[CONF_HOST], config[CONF_PORT]
    )

    if not controller.connected:
        raise ConfigEntryNotReady(
            f"Can't connect to MCZ {config[CONF_HOST]}:{config[CONF_PORT]}"
        )
    _LOGGER.debug("Connected to MCZ")

    last_chrono = None

    def fetch_data() -> dict:
        """Read the information frame and the weekly program."""
        nonlocal last_chrono
        data = controller.request_info()
        try:
            last_chrono = controller.read_chrono()
        except (*CONNECTION_ERRORS, ValueError) as err:
            _LOGGER.warning("Could not read chrono program: %s", err)
        data[CHRONO] = last_chrono
        return data

    async def async_update_data():
        """Fetch data from API."""
        try:
            return await hass.async_add_executor_job(fetch_data)
        except CONNECTION_ERRORS as err:
            raise UpdateFailed(f"Error communicating with MCZ: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=config[CONF_SCAN_INTERVAL]),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    undo_listener = entry.add_update_listener(_async_update_listener)

    manager = ChronoManager(hass, entry, controller, coordinator)
    await manager.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CONTROLLER: controller,
        COORDINATOR: coordinator,
        MANAGER: manager,
        CONF_HOST: controller.host,
        CONF_PORT: controller.port,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.host + controller.port)},
        manufacturer="MCZ",
        model="Maestro",
        name="MCZ Maestro",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_setup_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()
    await hass.data[DOMAIN][entry.entry_id][MANAGER].async_unload()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
