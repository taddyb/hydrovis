"""A file to support reading/managing JSON-LD formatted data"""
import asyncio
from datetime import datetime
import hashlib
import json
from typing import Any, List

import aio_pika
import lxml
import httpx
import redis
import redis.exceptions
from rdflib import Graph
from tqdm import tqdm
import xmltodict

from rnr.client import async_get, get
from rnr.schemas.weather import Site
from rnr.schemas.nwps import GaugeData, ProcessedData, Reach, ReachClassification
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
            # print(f"Error fetching data: {response.status_code}")
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
            # print(f"{endpoint} hit 404 error: {str(e)}")
            pass
            
    return forecasts 


def create_forecast_hash(hml_id: str, forecasts: List[GaugeData]) -> str:
    if len(forecasts) == 0:
        val = hml_id
    else:
        val = "".join([forecast.lid for forecast in forecasts])
    return hashlib.sha256(val.encode()).hexdigest()


def get_reach_flow(reach_id):
    flow_endpoint = f"{settings.BASE_URL}/reaches/{reach_id}/streamflow?series=short_range"
    reach_flow = get(flow_endpoint)
    return Reach(
        reach_id=reach_id,
        downstream_reach_id=int(reach_flow["reach"]["route"]["downstream"][0]["reachId"]),
        reach_classification=ReachClassification.flowline,
        times=[data["validTime"] for data in reach_flow["shortRange"]["series"]["data"]],
        forecast=[data["flow"] for data in reach_flow["shortRange"]["series"]["data"]]
    )


def fetch_all_flows(processed_data: ProcessedData, gauge_data: GaugeData) -> List[Reach]:
    endpoint = f"{settings.BASE_URL}/gauges/{gauge_data.downstreamLid}"
    forecast = get(endpoint)
    ending_reach_id = int(forecast["reachId"])
    output = []
    downstream_reach_id = processed_data.reaches[0].downstream_reach_id
    while downstream_reach_id != ending_reach_id:
        reach = get_reach_flow(downstream_reach_id)
        output.append(reach)
        downstream_reach_id = reach.downstream_reach_id
    end_reach = get_reach_flow(ending_reach_id)
    output.append(end_reach)
    return output


async def publish(channel: aio_pika.channel, forecasts: List[GaugeData]) -> None:
    if not channel:
        raise RuntimeError(
            "Message could not be sent as there is no RabbitMQ Connection"
        )
    if len(forecasts) > 0:
        for gauge_data in forecasts:
            forecast_endpoint = f"{settings.BASE_URL}/gauges/{gauge_data.lid}/stageflow/forecast"
            site_data = await async_get(forecast_endpoint)
            if site_data["data"][0]["secondary"] == -999:
                continue
            else:
                metadata_endpoint = f"{settings.BASE_URL}/reaches/{gauge_data.reachId}"
                downstream_metadata = get(metadata_endpoint)
                downstream_reach_id = int(downstream_metadata["route"]["downstream"][0]["reachId"])
                processed_data = ProcessedData(
                    lid = gauge_data.lid,
                    downstream_lid = gauge_data.downstreamLid,
                    reaches = [
                        Reach(
                            reach_id=gauge_data.reachId,
                            downstream_reach_id=downstream_reach_id,
                            reach_classification=ReachClassification.rfc_point,
                            times = [val["validTime"] for val in site_data["data"]],
                            forecast=[val["secondary"] for val in site_data["data"]],
                        )
                    ]
                )
                flowline_data = fetch_all_flows(processed_data, gauge_data)
                processed_data.reaches.extend(flowline_data)
            async with channel.transaction():
                msg = processed_data.json().encode()
                try:
                    await channel.default_exchange.publish(
                        aio_pika.Message(body=msg),
                        routing_key=settings.flooded_data_queue,
                        mandatory=True
                    )
                except aio_pika.exceptions.DeliveryError as e:
                    print(f"Message rejected: {e}")
                

async def main():
    connection = await aio_pika.connect_robust(
        settings.aio_pika_url,
        heartbeat=30
    )

    async with connection:
        channel = await connection.channel(publisher_confirms=False)
        await channel.declare_queue(
            settings.flooded_data_queue,
            durable=True
        )
        print("Successfully connected to RabbitMQ")
        headers = {
            'Accept': 'application/ld+json',
            'User-Agent': '(water.noaa.gov, Tadd.N.Bindas@rtx.com)'
        }
        hml_data = fetch_weather_products(headers)
        try:
            r = redis.Redis(
                host=settings.redis_url,
                port=settings.redis_port,
                decode_responses=True
            )
            hml_data = sorted(hml_data, key=lambda x: datetime.fromisoformat(x["issuanceTime"]))
            for hml in tqdm(hml_data, desc="reading through api.weather.gov HML outputs"):
                hml_id = hml["id"]
                if r.get(hml_id) is None:
                    hml_url = hml['@rdf:about']
                    site_data = await async_get(hml_url, headers=headers)
                    forecasts = await format_xml(site_data["productText"])
                    await publish(channel, forecasts)
                    forecast_hash = create_forecast_hash(hml_id, forecasts)
                    r.set(hml_id, forecast_hash)
        except redis.exceptions.ConnectionError as e:
            raise e("Cannot run Redis service") 
        

if __name__ == "__main__":
    asyncio.run(main())
