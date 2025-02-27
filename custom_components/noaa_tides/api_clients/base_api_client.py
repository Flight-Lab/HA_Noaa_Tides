"""Base API client for NOAA Tides integration."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Final, Optional, TypeVar

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..const import DEFAULT_TIMEOUT
from ..error_utils import map_exception_to_error
from ..errors import ApiError, NdbcApiError, NoaaApiError
from ..types import CoordinatorData

_LOGGER: Final = logging.getLogger(__name__)
T = TypeVar("T")  # Generic type for return values


class BaseApiClient:
    """Base API client for NOAA and NDBC data sources.

    Provides common functionality for making API requests with
    consistent error handling, logging, and retry logic.

    Error handling strategy:
    - Use _safe_request methods to make API calls with error handling
    - Convert standard exceptions to typed API exceptions
    - Provide user-friendly error messages for end users
    - Log detailed technical information for debugging
    """

    def __init__(
        self,
        hass: HomeAssistant,
        station_id: str,
        timezone: str,
        unit_system: str,
    ) -> None:
        """Initialize the API client.

        Args:
            hass: The Home Assistant instance
            station_id: The station or buoy ID
            timezone: The timezone setting
            unit_system: The unit system to use
        """
        self.hass = hass
        self.station_id = station_id
        self.timezone = timezone
        self.unit_system = unit_system
        self.session = async_get_clientsession(hass)
        self._is_noaa = True  # Will be overridden by subclasses

    async def fetch_data(self, selected_sensors: list[str]) -> CoordinatorData:
        """Fetch data from the API.

        Args:
            selected_sensors: List of sensors to fetch

        Returns:
            CoordinatorData: The fetched data

        Raises:
            NotImplementedError: If the subclass does not implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")

    async def handle_error(
        self, error: Exception, operation: str = "API call"
    ) -> ApiError:
        """Handle API errors and convert to structured ApiError objects.

        Args:
            error: The exception that occurred
            operation: The operation being performed when the error occurred

        Returns:
            ApiError: A structured error object with user-friendly messages
        """
        # Map the exception to a more specific error type
        specific_error = map_exception_to_error(
            error, self.station_id, self._is_noaa, operation
        )

        # Extract ApiError data from the specific error
        if isinstance(specific_error, (NoaaApiError, NdbcApiError)):
            return specific_error.api_error

        # Create a generic ApiError for unknown exceptions
        service_type = "NOAA Station" if self._is_noaa else "NDBC Buoy"
        return ApiError(
            code="unknown_error",
            message=f"{service_type} {self.station_id}: An unexpected error occurred.",
            technical_detail=str(error),
        )

    def _log_error(self, error: ApiError) -> None:
        """Log an API error with appropriate level and format.

        Args:
            error: The API error to log
        """
        service_type = "NOAA Station" if self._is_noaa else "NDBC Buoy"
        _LOGGER.error(
            "%s %s: %s (Code: %s)%s",
            service_type,
            self.station_id,
            error.message,
            error.code,
            f" Technical details: {error.technical_detail}"
            if error.technical_detail
            else "",
        )

    async def _safe_request(
        self, url: str, params: dict[str, Any] = None, timeout: int = DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        """Make a safe request to the API with error handling.

        Automatically retries on connection errors and timeouts
        with exponential backoff. Won't retry HTTP errors except
        for rate limits (429).

        Args:
            url: The URL to request
            params: The request parameters
            timeout: The request timeout in seconds

        Returns:
            dict[str, Any]: The JSON response

        Raises:
            UpdateFailed: If there's an error making the request
        """
        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with self.session.get(
                url, params=params, timeout=client_timeout
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as error:
            api_error = await self.handle_error(error)
            self._log_error(api_error)
            raise UpdateFailed(api_error.message) from error

    async def _safe_request_with_retry(
        self,
        url: str,
        params: dict[str, Any] = None,
        timeout: int = DEFAULT_TIMEOUT,
        method: str = "GET",
        operation: str = "API call",
    ) -> dict[str, Any]:
        """Make a request to the API with retry for transient errors, returning JSON.

        This method will automatically retry on connection errors and timeouts
        with an exponential backoff strategy. It won't retry HTTP errors except
        for rate limits (429).

        Args:
            url: The URL to request
            params: The request parameters
            timeout: The request timeout in seconds
            method: The HTTP method to use (defaults to GET)
            operation: The operation being performed (for error reporting)

        Returns:
            dict[str, Any]: The JSON response

        Raises:
            UpdateFailed: If there's an error making the request after retries
        """
        return await self._make_request_with_retry(
            url, params, timeout, method, response_format="json", operation=operation
        )

    async def _safe_request_with_retry_text(
        self,
        url: str,
        params: dict[str, Any] = None,
        timeout: int = DEFAULT_TIMEOUT,
        method: str = "GET",
        operation: str = "API call",
    ) -> str:
        """Make a request to the API with retry for transient errors, returning text.

        Similar to _safe_request_with_retry but returns text instead of JSON.

        Args:
            url: The URL to request
            params: The request parameters
            timeout: The request timeout in seconds
            method: The HTTP method to use (defaults to GET)
            operation: The operation being performed (for error reporting)

        Returns:
            str: The text response

        Raises:
            UpdateFailed: If there's an error making the request after retries
        """
        return await self._make_request_with_retry(
            url, params, timeout, method, response_format="text", operation=operation
        )

    async def _make_request_with_retry(
        self,
        url: str,
        params: Optional[dict[str, Any]],
        timeout: int,
        method: str,
        response_format: str,
        operation: str = "API call",
    ) -> T:
        """Core implementation of request with retry logic.

        Args:
            url: The URL to request
            params: The request parameters
            timeout: The request timeout in seconds
            method: The HTTP method to use
            response_format: The format to return ("json" or "text")
            operation: The operation being performed

        Returns:
            T: The response in the requested format

        Raises:
            UpdateFailed: If there's an error making the request after retries
        """
        attempts = 0
        max_attempts = 3
        base_wait_time = 2  # seconds

        # Extract endpoint name for better logging
        endpoint = url.split("/")[-1] if "/" in url else url
        operation_with_endpoint = f"{operation} ({endpoint})"

        _LOGGER.debug(
            "%s %s: Attempting %s, format=%s, method=%s",
            "NOAA Station" if self._is_noaa else "NDBC Buoy",
            self.station_id,
            operation_with_endpoint,
            response_format,
            method,
        )

        while attempts < max_attempts:
            try:
                client_timeout = aiohttp.ClientTimeout(total=timeout)

                # Choose the appropriate HTTP method
                if method == "GET":
                    request_method = self.session.get
                elif method == "POST":
                    request_method = self.session.post
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                async with request_method(
                    url, params=params, timeout=client_timeout
                ) as response:
                    if response.status == 429:  # Rate limit
                        retry_after = int(response.headers.get("Retry-After", "60"))
                        _LOGGER.warning(
                            "%s %s: Rate limited. Retrying after %s seconds.",
                            "NOAA Station" if self._is_noaa else "NDBC Buoy",
                            self.station_id,
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        attempts += 1
                        continue

                    response.raise_for_status()

                    # Return the appropriate response format
                    if response_format == "json":
                        return await response.json()
                    elif response_format == "text":
                        return await response.text()
                    else:
                        raise ValueError(
                            f"Unsupported response format: {response_format}"
                        )

            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as err:
                attempts += 1
                if attempts >= max_attempts:
                    api_error = await self.handle_error(
                        err, operation=operation_with_endpoint
                    )
                    self._log_error(api_error)
                    raise UpdateFailed(
                        f"{api_error.message} ({operation_with_endpoint})"
                    ) from err

                # Calculate wait time with exponential backoff and jitter
                wait_time = base_wait_time**attempts + random.uniform(0, 1)
                _LOGGER.debug(
                    "%s %s: Connection error, retrying in %.1f seconds (%d/%d): %s",
                    "NOAA Station" if self._is_noaa else "NDBC Buoy",
                    self.station_id,
                    wait_time,
                    attempts,
                    max_attempts,
                    str(err),
                )
                await asyncio.sleep(wait_time)

            except aiohttp.ClientResponseError as err:
                # Don't retry HTTP errors except rate limits which are handled above
                api_error = await self.handle_error(
                    err, operation=operation_with_endpoint
                )
                self._log_error(api_error)
                raise UpdateFailed(
                    f"{api_error.message} ({operation_with_endpoint})"
                ) from err

            except Exception as err:
                # Don't retry unknown errors
                api_error = await self.handle_error(
                    err, operation=operation_with_endpoint
                )
                self._log_error(api_error)
                raise UpdateFailed(
                    f"{api_error.message} ({operation_with_endpoint})"
                ) from err
