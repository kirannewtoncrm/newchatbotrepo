from flask import Flask, request, jsonify
import re
import logging
import os
import requests
from logging.handlers import RotatingFileHandler
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Initialize Flask App
app = Flask(__name__)

# Configure ProxyFix for IIS (corrected)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Configure CORS
CORS(app, resources={r"/add_lead": {"origins": ["http://localhost:3000", "http://192.168.1.13:3000"]}}, supports_credentials=True)

# Environment Variables
NEWTON_CRM_API = os.getenv("CRM_API_URL", "https://newtonerp.in/NewtonApps/NewtonCrmAI/EnquiryDetails/AddLead")

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

        if not data:
            app.logger.error("Empty request body received.")
            return jsonify({"error": "Invalid request. No data provided"}), 400

        app.logger.info(f"Incoming request data: {data}")

        # Assigning default "Enq_Id" if missing
        extracted_data = {
            "Enq_Id": data.get("Enq_Id", "12345"),  # Default ID if not provided
            "firstnm": data.get("firstnm", "").strip(),
            "email": data.get("email", "").strip(),
            "mobile": data.get("mobile", "").strip()
        }

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
    app.run(debug=True)
