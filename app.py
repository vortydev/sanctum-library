# app.py
from __future__ import annotations
import os
from flask import Flask, render_template

from blueprints import api_bp
from config import FLASK_PORT, FLASK_ROOT, ENV_MODE, VERSION

app = Flask(__name__)
app.register_blueprint(api_bp)

@app.context_processor
def inject_flags():
    flags = {
        "api_root": FLASK_ROOT,
        "version": VERSION,
    }
    return flags

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/scan")
def scan():
    return render_template("scan.html")


if __name__ == "__main__":
    dev_env = ENV_MODE == "dev"

    if dev_env:
        print(f"\n======================\n\tROUTES\n======================\n{app.url_map}\n======================")

    app.run(
        debug=dev_env, 
        host="0.0.0.0", 
        port=FLASK_PORT
    )