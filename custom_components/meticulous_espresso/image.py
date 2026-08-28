"""Image platform for Meticulous Espresso integration."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .connection import build_base_url
from .const import DEFAULT_PORT, DOMAIN
from .coordinator import MeticulousPushCoordinator
from .entity import MeticulousEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meticulous image entities."""
    coordinator: MeticulousPushCoordinator = hass.data[DOMAIN][entry.entry_id]["push"]
    async_add_entities([MeticulousProfileImage(coordinator)])


class MeticulousProfileImage(MeticulousEntity, ImageEntity):
    """Image entity showing the active profile image."""

    def __init__(self, coordinator: MeticulousPushCoordinator) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, "profile_image")
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_name = "Profile Image"
        self._attr_icon = "mdi:image"
        self._last_profile: str | None = None

    @property
    def image_url(self) -> str | None:
        """Return the URL of the active profile image."""
        profile = self.coordinator.data.get("active_profile")
        if not profile:
            return None

        # Find profile ID from name
        for pid, name in self.coordinator.available_profiles.items():
            if name != profile:
                continue

            base_url = build_base_url(
                self.coordinator.host, self.coordinator.port or DEFAULT_PORT
            )
            # Newer firmware reports the image path on the profile itself;
            # fall back to the legacy per-profile endpoint.
            path = self.coordinator.profile_images.get(pid)
            if path:
                return f"{base_url}/{path.lstrip('/')}"
            return f"{base_url}/api/v1/profile/{pid}/image"

        return None

    @property
    def image_last_updated(self) -> datetime | None:
        """Return when the image was last updated."""
        current = self.coordinator.data.get("active_profile")
        if current != self._last_profile:
            self._last_profile = current
            return datetime.now()
        return None
