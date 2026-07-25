# run dis from backend/ >uv run flask --app main run --debug<

import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

from comments import create_comments_blueprint

load_dotenv()
app = Flask(__name__)

# DB for Comments
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
	"DATABASE_URL",
	"sqlite:///vsff.db",
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Websocket stuff
allowed_frontend_origins = [
	"http://localhost:5173",
	"http://127.0.0.1:5173",
	"http://192.168.4.66:5173",
]

socketio = SocketIO(
	app,
	async_mode="threading",
	cors_allowed_origins=allowed_frontend_origins,
	#logger=True,	# useful for debugging
	#engineio_logger=True, # ^
)

# Adding our comment routes, socket hookup to the app
comments_blueprint = create_comments_blueprint(
	db,
	socketio,
)

app.register_blueprint(comments_blueprint)

''' Ran once
Wacky started using old db from previous project, making a dedicated db now

Local:
DATABASE: vsff_website
DBUSER: website_user


Common:
When changing a db model (think of it like git)
	> uv run flask --app main db migrate -m "Describe change"
	> uv run flask --app main db upgrade

Deploying:
	> git pull
	> uv sync --frozen
	> uv run flask --app main db upgrade
	> sudo systemctl restart vsff-api

Check info:
	uv run python - <<'PY'
	from sqlalchemy import inspect

	from main import app, db

	with app.app_context():
		print("Database:", db.engine.url.database)
		print("Tables:", inspect(db.engine).get_table_names())
	PY
'''

# Sheets
google_sheet_web_app_url = os.environ.get("GOOGLE_SHEET_WEB_APP_URL")

if not google_sheet_web_app_url:
	raise RuntimeError("GOOGLE_SHEET_WEB_APP_URL is not configured")

CORS(
	app,
	resources={
		r"/api/*": {
			"origins": allowed_frontend_origins,
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

# uv run flask --app main run --debug -> uv run python main.py
if __name__ == "__main__":
	socketio.run(
		app,
		host="127.0.0.1",
		port=5000,
		debug=True,
		#use_reloader=False, # temporary disable
	)