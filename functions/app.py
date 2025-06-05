# functions/app.py
from awsgi import response
from src.app import app    # import your Flask `app` object

def handler(event, context):
    return response(app, event, context)
