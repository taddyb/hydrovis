from datetime import datetime
from typing import List, OrderedDict

def quicksort_weather_data(data: List[OrderedDict]):
    
    if len(data) <= 1:
        return data
    
    pivot = datetime.fromisoformat(data[-1]["issuanceTime"])

    left = [x for x in data if datetime.fromisoformat(x["issuanceTime"] <= pivot)]
    right = [x for x in data if datetime.fromisoformat(x["issuanceTime"] > pivot)]

    return quicksort_weather_data(left) + [data[-1]] + quicksort_weather_data(right)
