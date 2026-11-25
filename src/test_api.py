import os
import requests
import json
import argparse
import webbrowser
import socket
from pathlib import Path
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Load environment variables from .env
env_path = Path(".") / ".env"
if not load_dotenv(dotenv_path=env_path):
    print(f"Warning: .env file not found at {env_path.absolute()}")

# LinkedIn API credentials
CLIENT_ID = os.getenv("LI_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("LI_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("LI_REDIRECT_URI", "http://localhost:8080/").strip()
ACCESS_TOKEN = os.getenv("LI_ACCESS_TOKEN", "").strip()

class AuthCodeHandler(BaseHTTPRequestHandler):
    """Handles the redirect from LinkedIn to capture the auth code."""
    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        if "code" in params:
            self.server.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authentication Successful!</h1><p>You can close this window and return to the terminal.</p>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Authentication Failed</h1><p>No authorization code found.</p>")

def run_local_server(port):
    """Starts a temporary HTTP server to receive the auth code."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, AuthCodeHandler)
    httpd.auth_code = None
    print(f"Waiting for authentication on {REDIRECT_URI}...")
    httpd.handle_request()
    return httpd.auth_code

def get_access_token_via_auth_flow():
    """
    Obtain an access token using the Authorization Code Flow.
    """
    if ACCESS_TOKEN:
        return ACCESS_TOKEN

    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: LI_CLIENT_ID or LI_CLIENT_SECRET is missing in .env")
        return None

    # Step 1: Redirect user to LinkedIn's authorization URL
    # Using older scopes which are often the default for many apps
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": "random_state_string",
        "scope": "r_liteprofile r_emailaddress",
    }
    
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + requests.compat.urlencode(params)

    print("\n--- LinkedIn Authentication ---")
    print(f"Authorization URL: {auth_url}")
    print("\nOpening your browser to authorize the application...")
    webbrowser.open(auth_url)

    # Step 2: Start local server to catch the redirect
    port = urlparse(REDIRECT_URI).port or 8080
    auth_code = run_local_server(port)

    if not auth_code:
        print("Error: Failed to obtain authorization code.")
        return None

    # Step 3: Exchange authorization code for an access token
    print("Exchanging authorization code for an access token...")
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get("access_token")
        if token:
            print("Access token obtained successfully.")
            return token
    except Exception as e:
        print(f"Error exchanging code for token: {e}")
        if 'response' in locals():
            print(f"Response: {response.text}")
    return None

def fetch_and_save_profile(profile_id=None):
    """
    Fetch profile information from LinkedIn API and save it to li/{profile_id}.json.
    """
    token = get_access_token_via_auth_flow()
    if not token:
        return

    # Using the standard /v2/me endpoint for r_liteprofile
    endpoint = "https://api.linkedin.com/v2/me" if not profile_id else f"https://api.linkedin.com/v2/people/id={profile_id}"
    filename = profile_id if profile_id else "me"

    headers = {
        "Authorization": f"Bearer {token}",
        "Connection": "Keep-Alive",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    try:
        print(f"Fetching profile data from: {endpoint}")
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        profile_data = response.json()

        output_dir = Path("li")
        output_dir.mkdir(exist_ok=True)

        output_path = output_dir / f"{filename}.json"
        with open(output_path, "w") as f:
            json.dump(profile_data, f, indent=4)

        print(f"Profile data successfully saved to {output_path}")
        return profile_data

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch LinkedIn profile data.")
    parser.add_argument("--profile", type=str, help="LinkedIn profile ID (optional, defaults to 'me')")
    args = parser.parse_args()

    fetch_and_save_profile(args.profile)


