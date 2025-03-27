from flask import Flask, request, jsonify
from flask_cors import CORS
import pyttsx3
import pymssql

app = Flask(__name__)
CORS(app)
CORS(app, resources={r"/*": {"origins": "*"}})

# ✅ Aapke SQL Server ke connection details (pymssql ke format me)
DB_CONFIG = {
    "server": "3.109.247.242",
    "user": "kiran",
    "password": "Kiran_123!!",
    "database": "newton_crm_ai"
}

user_data = {"name": None, "email": None, "phone": None}

def speak(text):
    """Text-to-Speech Function"""
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

@app.route("/chat", methods=["POST"])
def chat():
    """Chatbot API to Handle User Messages"""
    global user_data
    data = request.json
    user_message = data.get("message", "").lower()
    
    if "add one lead" in user_message:
        user_data = {"name": None, "email": None, "phone": None}  # Reset user data
        response = "Yes, we can do that. Please tell me your name."
    
    elif "my name is" in user_message:
        user_data["name"] = user_message.replace("my name is ", "").strip()
        response = f"Got it, {user_data['name']}. Please provide an email."
    
    elif "my email is" in user_message:
        user_data["email"] = user_message.replace("my email is ", "").strip()
        response = "Email recorded. Please provide a phone number."

    elif "my phone is" in user_message:
        user_data["phone"] = user_message.replace("my phone is ", "").strip()

        if all(user_data.values()):
            try:
                conn = pymssql.connect(**DB_CONFIG)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Leads (Name, Email, Phone) VALUES (%s, %s, %s)", 
                               (user_data["name"], user_data["email"], user_data["phone"]))
                conn.commit()
                conn.close()
                response = "Lead successfully added!"
            except Exception as e:
                response = f"Database error: {str(e)}"
        else:
            response = "Some details are missing. Please try again."

    else:
        response = "Sorry, I didn't understand. Can you please repeat?"

    speak(response)
    return jsonify({"reply": response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
