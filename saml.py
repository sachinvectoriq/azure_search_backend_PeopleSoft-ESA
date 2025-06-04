import os
import json
import urllib.parse
import datetime
import jwt  # Import PyJWT for JWT operations
from flask import session, redirect, request, jsonify
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError  # Import JWT exceptions

# SAML and JWT configuration
admin_group_id = os.getenv('ADMIN_GROUP_ID')
redirect_url = os.getenv('REDIRECT_URL')
#admin_group_id = '3ad704ec-ada7-4268-939a-6fdd985b0cfb'
#JWT_SECRET_KEY = 'Vectoriq#qa'  # Replace with your actual JWT secret key
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
# SAML functions
def init_saml_auth(req, saml_path):
    print('In init auth')
    auth = OneLogin_Saml2_Auth(req, custom_base_path=saml_path)
    return auth

def prepare_flask_request(request):
    print('In Prepare Flask')
    url_data = request.url.split('?')
    return {
        'https': 'on',
        'http_host': request.host,
        'script_name': request.path,
        'server_port': request.host.split(':')[1] if ':' in request.host else '443',
        'get_data': request.args.copy(),
        'post_data': request.form.copy(),
    }

def saml_login(saml_path):
    try:
        print('In SAML Login')
        req = prepare_flask_request(request)
        print(f'Request Prepared: {req}')
        auth = init_saml_auth(req, saml_path)
        print('SAML Auth Initialized')
        login_url = auth.login()
        print(f'Redirecting to: {login_url}')
        return redirect(login_url)
    except Exception as e:
        print(f'Error during SAML login: {str(e)}')
        return f'Internal Server Error: {str(e)}', 500

def saml_callback(saml_path):
    req = prepare_flask_request(request)
    auth = init_saml_auth(req, saml_path)
    auth.process_response()
    errors = auth.get_errors()
    group_name = 'user'
    
    if not errors:
        session['samlUserdata'] = auth.get_attributes()
        session['samlNameId'] = auth.get_nameid()
        json_data = session['samlUserdata']
        groups = json_data.get("http://schemas.microsoft.com/ws/2008/06/identity/claims/groups", [])
        
        # Check if the user belongs to the admin group
        if admin_group_id in groups:
            group_name = 'admin'
        
        user_data = {
            'name': session['samlUserdata']['http://schemas.microsoft.com/identity/claims/displayname'],
            'group': group_name
        }
        with open("session_data_from_backend.txt", "w") as file:
        # Write the content of the variable to the file
            file.write(json.dumps(session['samlUserdata'], indent=4))
        token = create_jwt_token(user_data)
        # Redirect to the React dashboard with the user data
        return redirect(f'{redirect_url}?token={token}')
    else:
        return f"Error in SAML Authentication: {errors}-{req}", 500

# JWT functions
def create_jwt_token(user_data):
    # Define the token expiration time (e.g., 1 hour)
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    payload = {
        'user_data': user_data,
        'exp': expiration  # Token expiration time
    }
    # Create the token
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
    return token

def get_data_from_token(token):
    try:
        # Decode the token (this will verify the signature and expiration)
        decoded_data = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        # Extract user data from the decoded token
        user_data = decoded_data.get('user_data')
        return user_data

    except ExpiredSignatureError:
        return 'Error: Token has expired'

    except InvalidTokenError:
        return 'Error: Invalid token'
    
# Function to extract data from token

def extract_token():
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Token is missing"}), 400
    
    user_data = get_data_from_token(token)
    #user_data["user_data"]["name"] = user_data["user_data"]["name"][0] 

    if isinstance(user_data, str) and user_data.startswith("Error"):
        return jsonify({"error": user_data}), 400
    
    return jsonify({"user_data": user_data}), 200
    #return jsonify(user_data), 200
