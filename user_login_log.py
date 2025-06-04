from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql
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

@app.route('/log_user', methods=['POST'])
def log_user():
    data = request.get_json()
    if not data or 'user_name' not in data:
        return jsonify({'error': 'Missing "user_name" in request body'}), 400

    user_name = data['user_name']

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        insert_query = sql.SQL("""
            INSERT INTO azaisearch_login_log (user_name)
            VALUES (%s)
            RETURNING login_session_id, user_name, date_and_time;
        """)

        cur.execute(insert_query, [user_name])
        inserted_row = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'message': 'User logged successfully',
            'login_session_id': inserted_row[0],
            'user_name': inserted_row[1],
            'date_and_time': inserted_row[2].strftime("%Y-%m-%d %H:%M:%S")
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
