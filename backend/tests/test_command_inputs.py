from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.realtime.gateway import Chat,Unlock
from app.concierge.service import Ask

@pytest.mark.parametrize('value',['\x00','\ud800','   '])
def test_invalid_text_cannot_reach_database_or_model(value):
    with pytest.raises(ValidationError): Chat(commandId=uuid4(),correlationId=uuid4(),body=value)
    with pytest.raises(ValidationError): Unlock(commandId=uuid4(),correlationId=uuid4(),itemId=uuid4(),expectedPositionVersion=1,reason=value)
    with pytest.raises(ValidationError): Ask(question=value)
