from flask import Flask, request, jsonify
import psycopg2
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

@app.route('/log', methods=['POST'])
def log_query():
    data = request.get_json()

    required_fields = ["chat_session_id", "user_id", "user_name", "query", "ai_response", "citations", "login_session_id"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing one or more required fields."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        insert_query = """
            INSERT INTO azaisearch_logging (chat_session_id, user_id, user_name, query, ai_response, citations, login_session_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cur.execute(insert_query, (
            data["chat_session_id"],
            data["user_id"],
            data["user_name"],
            data["query"],
            data["ai_response"],
            data["citations"],
            data["login_session_id"]
        ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Log inserted successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
