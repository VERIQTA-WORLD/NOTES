"""Response contracts shared by the container routes and offline tests."""
def response(path):
    if path=='/':return {'message':'Hello from Veriqta on AWS','status':'success'},200
    if path=='/health':return {'status':'ok'},200
    return {'error':'not_found'},404
