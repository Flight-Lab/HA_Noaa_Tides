"""Error handling utilities for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import aiohttp

from .errors import (
    ApiError,
    BuoyNotFoundError,
    InvalidDataError,
    NdbcApiError,
    NdbcConnectionTimeoutError,
    NoaaApiError,
    NoaaConnectionTimeoutError,
    RateLimitError,
    ServerError,
    StationNotFoundError,
)

_LOGGER: Final = logging.getLogger(__name__)


async def handle_api_error(
    error: Exception, source_id: str, is_noaa: bool = True, operation: str = "API call"
) -> ApiError:
    """Handle API errors and return user-friendly messages.

    Args:
        error: The exception that occurred
        source_id: The station or buoy ID
        is_noaa: Whether this is a NOAA station (True) or NDBC buoy (False)
        operation: Description of the operation being performed

    Returns:
        ApiError: A structured error object with user-friendly messages
    """
    prefix = "Station" if is_noaa else "Buoy"
    service_name = "NOAA" if is_noaa else "NDBC"
    help_url = (
        "https://tidesandcurrents.noaa.gov/stations.html"
        if is_noaa
        else "https://www.ndbc.noaa.gov/stations.shtml"
    )
    operation_desc = f" during {operation}" if operation else ""

    if isinstance(error, asyncio.TimeoutError):
        return ApiError(
            code="timeout",
            message=f"{prefix} {source_id}: Connection timed out{operation_desc}. Please check your internet connection.",
            technical_detail=str(error),
        )

    if isinstance(error, aiohttp.ClientResponseError):
        if error.status == 404:
            return ApiError(
                code=f"{'station' if is_noaa else 'buoy'}_not_found",
                message=f"{prefix} {source_id}: Not found{operation_desc}. Please verify the {('station' if is_noaa else 'buoy')} ID.",
                help_url=help_url,
            )
        if error.status in (500, 502, 503, 504):
            return ApiError(
                code="server_error",
                message=f"{prefix} {source_id}: {service_name} service is temporarily unavailable. {operation_desc}. Please try again later.",
                technical_detail=f"Status: {error.status}",
            )
        if error.status == 429:
            return ApiError(
                code="rate_limit",
                message=f"{prefix} {source_id}: Too many requests to {service_name} API. {operation_desc}. Please try again later.",
                technical_detail=f"Status: {error.status}",
            )
        return ApiError(
            code=f"http_error_{error.status}",
            message=f"{prefix} {source_id}: Unexpected HTTP error occurred.",
            technical_detail=f"Status: {error.status}",
        )

    if isinstance(error, aiohttp.ClientConnectionError):
        return ApiError(
            code="connection_error",
            message=f"{prefix} {source_id}: Could not connect to {service_name} service. {operation_desc}. Please check your internet connection.",
            technical_detail=str(error),
        )

    if isinstance(error, ValueError):
        return ApiError(
            code="invalid_data",
            message=f"{prefix} {source_id}: Received invalid data from {service_name} service. {operation_desc}.",
            technical_detail=str(error),
        )

    # Handle NDBC-specific errors
    if not is_noaa and isinstance(error, UnicodeDecodeError):
        return ApiError(
            code="decode_error",
            message=f"Buoy {source_id}: Could not read NDBC data format. {operation_desc}.",
            technical_detail=str(error),
        )

    return ApiError(
        code="unknown",
        message=f"{prefix} {source_id}: An unexpected error occurred while connecting to {service_name}. {operation_desc}.",
        technical_detail=str(error),
    )


async def handle_noaa_api_error(error: Exception, station_id: str) -> ApiError:
    """Handle NOAA API errors and return user-friendly messages.

    Args:
        error: The exception that occurred
        station_id: The station ID

    Returns:
        ApiError: A structured error object with user-friendly messages
    """
    return await handle_api_error(error, station_id, is_noaa=True)


async def handle_ndbc_api_error(error: Exception, buoy_id: str) -> ApiError:
    """Handle NDBC API errors and return user-friendly messages.

    Args:
        error: The exception that occurred
        buoy_id: The buoy ID

    Returns:
        ApiError: A structured error object with user-friendly messages
    """
    return await handle_api_error(error, buoy_id, is_noaa=False)


def map_exception_to_error(
    exception: Exception,
    source_id: str,
    is_noaa: bool = True,
    operation: str = "API call",
) -> Exception:
    """Map a generic exception to a more specific error type.

    Args:
        exception: The original exception
        source_id: The station or buoy ID
        is_noaa: Whether this is a NOAA station (True) or NDBC buoy (False)
        operation: Description of the operation being performed

    Returns:
        Exception: A more specific exception type
    """
    if isinstance(exception, asyncio.TimeoutError):
        return (
            NoaaConnectionTimeoutError(source_id, operation=operation)
            if is_noaa
            else NdbcConnectionTimeoutError(source_id, operation=operation)
        )

    if isinstance(exception, aiohttp.ClientResponseError):
        if exception.status == 404:
            return (
                StationNotFoundError(source_id, operation=operation)
                if is_noaa
                else BuoyNotFoundError(source_id, operation=operation)
            )
        if exception.status in (500, 502, 503, 504):
            return ServerError(
                source_id, exception.status, is_noaa, operation=operation
            )
        if exception.status == 429:
            return RateLimitError(source_id, is_noaa, operation=operation)

    if isinstance(exception, ValueError):
        return InvalidDataError(source_id, str(exception), is_noaa, operation=operation)

    # For NDBC-specific errors
    if not is_noaa and isinstance(exception, UnicodeDecodeError):
        return InvalidDataError(
            source_id,
            f"Decode error: {str(exception)}",
            is_noaa=False,
            operation=operation,
        )

    # Use a default ApiError for unknown exceptions
    operation_desc = f" during {operation}" if operation else ""
    api_error = ApiError(
        code="unknown",
        message=f"{'Station' if is_noaa else 'Buoy'} {source_id}: An unexpected error occurred{operation_desc}.",
        technical_detail=str(exception),
    )

    return NoaaApiError(api_error) if is_noaa else NdbcApiError(api_error)
