import time, uuid
def envelope(data=None,message="ok",request_id=None):
    return {"code":0,"message":message,"request_id":request_id or str(uuid.uuid4()),"timestamp":int(time.time()),"data":data if data is not None else {}}
