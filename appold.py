from flask import Flask, request, jsonify
import re
import logging
import os
import requests
import openai
from logging.handlers import RotatingFileHandler
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import pyodbc  # For MSSQL connection
import uuid 

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

# MSSQL Database Configuration
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

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

def get_db_connection():
    """Establish a connection to the MSSQL database."""
    try:
        connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_HOST},{DB_PORT};"
            f"DATABASE={DB_NAME};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
        )
        conn = pyodbc.connect(connection_string)
        app.logger.info("Successfully connected to MSSQL database.")
        return conn
    except pyodbc.Error as e:
        app.logger.error(f"Error connecting to MSSQL database: {str(e)}")
        raise

def insert_into_enquiry_detail(extracted_data):
    """Insert lead data into EnquiryDetail table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # SQL query to insert data into EnquiryDetail
        query = """
        INSERT INTO EnquiryDetail (
            Enq_Id, Enq_Date, Name, Mobile, Email, Proprty_ref, Descrip, Budget, Remark, Firstnm, Lastnm
        ) VALUES (
            ?, GETDATE(), ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
        # Map extracted data to EnquiryDetail fields
        cursor.execute(query, (
            extracted_data["Enq_Id"],
            extracted_data["firstnm"] + " " + extracted_data.get("middlenm", ""),
            extracted_data["mobile"],
            extracted_data["email"],
            extracted_data.get("Proprty_ref", "N/A"),
            extracted_data.get("Descrip", "N/A"),
            extracted_data.get("Budget", 0),
            extracted_data.get("Remark", "N/A"),
            extracted_data["firstnm"],
            extracted_data.get("lastnm", "N/A")
        ))

        conn.commit()
        conn.close()
        return {"message": "Data successfully inserted into EnquiryDetail"}
    except Exception as e:
        app.logger.error(f"Error inserting data into EnquiryDetail: {str(e)}")
        return {"error": "Database error while inserting into EnquiryDetail"}

# Routes
@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "message": "AI Chatbot API is running",
        "version": "1.0.0",
        "documentation": "/docs"
    })

import uuid  # Import UUID module for unique ID generation

def extract_data_from_message(message):
    """Extract structured data from unstructured text input."""
    extracted_data = {
        "Enq_Id": str(uuid.uuid4()),  # Generate unique ID
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

    # Extract name (basic heuristic: look for "my name is", "I am", or similar patterns)
    name_match = re.search(r"(my name is|I am|this is|name is)\s+([a-zA-Z]+)", message, re.IGNORECASE)
    if name_match:
        extracted_data["firstnm"] = name_match.group(2).strip()

    # Log extracted data for debugging
    app.logger.info(f"Extracted data: {extracted_data}")

    return extracted_data
if __name__ == "__main__":
    # Use environment variables for configuration
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))

    # Run the app with production-ready settings
    app.run(debug=debug_mode, host=host, port=port)