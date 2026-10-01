from pydantic import BaseModel

class GoogleNewsConfigUpdate(BaseModel):
    q: str
    hl: str
    gl: str
    ceid: str
    when: str
    site: str
    intitle: str
    max_results: int