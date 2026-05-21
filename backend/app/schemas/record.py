from pydantic import BaseModel, Field


class RecordContent(BaseModel):
    content: str
    disabled: bool = False


class RecordSetCreate(BaseModel):
    name: str
    type: str
    ttl: int = Field(..., ge=0, le=2147483647)
    records: list[RecordContent]
    comment: str | None = Field(None, max_length=500)
    changetype: str = "REPLACE"


class RecordSetDelete(BaseModel):
    name: str
    type: str
    changetype: str = "DELETE"


class BulkRecordOperation(BaseModel):
    rrsets: list[RecordSetCreate | RecordSetDelete]


SUPPORTED_RECORD_TYPES = [
    "A", "AAAA", "CNAME", "MX", "NS", "TXT", "SRV", "CAA", "TLSA",
    "PTR", "SOA", "NAPTR", "SSHFP", "DNSKEY", "DS", "ALIAS", "HTTPS", "SVCB",
]
