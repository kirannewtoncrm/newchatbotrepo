from flask import Flask, request, jsonify
import re
import logging
import os
import requests
import openai
from logging.handlers import RotatingFileHandler
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv  # Import dotenv to load environment variables

# Load environment variables from .env file
load_dotenv()

# Initialize Flask App
app = Flask(__name__)

# Configure ProxyFix for IIS (corrected)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Configure CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")
CORS(app, resources={r"/add_lead": {"origins": CORS_ORIGINS}}, supports_credentials=True)

# Environment Variables
NEWTON_CRM_API = os.getenv("CRM_API_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Logging Setup
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
LOG_FILE_PATH = os.path.join(LOG_DIR, 'app.log')

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Helper Functions
def validate_phone(phone):
    """Validate Indian phone numbers with optional country code"""
    pattern = r"^(\+91[\-\s]?)?[0]?(91)?[789]\d{9}$"
    return bool(re.fullmatch(pattern, phone.strip())) if phone else False

def validate_email(email):
    """Basic email validation"""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.fullmatch(pattern, email.strip())) if email else False

def extract_data_from_message(message):
    """Extract structured data from unstructured text input."""
    extracted_data = {
        "Enq_Id": "12345",  # Default ID
        "firstnm": "",
        "email": "",
        "mobile": ""
    }

    # Extract email
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", message)
    if email_match:
        extracted_data["email"] = email_match.group(0)

    # Extract mobile number (Indian format)
    mobile_match = re.search(r"(\+91[\-\s]?)?[0]?(91)?[789]\d{9}", message)
    if mobile_match:
        extracted_data["mobile"] = mobile_match.group(0)

    # Extract name (basic heuristic: look for "my name is" or similar patterns)
    name_match = re.search(r"(my name is|I am|this is)\s+([a-zA-Z]+)", message, re.IGNORECASE)
    if name_match:
        extracted_data["firstnm"] = name_match.group(2).strip()

    return extracted_data

# Routes
@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "message": "AI Chatbot API is running",
        "version": "1.0.0",
        "documentation": "/docs"
    })

@app.route('/add_lead', methods=['OPTIONS'])
def handle_preflight():
    """Handles CORS preflight requests"""
    response = jsonify({"message": "CORS preflight successful"})
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    return response

@app.route('/add_lead', methods=['POST'])
def add_lead():
    """Handle lead submission with validation"""
    try:
        data = request.get_json(silent=True) or {}
        app.logger.info(f"Received payload: {data}")  # Log the entire payload

        if not data or "message" not in data:
            app.logger.error("Invalid request. No message provided.")
            return jsonify({"error": "Invalid request. No message provided"}), 400

        app.logger.info(f"Incoming request message: {data['message']}")

        # Extract data from the unstructured message
        extracted_data = extract_data_from_message(data["message"])
        app.logger.info(f"Extracted data: {extracted_data}")

        # Validate required fields
        required_fields = ['Enq_Id', 'firstnm', 'email', 'mobile']
        missing_fields = [field for field in required_fields if not extracted_data.get(field)]
        if missing_fields:
            app.logger.warning(f"Missing fields: {missing_fields}")
            return jsonify({"error": "Missing required fields", "missing": missing_fields}), 400

        # Validate email and phone
        if not validate_email(extracted_data['email']):
            app.logger.error(f"Invalid email: {extracted_data['email']}")
            return jsonify({"error": "Invalid email format"}), 400

        if not validate_phone(extracted_data['mobile']):
            app.logger.error(f"Invalid phone: {extracted_data['mobile']}")
            return jsonify({"error": "Invalid phone number"}), 400

        # API Call to Newton CRM
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(NEWTON_CRM_API, json=extracted_data, headers=headers, timeout=10)
            response.raise_for_status()

            app.logger.info(f"CRM API Response: {response.json()}")
            return jsonify({"message": "Lead submitted successfully", "crm_response": response.json()}), response.status_code

        except requests.exceptions.HTTPError as http_err:
            app.logger.error(f"CRM API HTTP Error: {http_err.response.text}")
            return jsonify({"error": "CRM API returned an error", "details": http_err.response.text}), http_err.response.status_code
        except requests.exceptions.RequestException as req_err:
            app.logger.error(f"CRM API Connection Error: {str(req_err)}")
            return jsonify({"error": "Failed to connect to CRM system", "details": str(req_err)}), 503

    except Exception as e:
        app.logger.exception("Unexpected error in add_lead endpoint")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

if __name__ == "__main__":
    # Use environment variables for configuration
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))

    # Run the app with production-ready settings
    app.run(debug=debug_mode, host=host, port=port)