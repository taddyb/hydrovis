from typing import Any, Dict, Optional

import httpx


def get(
    endpoint: str, params: Optional[Dict[str, Any]] = None, headers=None,
) -> Dict[str, Any]:
    """A synchronous GET request using httpx.

    Parameters
    ----------
    endpoint : str
    - The URL we're hitting.

    params : Optional[Dict[str, Any]], optional
    - The parameters passed to the API endpoint.

    Returns
    -------
    Dict[str, Any]
    - The JSON response from the API.

    Raises
    ------
    NWPSAPIError
    - If the request fails or returns a non-200 status code.
    """
    with httpx.Client() as client:
        try:
            # if params is not None:
            response = client.get(endpoint, params=params, headers=headers)
            # else:
            #     response = client.get(endpoint)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise e("Status Error")
        except httpx.RequestError as e:
            raise e("Request Error")
