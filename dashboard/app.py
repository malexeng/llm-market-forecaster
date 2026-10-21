"""dashboard/app.py"""
import time
from flask import Flask, render_template, jsonify, request
from skill.database import get_recent_forecasts, get_recent_reports, get_accuracy_stats


def create_app(state: dict) -> Flask:
    app = Flask(__name__, template_folder="templates")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        up = int(time.time() - state.get("uptime_start", time.time()))
        h, r = divmod(up, 3600); m, s = divmod(r, 60)
        return jsonify({
            "uptime":      f"{h}h {m}m {s}s",
            "llm_status":  state.get("llm_status", "checking"),
            "llm_model":   state.get("llm_model", "—"),
            "running":     state.get("running", False),
            "last_run":    state.get("last_run", "Never"),
            "next_run":    state.get("next_run", "—"),
            "status_msg":  state.get("status_msg", "Idle"),
        })

    @app.route("/api/forecasts")
    def api_forecasts():
        return jsonify(get_recent_forecasts(20))

    @app.route("/api/reports")
    def api_reports():
        return jsonify(get_recent_reports(7))

    @app.route("/api/accuracy")
    def api_accuracy():
        return jsonify(get_accuracy_stats(days=30))

    @app.route("/api/control", methods=["POST"])
    def api_control():
        action = request.json.get("action")
        state[f"{action}_signal"] = True
        return jsonify({"ok": True})

    return app
