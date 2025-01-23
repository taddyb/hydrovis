"""A file to support reading/managing JSON-LD formatted data"""
import asyncio
import hashlib
import json
import os
from typing import Any, List

import lxml
import httpx
import redis
import redis.exceptions
from rdflib import Graph
import xmltodict

from rnr.client import async_get
from rnr.schemas.weather import Site
from rnr.schemas.nwps import GaugeData
from rnr.settings import Settings

settings = Settings()

def fetch_weather_products(headers) -> list[Any]:
    url = "https://api.weather.gov/products"
    headers = {
        'Accept': 'application/ld+json',
        'User-Agent': '(water.noaa.gov, Tadd.N.Bindas@rtx.com)'
    }
    
    params = {
        'type': 'HML'
    }

    timeout_config = httpx.Timeout(
        connect=5.0,
        read=30.0,
        write=5.0,
        pool=5.0
    )
    
    limits_config = httpx.Limits(
        max_keepalive_connections=5,
        max_connections=10,
        keepalive_expiry=30.0
    )
    
    with httpx.Client(timeout=timeout_config, limits=limits_config) as client:
        response = client.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            response_json = response.json()
            response_json['@context']["@version"] = float(response_json['@context']["@version"])
            
            data = json.dumps(response_json)
            g = Graph()
            g.parse(data=data, format='json-ld')
            data_dict = xmltodict.parse(g.serialize(format="pretty-xml"))
            return data_dict['rdf:RDF']['rdf:Description']
        else:
            print(f"Error fetching data: {response.status_code}")
            raise Exception


async def format_xml(product_text: str) -> List[GaugeData]:
    """A function to format the product text from HML into valid XML segments
    """
    xml_split = product_text.split("?xml")
    forecasts = []

    # ignore the first one since it's not valid XML
    for i in range(1, len(xml_split)):
        xml_segment = "<?xml" + xml_split[i][:-2]  # adding removed XML tag, and removed trailing tags
        try:
            site = Site.from_xml(xml_segment)
        except lxml.etree.XMLSyntaxError:
            xml_segment = xml_segment.split("</site>")[0] + "</site>"  # Removing extra content at end of document
            site = Site.from_xml(xml_segment)
        endpoint = f"{settings.BASE_URL}/gauges/{site.properties['id']}"
        try:
            forecast = await async_get(endpoint)
            gauge_data = GaugeData(**forecast)
            if gauge_data.ForecastFloodCategory in settings.STAGES:
                forecasts.append(gauge_data)
        except httpx.HTTPStatusError as e:
            print(f"{endpoint} hit 404 error: {str(e)}")
            
    return forecasts 


def create_forecast_hash(hml_id: str, forecasts: List[GaugeData]) -> str:
    if len(forecasts) == 0:
        val = hml_id
    else:
        val = "".join([forecast.lid for forecast in forecasts])
    return hashlib.sha256(val.encode()).hexdigest()


async def main():
    headers = {
        'Accept': 'application/ld+json',
        'User-Agent': '(water.noaa.gov, Tadd.N.Bindas@rtx.com)'
    }
    hml_data = fetch_weather_products(headers)
    if os.getenv("REDIS_URL") is not None:
        redis_url = os.getenv("REDIS_URL")
    else:
        redis_url = "localhost"
    try:
        r = redis.Redis(host=redis_url, port=6379, decode_responses=True)
        for hml in hml_data:
            hml_id = hml["id"]
            if r.get(hml_id) is None:
                hml_url = hml['@rdf:about']
                site_data = await async_get(hml_url, headers=headers)
                forecasts = await format_xml(site_data["productText"])
                forecast_hash = create_forecast_hash(hml_id, forecasts)
                r.set(hml_id, forecast_hash)


    except redis.exceptions.ConnectionError as e:
        raise e("Cannot run Redis service") 
    

if __name__ == "__main__":
    asyncio.run(main())

