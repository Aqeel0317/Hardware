# filepath: functions/app.py
import awsgi
from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello from Flask on Netlify!"

def handler(event, context):
    return awsgi.response(app, event, context)
