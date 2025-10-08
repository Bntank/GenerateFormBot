import os
import requests
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Global cache untuk access_token
_token_cache = {
    'access_token': None,
    'expires_at': None
}

def get_access_token():
    """
    Mendapatkan access_token yang selalu valid dengan otomatis refresh jika diperlukan
    
    Environment variables yang diperlukan:
    - CLIENT_ID: OAuth client ID
    - CLIENT_SECRET: OAuth client secret  
    - REFRESH_TOKEN: OAuth refresh token
    
    Returns:
        str: Valid access_token atau None jika gagal
    """
    try:
        # Ambil credentials dari environment
        client_id = os.environ.get('CLIENT_ID')
        client_secret = os.environ.get('CLIENT_SECRET')
        refresh_token = os.environ.get('REFRESH_TOKEN')
        
        if not all([client_id, client_secret, refresh_token]):
            logger.error("Missing OAuth credentials in environment variables")
            return None
        
        # Cek apakah token masih valid (buffer 5 menit sebelum expired)
        now = datetime.now()
        if (_token_cache['access_token'] and 
            _token_cache['expires_at'] and 
            now < _token_cache['expires_at'] - timedelta(minutes=5)):
            
            logger.info("Using cached access_token")
            return _token_cache['access_token']
        
        # Token expired atau belum ada, lakukan refresh
        logger.info("Refreshing access_token...")
        
        # Request ke OAuth endpoint
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(token_url, data=data, timeout=30)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Extract access_token dan expires_in
            access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)  # default 1 jam
            
            if access_token:
                # Simpan ke cache dengan waktu expired
                _token_cache['access_token'] = access_token
                _token_cache['expires_at'] = now + timedelta(seconds=expires_in)
                
                logger.info(f"Access token refreshed successfully, expires at: {_token_cache['expires_at']}")
                return access_token
            else:
                logger.error("No access_token in response")
                return None
        else:
            logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during token refresh: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}")
        return None

def clear_token_cache():
    """Clear token cache (berguna untuk testing atau reset manual)"""
    global _token_cache
    _token_cache = {
        'access_token': None,
        'expires_at': None
    }
    logger.info("Token cache cleared")

def get_token_info():
    """Get informasi tentang token yang sedang di-cache"""
    if _token_cache['access_token']:
        return {
            'has_token': True,
            'expires_at': _token_cache['expires_at'],
            'is_expired': datetime.now() > _token_cache['expires_at'] if _token_cache['expires_at'] else True
        }
    else:
        return {
            'has_token': False,
            'expires_at': None,
            'is_expired': True
        }