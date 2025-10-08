from google_auth_oauthlib.flow import InstalledAppFlow
import json

# Scopes yang diperlukan (sesuaikan dengan bot Anda)
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

# Path ke file JSON credentials yang sudah didownload
CLIENT_CONFIG_FILE = 'client_secret_752764582243-6l76s65tdfgum0k9klcvm0tocvutabo9.apps.googleusercontent.com.json'

def get_refresh_token():
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_CONFIG_FILE, 
        SCOPES
    )
    
    # Akan membuka browser untuk authorize
    credentials = flow.run_local_server(port=0)
    
    print("CLIENT_ID:", credentials.client_id)
    print("CLIENT_SECRET:", credentials.client_secret)
    print("REFRESH_TOKEN:", credentials.refresh_token)
    
    return credentials

if __name__ == "__main__":
    get_refresh_token()