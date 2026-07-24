# run dis from backend/ >uv run flask --app main run --debug<

import os
import json

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
google_sheet_web_app_url = os.environ.get("GOOGLE_SHEET_WEB_APP_URL")

if not google_sheet_web_app_url:
	raise RuntimeError("GOOGLE_SHEET_WEB_APP_URL is not configured")

CORS(
	app,
	resources={
		r"/api/*": {
			"origins": "http://localhost:5173",
		},
	},
)

def get_prize_tier(count):
	if count < 5:
		return 0 # not enough
	elif count < 15:
		return 1 # total $30
	elif count < 30:
		return 2 # total #100
	else:
		return 3 # total #200

def get_submissions_required_for_tier(tier):
	return {1: 5, 2: 15, 3: 30, 4: 0}[tier]

@app.get("/api/submissions")
def get_submissions():
	web_app_url = os.getenv("GOOGLE_SHEET_WEB_APP_URL")

	if not web_app_url:
		return jsonify({
			"error": "Google Sheets endpoint is not configured",
		}), 500

	try:
		response = requests.get(
			web_app_url,
			timeout=10,
		)
		response.raise_for_status()
		data = response.json()
	except requests.RequestException:
		return jsonify({
			"error": "Could not contact Google Sheets",
		}), 502
	except ValueError:
		return jsonify({
			"error": "Google Sheets returned invalid JSON",
		}), 502
	
	count = int(data.get("count", 0))

	tier = get_prize_tier(count)
	data["prizeTier"] = tier
	data["nextTierRequirement"] = get_submissions_required_for_tier(tier + 1)
	data["submissionsClose"] = "2026-08-17T23:59:59-07:00"

	return jsonify(data)
