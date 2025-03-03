import requests
import json

url = "https://test.api.amadeus.com/v1/security/oauth2/token"

payload = 'client_id=J4G3KDKElwjlhNGqP123qmKkUJ2AC3gK&client_secret=wJMNaxiv3AyHEvUW&grant_type=client_credentials'
headers = {
  'Content-Type': 'application/x-www-form-urlencoded'
}

response = requests.request("POST", url, headers=headers, data=payload)

# Parse the JSON response
response_data = json.loads(response.text)

# Access the access_token
access_token = response_data.get("access_token")

# Update the .env file with the new access_token
with open('.env', 'r') as env_file:
    lines = env_file.readlines()

# Write back to the .env file, replacing the old token
with open('.env', 'w') as env_file:
    for line in lines:
        if line.startswith('AMADEUS_ACCESS_TOKEN='):
            env_file.write(f'AMADEUS_ACCESS_TOKEN={access_token}\n')
        else:
            env_file.write(line)

print(access_token)
