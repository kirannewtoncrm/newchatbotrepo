import pymssql

DB_CONFIG = {
    "server": "3.109.247.242",
    "user": "kiran",
    "password": "Kiran_123!!",
    "database": "newton_crm_ai"
}

def save_lead(name, email, phone):
    try:
        conn = pymssql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Leads (Name, Email, Phone) VALUES (%s, %s, %s)", 
                       (name, email, phone))
        conn.commit()
        conn.close()
        return True
    except pymssql.Error as e:
        print(f"Error saving lead: {str(e)}")
        return False
