import hashlib
import json
import time

class ConflictError(RuntimeError):
    pass

def session_key(owner, session_id):
    # Fixed-size key, includes authenticated owner so users cannot collide.
    return hashlib.sha256(json.dumps([owner,session_id]).encode()).hexdigest()

def compact(turns):
    # Trim whole turns, never split a toolUse/toolResult exchange.
    kept=list(turns[-3:])
    while kept and len(json.dumps(kept).encode())>48000:
        kept.pop(0)
    return kept

class DynamoMemory:
    def __init__(self, table):
        self.table=table

    def load(self, owner, session_id):
        item=self.table.get_item(Key={"pk":session_key(owner,session_id)},ConsistentRead=True).get("Item")
        if not item:
            return [],0
        version=int(item["version"])
        # TTL deletion is eventual; enforce expiry on every read.
        if int(item["expires_at"])<=int(time.time()):
            return [],version
        return json.loads(item["turns_json"]),version

    def save(self, owner, session_id, turns, version):
        data={"pk":session_key(owner,session_id),"version":version+1,
              "expires_at":int(time.time())+3600,
              "turns_json":json.dumps(compact(turns))}
        kwargs={"Item":data}
        if version:
            kwargs.update(ConditionExpression="#v = :v",ExpressionAttributeNames={"#v":"version"},
                          ExpressionAttributeValues={":v":version})
        else:
            kwargs["ConditionExpression"]="attribute_not_exists(pk)"
        try:
            self.table.put_item(**kwargs)
        except Exception as exc:
            if getattr(exc,"response",{}).get("Error",{}).get("Code")=="ConditionalCheckFailedException":
                raise ConflictError("Concurrent session update; send one request at a time") from exc
            raise
