import json
from datetime import datetime
from typing import Any

import requests
from pydantic import AnyHttpUrl, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.exceptions import HTTPError, RequestException

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import operator


class Settings(BaseSettings):
    """Settings for communicating with the Distiller API. ENV
    variables will contain the necessary secrets."""

    model_config = SettingsConfigDict(case_sensitive=True)
    DISTILLER_API_URL: AnyHttpUrl
    DISTILLER_API_KEY_NAME: str
    DISTILLER_API_KEY: str


class Location(BaseModel):
    """The location of a data set. If host is perlmutter then
    the streaming operation is finished. The path is the path to the data.

    Attributes
    ----------
    host : str
        The name of the host where the data is located. e.g. Perlmutter
    path : str
        The file path on the host to where the data is located.
    """

    host: str  # you'll look for host = perlmutter
    path: str


class Scan(BaseModel):
    """Information about a scan captured in the Distiller system.

    A Scan contains metadata and location data from a 4D Camera dataset,
    including identifiers for both the Distiller system. Each scan tracks
    multiple location points and maintains creation timestamp information.

    Attributes
    ----------
    id : int
        Unique identifier for the scan within the Distiller system.
    scan_id : int, optional
        Identifier from the 4D camera system. May be None if the scan
        was not captured using 4D camera equipment.
    locations : list[Location]
        List of Location objects representing spatial data points
        captured during the scan.
    created : datetime
        Timestamp indicating when the scan was created.
    image_path : str, optional
        File path to an associated image. Defaults to None if no image
        is stored with the scan.
    metadata : dict, optional
        The metadata for the scan.
    notes : str, optional
        Notes from Distiller
    """

    id: int  # distiller id
    scan_id: int | None  # scan id from 4d camera
    locations: list[Location]
    created: datetime
    image_path: str | None = None
    notes: str | None
    metadata: dict[str, Any] | None  # = Field(alias="metadata_")


def get_scans(
    skip: int = 0,
    limit: int = 100,
    scan_id: int = -1,
    start: datetime | None = None,
    end: datetime | None = None,
    job_id: int | None = None,
) -> list[Scan]:
    """
    Fetch a list of scans with various filter options.

    Parameters:
        skip (int): Number of records to skip.
        limit (int): Maximum number of records to return.
        scan_id (int): Specific scan ID to filter by.
        start (Optional[datetime]): Start of the date range for creation time.
        end (Optional[datetime]): End of the date range for creation time.
        job_id (Optional[int]): Job ID to filter by.

    Returns:
        List[Scan]: A list of Scan objects matching the criteria.

    Raises:
        HTTPError: If the request fails due to an HTTP error.
        RequestException: For any other request-related errors.
    """
    headers = {
        settings.DISTILLER_API_KEY_NAME: settings.DISTILLER_API_KEY,
        "Content-Type": "application/json",
    }

    params: dict[str, Any] = {
        "skip": skip,
        "limit": limit,
    }

    if scan_id != -1:
        params["scan_id"] = scan_id
    if start is not None:
        params["start"] = start.isoformat()
    if end is not None:
        params["end"] = end.isoformat()
    if job_id is not None:
        params["job_id"] = job_id

    url = f"{settings.DISTILLER_API_URL}/scans"

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        json_data = response.json()
        return [Scan(**scan_data) for scan_data in json_data]
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")


def add_metadata(distiller_scan_id: int, metadata: dict[str, Any]):
    """Update the metadata field in Distiller. This can be used to
    store updated or supplemental metadata for a 4D STEM scan.

    Parameters
    ----------
    distiller_scan_id : int
        The Distiller scan id. This is a unique ID attached to each data set in the database.
    metadata : dict
        The metadata to merge into the existing metadata field in Distiller.

    Returns
    -------
    : Scan
        A Scan class object with information about the scan that was changed
    """

    headers = {
        settings.DISTILLER_API_KEY_NAME: settings.DISTILLER_API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.DISTILLER_API_URL}/scans/{distiller_scan_id}"
    params = {"merge": True}

    try:
        response = requests.patch(
            url,
            headers=headers,
            params=params,
            data=json.dumps({"metadata": metadata}),
        )
        response.raise_for_status()
        json_data = response.json()
        # print(json_data)
        return Scan(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")


logger = get_logger()
global settings
settings = Settings()

@operator
def update_distiller_metadata(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """Adds information about a scan to the Disitller metadata"""
    global settings
    if not inputs:
        logger.warning("No input provided to the update_distiller_metadata operator.")
        return None

    # TODO: Implement operator logic here
    logger.info("update_distiller_metadata operator running...")

    # We have to have a scan_number to identify the scan in Distiller
    if "scan_number" in inputs.header.meta:
        scan_number = inputs.header.meta["scan_number"]
        logger.info(f"Detector Scan Number: {scan_number}")
    else:
        logger.info("Detector Scan Number not found in metadata.")
        return

    # Extract C12 magnitude and angle from metadata if available
    direct_ptycho_params = inputs.header.meta.get("direct_ptycho_params", None)
    if direct_ptycho_params is not None:
        C12_magnitude = direct_ptycho_params.get("C12", None)
        C12_angle = direct_ptycho_params.get("phi12", None)

    if C12_magnitude is not None and C12_angle is not None:
        logger.info(f"C12: {C12_magnitude} {C12_angle}")
        # Add metadata to Distiller via its API
        # We can only use the detector scan_number to identify the scan in Distiller
        logger.info("Querying Distiller for matching scan...")
        scans = get_scans(limit=3)
        logger.info(f"Retrieved {len(scans)} scans from Distiller.")
        scan_ids = []
        if scans:
            for scan in scans:
                if scan.scan_id == scan_number:
                    logger.info(f"Found matching Distiller scan ID: {scan.id}")
                    # save this scan_id
                    scan_ids.append(scan.id)
                else:
                    logger.info(
                        f"No matching scan found for detector scan number: {scan_number}"
                    )
        else:
            logger.info("No scans found in Distiller.")

        if len(scan_ids) > 1:
            logger.warning(
                f"Multiple Distiller scans found for detector scan number: {scan_number}. Not updating metadata."
            )
        elif len(scan_ids) == 1:
            distiller_scan_id = scan_ids[0]
            logger.info(f"Updating metadata for Distiller scan ID: {distiller_scan_id}")

            # Prepare metadata payload
            metadata_payload = {
                "C12_magnitude": C12_magnitude,
                "C12_angle": C12_angle,
            }
            updated_scan = add_metadata(distiller_scan_id, metadata_payload)
            logger.info(f"Updated Distiller scan metadata: {updated_scan.metadata}")
    else:
        logger.info("C12 Magnitude or phi12 not found in metadata.")
        return

    return None
