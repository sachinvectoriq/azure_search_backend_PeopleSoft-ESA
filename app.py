from flask import Flask, jsonify
from saml import saml_login, saml_callback, extract_token
import os


app = Flask(__name__)




@app.route('/')
def hello():
    return 'Hello!'







from search_query import ask
@app.route('/ask', methods=['POST'])
def call_ask():
    return ask()

from user_login_log import log_user
@app.route('/log/user', methods=['POST'])
def call_log_user():
    return log_user()

from feedback import submit_feedback
@app.route('/feedback', methods=['POST'])
def call_submit_feedback():
    return submit_feedback()

from logging_chat import log_query
@app.route('/log', methods=['POST'])
def call_log_query():
    return log_query()



if __name__ == "__main__":
    app.run(debug=True)
