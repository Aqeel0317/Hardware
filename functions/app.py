# filepath: functions/app.py
import awsgi
from flask import Flask, render_template

app = Flask(__name__)


def handler(event, context):
    return awsgi.response(app, event, context)
