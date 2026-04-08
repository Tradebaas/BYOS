from pydantic import BaseModel, ConfigDict
from typing import Optional

class TopstepCredentials(BaseModel):
    """
    Credentials for authenticating with the Topstep API.
    These should generally be loaded from environment variables (.env).
    """
    account_id: int
    jwt_token: str

class TopstepOrderResponse(BaseModel):
    """
    Normalized response from the Topstep API after placing an order.
    Used by the Data Vault to log execution timestamps and real IDs.
    """
    success: bool
    order_id: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[int] = None
    
    model_config = ConfigDict(frozen=True)
