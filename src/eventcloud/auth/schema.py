from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True
