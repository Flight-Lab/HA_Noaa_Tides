"""Error types for the NOAA Tides integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ApiError:
    """Base class for API errors with user-friendly messages."""

    code: str
    message: str
    technical_detail: Optional[str] = None
    help_url: Optional[str] = None


class NoaaApiError(Exception):
    """Exception for NOAA API errors."""

    def __init__(self, api_error: ApiError, operation: str = "API call") -> None:
        """Initialize the exception.

        Args:
            api_error: The API error details
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        self.api_error = api_error
        super().__init__(api_error.message)


class NdbcApiError(Exception):
    """Exception for NDBC API errors."""

    def __init__(self, api_error: ApiError, operation: str = "API call") -> None:
        """Initialize the exception.

        Args:
            api_error: The API error details
        """
        operation_desc = f" during {operation}" if operation else ""
        self.api_error = api_error
        super().__init__(api_error.message)


class StationNotFoundError(NoaaApiError):
    """Exception raised when a NOAA station is not found."""

    def __init__(self, station_id: str, operation: str = "API call") -> None:
        """Initialize the exception.

        Args:
            station_id: The station ID that was not found
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        api_error = ApiError(
            code="station_not_found",
            message=f"Station {station_id}: Not found. {operation_desc}. Please verify the station ID.",
            help_url="https://tidesandcurrents.noaa.gov/stations.html",
        )
        super().__init__(api_error)


class BuoyNotFoundError(NdbcApiError):
    """Exception raised when an NDBC buoy is not found."""

    def __init__(self, buoy_id: str, operation: str = "API call") -> None:
        """Initialize the exception.

        Args:
            buoy_id: The buoy ID that was not found
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        api_error = ApiError(
            code="buoy_not_found",
            message=f"Buoy {buoy_id}: Not found. {operation_desc}. Please verify the buoy ID.",
            help_url="https://www.ndbc.noaa.gov/stations.shtml",
        )
        super().__init__(api_error)


class NoaaConnectionTimeoutError(NoaaApiError):
    """Exception raised when a connection to NOAA API times out."""

    def __init__(self, station_id: str, operation: str = "API call") -> None:
        """Initialize the exception.

        Args:
            station_id: The station ID
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        api_error = ApiError(
            code="timeout",
            message=f"Station {station_id}: Connection to NOAA timed out. {operation_desc}. Please check your internet connection.",
        )
        super().__init__(api_error)


class NdbcConnectionTimeoutError(NdbcApiError):
    """Exception raised when a connection to NDBC API times out."""

    def __init__(self, buoy_id: str, operation: str = "API call") -> None:
        """Initialize the exception.

        Args:
            buoy_id: The buoy ID
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        api_error = ApiError(
            code="timeout",
            message=f"Buoy {buoy_id}: Connection to NDBC timed out. {operation_desc}. Please check your internet connection.",
        )
        super().__init__(api_error)


class ServerError(Exception):
    """Exception raised when a server error occurs."""

    def __init__(
        self,
        source_id: str,
        status_code: int,
        is_noaa: bool = True,
        operation: str = "API call",
    ) -> None:
        """Initialize the exception.

        Args:
            source_id: The station or buoy ID
            status_code: The HTTP status code
            is_noaa: Whether this is a NOAA station (True) or NDBC buoy (False)
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        prefix = "Station" if is_noaa else "Buoy"
        service_name = "NOAA" if is_noaa else "NDBC"

        api_error = ApiError(
            code=f"server_error_{status_code}",
            message=f"{prefix} {source_id}: {service_name} service is temporarily unavailable. {operation_desc}. Please try again later.",
            technical_detail=f"Status: {status_code}",
        )

        if is_noaa:
            super().__init__(NoaaApiError(api_error))
        else:
            super().__init__(NdbcApiError(api_error))


class RateLimitError(Exception):
    """Exception raised when rate limits are exceeded."""

    def __init__(
        self, source_id: str, is_noaa: bool = True, operation: str = "API call"
    ) -> None:
        """Initialize the exception.

        Args:
            source_id: The station or buoy ID
            is_noaa: Whether this is a NOAA station (True) or NDBC buoy (False)
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        prefix = "Station" if is_noaa else "Buoy"
        service_name = "NOAA" if is_noaa else "NDBC"

        api_error = ApiError(
            code="rate_limit",
            message=f"{prefix} {source_id}: Too many requests to {service_name} API. {operation_desc}. Please try again later.",
            technical_detail="Status: 429",
        )

        if is_noaa:
            super().__init__(NoaaApiError(api_error))
        else:
            super().__init__(NdbcApiError(api_error))


class InvalidDataError(Exception):
    """Exception raised when invalid data is received."""

    def __init__(
        self,
        source_id: str,
        error_detail: str = "",
        is_noaa: bool = True,
        operation: str = "API call",
    ) -> None:
        """Initialize the exception.

        Args:
            source_id: The station or buoy ID
            error_detail: Additional error details
            is_noaa: Whether this is a NOAA station (True) or NDBC buoy (False)
            operation: Description of the operation being performed
        """
        operation_desc = f" during {operation}" if operation else ""
        prefix = "Station" if is_noaa else "Buoy"
        service_name = "NOAA" if is_noaa else "NDBC"

        api_error = ApiError(
            code="invalid_data",
            message=f"{prefix} {source_id}: Received invalid data from {service_name} service. {operation_desc}.",
            technical_detail=error_detail,
        )

        if is_noaa:
            super().__init__(NoaaApiError(api_error))
        else:
            super().__init__(NdbcApiError(api_error))
