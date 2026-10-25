from flask import Flask,jsonify
from app_core import response
app=Flask(__name__)
@app.route('/',defaults={'path':''})
@app.route('/<path:path>')
def route(path):
    body,status=response('/'+path)
    return jsonify(body),status
