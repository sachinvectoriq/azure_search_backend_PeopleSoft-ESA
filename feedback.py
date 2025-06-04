from flask import Flask, request, jsonify
import psycopg2
from datetime import datetime
import os

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT')
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


# --- Route to insert feedback ---
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.get_json()

        # Extracting values from JSON
        session_id = data.get("session_id")
        user_name = data.get("user_name")
        query = data.get("query")
        ai_response = data.get("ai_response")
        citations = data.get("citations")
        feedback_type = data.get("feedback_type")
        feedback = data.get("feedback")

        # Connect to PostgreSQL
        conn = get_db_connection()

        cursor = conn.cursor()

        # Insert into table
        insert_query = """
            INSERT INTO azaisearch_feedback 
            (session_id, user_name, date_and_time, query, ai_response, citations, feedback_type, feedback)
            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
        """

        cursor.execute(insert_query, (
            session_id, user_name, query, ai_response,
            citations, feedback_type, feedback
        ))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Feedback submitted successfully"}), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Run the app ---
if __name__ == '__main__':
    app.run(debug=True)
