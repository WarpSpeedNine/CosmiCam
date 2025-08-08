import os
import secrets
from functools import wraps
from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

def require_admin_access(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        admin_key = os.getenv('COSMICAM_ADMIN_API_KEY')
        
        if not admin_key:
            return jsonify({'error': 'API key not configured'}), 500
            
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing authorization header'}), 401
            
        api_key = auth_header[7:]  # Remove 'Bearer ' prefix
        if not secrets.compare_digest(api_key, admin_key):
            return jsonify({'error': 'Invalid API key'}), 403
            
        return f(*args, **kwargs)
    return decorated