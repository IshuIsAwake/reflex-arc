"""
server.py — runs ON THE PI. Flask bridge between (a) a browser-based manual
test page and (b) Unity, both talking the same tiny JSON API, driving the
real motors via motor_control.Rover.

Run:
    python3 server.py
Then on any device on the same network:
    http://<pi-ip>:5000/          -> manual button-driven test UI
Unity (or curl/Postman) hits the same endpoints:
    POST /drive   {"throttle": 0.5, "turn": 0.0}
    POST /stop
    GET  /status

prototype8/game/rover_link.py -- same repo, one directory up -- is what sends
/drive and /stop pulses for an LLM-planned route. Sharing a repo with the
planner changes nothing here: this machine stays a dumb motor relay and knows
nothing about plans, routes, or grids. That separation is the point, and it is
easier to erode now that both halves are checked out together.
"""

from flask import Flask, request, jsonify, render_template
from motor_control import Rover

app = Flask(__name__)
# Template edits (index.html) take effect on the next request with no restart
# needed -- just refresh the browser. NOT using debug=True/use_reloader=True:
# Werkzeug's reloader re-execs this whole script in a subprocess, which would
# construct a second Rover() and crash on "GPIO busy" fighting the first for
# the same pins. Python (.py) changes still need a manual restart.
app.config["TEMPLATES_AUTO_RELOAD"] = True
rover = Rover()

last_command = {"throttle": 0.0, "turn": 0.0}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/drive", methods=["POST"])
def drive():
    data = request.get_json(force=True, silent=True) or {}
    throttle = float(data.get("throttle", 0.0))
    turn = float(data.get("turn", 0.0))
    rover.drive(throttle, turn)
    last_command["throttle"] = throttle
    last_command["turn"] = turn
    return jsonify(ok=True, throttle=throttle, turn=turn)


@app.route("/stop", methods=["POST"])
def stop():
    rover.stop()
    last_command["throttle"] = 0.0
    last_command["turn"] = 0.0
    return jsonify(ok=True)


@app.route("/status")
def status():
    return jsonify(last_command=last_command)


if __name__ == "__main__":
    try:
        # host=0.0.0.0 so it's reachable from Unity running on another
        # machine on the same network, not just localhost on the Pi.
        app.run(host="0.0.0.0", port=5000)
    finally:
        rover.cleanup()
