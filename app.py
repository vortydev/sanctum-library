# app.py
from __future__ import annotations
import os
from flask import Flask, render_template

from blueprints import api_bp
from config import FLASK_PORT

app = Flask(__name__)
app.register_blueprint(api_bp)

@app.context_processor
def inject_flags():
    BAR = True # TEMP
    return {"foo": BAR}

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/scan")
def scan():
    return render_template("scan.html")


if __name__ == "__main__":
    app.run(
        debug=True, 
        host="0.0.0.0", 
        port=FLASK_PORT
    )