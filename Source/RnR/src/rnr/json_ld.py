"""A file to support reading/managing JSON-LD formatted data"""
import json
import os
from typing import Any

import httpx
import redis
import redis.exceptions
from rdflib import Graph
import xmltodict

from rnr.client import get

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

if __name__ == "__main__":
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
                site_data = get(hml_url, headers=headers)
                product_text = site_data["productText"]

    except redis.exceptions.ConnectionError as e:
        raise e("Cannot run Redis service") 

