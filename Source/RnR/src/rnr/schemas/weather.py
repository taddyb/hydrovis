from datetime import datetime
from typing import Dict, List, Optional 

from pydantic_xml import BaseXmlModel, element
from pydantic import BaseModel, Field

class Disclaimers(BaseXmlModel, tag='disclaimers'):
    AHPSXMLversion: str = element(tag="AHPSXMLversion")
    status: str = element(tag="status")
    quality: Optional[str] = element(tag="quality", default=None)
    standing: Optional[str] = element(tag="standing", default=None)

class Datum(BaseXmlModel, tag='datum'):
    valid: str = element(tag="valid")
    primary: str = element(tag="primary")
    secondary: str = element(tag="secondary")

class Observed(BaseXmlModel, tag="observed"):
    properties: Dict[str, str]
    datum: List[Datum] = element(tag='datum')

class Site(BaseXmlModel, tag='site'):
    properties: Dict[str, str]
    disclaimers: Disclaimers
    observed: Optional[Observed] = None

class HML(BaseModel):
    rdf: str = Field(alias="@rdf:about")
    id: str
    wmo_collective_id: str = Field(alias="wmoCollectiveId")
    issuing_office: str = Field(alias="issuingOffice")
    issuance_time: datetime = Field(alias="issuanceTime")
    product_code: str = Field(alias="productCode")
    product_name: str = Field(alias="productName")

    class Config:
        populate_by_name = True
