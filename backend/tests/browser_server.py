"""Test-only short first access token; production issuance remains unchanged."""
import os
import time
import jwt
from app.main import app
from app.api import auth

original=auth.issue_access_token
issued=set()


def issue(user_id,session_id,**config):
    token=original(user_id,session_id,**config)
    if os.getenv('BROWSER_SHORT_ACCESS')=='1' and session_id not in issued:
        issued.add(session_id)
        claims=jwt.decode(token,config['key'],algorithms=['HS256'],audience=config['audience'],issuer=config['issuer'])
        claims['exp']=int(time.time())+8
        token=jwt.encode(claims,config['key'],algorithm='HS256')
    return token


auth.issue_access_token=issue
