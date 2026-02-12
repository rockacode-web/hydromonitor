"""
Flask Documentation:     https://flask.palletsprojects.com/
Jinja2 Documentation:    https://jinja2.palletsprojects.com/
Werkzeug Documentation:  https://werkzeug.palletsprojects.com/
This file creates your application.
"""

import site
from app import app, Config, mongo, Mqtt

from flask import (
    escape,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    make_response,
    send_from_directory,
)
from json import dumps, loads
from werkzeug.utils import secure_filename
from os import getcwd
from os.path import join, exists

#####################################
#   NEW: Latest + Control endpoints #
#####################################


@app.route("/api/climo/latest", methods=["GET"])
def climo_latest():
    """Return the most recent sensor document (by timestamp)."""
    try:
        # Use the same connection logic as your DB class uses
        # We avoid depending on "private" methods.
        from pymongo import MongoClient
        from urllib import parse

        host = Config.DB_SERVER or "127.0.0.1"
        port = Config.DB_PORT or "27017"

        if not Config.DB_USERNAME or not Config.DB_PASSWORD:
            uri = f"mongodb://{host}:{port}"
        else:
            user = parse.quote_plus(Config.DB_USERNAME)
            pwd = parse.quote_plus(Config.DB_PASSWORD)
            uri = f"mongodb://{user}:{pwd}@{host}:{port}"

        client = MongoClient(uri, tls=False)
        doc = client.ELET2415.climo.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])

        return jsonify({"status": "success", "data": doc})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "data": None}), 500


@app.route("/api/mqtt/control", methods=["POST"])
def mqtt_control():
    """
    Receive controls JSON from frontend and publish to MQTT topic: 620171712_sub

    Frontend sends:
      { "brightness": 120, "leds": 3, "color": { "r":255, "g":0, "b":0, "a":1 } }

    ESP32 expects:
      { "type":"controls", "brightness":120, "leds":3, "red":255, "green":0, "blue":0 }
    """
    try:
        data = request.get_json(force=True, silent=False)

        if not isinstance(data, dict):
            return jsonify({"status": "bad request", "message": "JSON body must be an object"}), 400

        topic = "620171712_sub"

        color = data.get("color") or {}
        payload = {
            "type": "controls",
            "leds": int(data.get("leds", 0)),
            "brightness": int(data.get("brightness", 128)),
            "red": int(color.get("r", 0)),
            "green": int(color.get("g", 0)),
            "blue": int(color.get("b", 0)),
        }

        ok = Mqtt.publish(topic, dumps(payload))
        if not ok:
            return jsonify({"status": "error", "message": "MQTT publish failed"}), 500

        return jsonify({"status": "success", "topic": topic, "payload": payload})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


#####################################
#   Routing for your application    #
#####################################


@app.route("/api/climo/get/<start>/<end>", methods=["GET"])
def get_all(start, end):
    """RETURNS ALL THE DATA FROM THE DATABASE THAT EXIST IN BETWEEN THE START AND END TIMESTAMPS"""
    try:
        start_ts = int(start)
        end_ts = int(end)
    except Exception:
        return jsonify({"status": "bad request", "message": "start/end must be unix timestamps"}), 400

    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    data = mongo.getAllInRange(start_ts, end_ts) or []
    return jsonify({"status": "success", "data": data})


@app.route("/api/mmar/temperature/<start>/<end>", methods=["GET"])
def get_temperature_mmar(start, end):
    """RETURNS MIN, MAX, AVG AND RANGE FOR TEMPERATURE. THAT FALLS WITHIN THE START AND END DATE RANGE"""
    try:
        start_ts = int(start)
        end_ts = int(end)
    except Exception:
        return jsonify({"status": "bad request", "message": "start/end must be unix timestamps"}), 400

    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    data = mongo.temperatureMMAR(start_ts, end_ts) or []
    return jsonify({"status": "success", "data": data})


@app.route("/api/mmar/humidity/<start>/<end>", methods=["GET"])
def get_humidity_mmar(start, end):
    """RETURNS MIN, MAX, AVG AND RANGE FOR HUMIDITY. THAT FALLS WITHIN THE START AND END DATE RANGE"""
    try:
        start_ts = int(start)
        end_ts = int(end)
    except Exception:
        return jsonify({"status": "bad request", "message": "start/end must be unix timestamps"}), 400

    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    data = mongo.humidityMMAR(start_ts, end_ts) or []
    return jsonify({"status": "success", "data": data})


@app.route("/api/frequency/<variable>/<start>/<end>", methods=["GET"])
def get_freq_distro(variable, start, end):
    """RETURNS FREQUENCY DISTRIBUTION FOR SPECIFIED VARIABLE"""
    variable = (variable or "").strip().lower()
    allowed = {"temperature", "humidity", "heatindex", "timestamp"}
    if variable not in allowed:
        return jsonify({"status": "bad request", "message": f"variable must be one of {sorted(list(allowed))}"}), 400

    try:
        start_ts = int(start)
        end_ts = int(end)
    except Exception:
        return jsonify({"status": "bad request", "message": "start/end must be unix timestamps"}), 400

    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    data = mongo.frequencyDistro(variable, start_ts, end_ts) or []
    return jsonify({"status": "success", "data": data})


@app.route("/api/file/get/<filename>", methods=["GET"])
def get_images(filename):
    """RETURNS REQUESTED FILE FROM UPLOADS FOLDER"""
    safe_name = secure_filename(filename)

    if not Config.UPLOADS_FOLDER:
        return jsonify({"status": "server misconfigured", "message": "UPLOADS_FOLDER not set"}), 500

    upload_dir = join(getcwd(), Config.UPLOADS_FOLDER)
    file_path = join(upload_dir, safe_name)

    if not exists(file_path):
        return jsonify({"status": "file not found"}), 404

    return send_from_directory(upload_dir, safe_name, as_attachment=False)


@app.route("/api/file/upload", methods=["POST"])
def upload():
    """SAVES A FILE TO THE UPLOADS FOLDER"""
    if "file" not in request.files:
        return jsonify({"status": "bad request", "message": "missing form-data field: file"}), 400

    if not Config.UPLOADS_FOLDER:
        return jsonify({"status": "server misconfigured", "message": "UPLOADS_FOLDER not set"}), 500

    file = request.files["file"]
    if not file or file.filename.strip() == "":
        return jsonify({"status": "bad request", "message": "empty filename"}), 400

    filename = secure_filename(file.filename)
    upload_dir = join(getcwd(), Config.UPLOADS_FOLDER)
    file.save(join(upload_dir, filename))

    return jsonify({"status": "File upload successful", "filename": filename})


###############################################################
# The functions below should be applicable to all Flask apps. #
###############################################################


@app.route("/<file_name>.txt")
def send_text_file(file_name):
    file_dot_text = file_name + ".txt"
    return app.send_static_file(file_dot_text)


@app.after_request
def add_header(response):
    response.headers["X-UA-Compatible"] = "IE=Edge,chrome=1"
    response.headers["Cache-Control"] = "public, max-age=0"
    return response


@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": 404, "message": "Not Found"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"status": 405, "message": "Method Not Allowed"}), 405
