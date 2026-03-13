import os

# --- ACCOUNT CONFIGURATION ---
# We use a list of dictionaries to manage your 3 alts independently
ACCOUNTS = [
    {
        "token": os.getenv("TOKEN1"), 
        "spam_channel": 1459841583536148601, 
        "name": "Main Account"
    },
    {
        "token": os.getenv("TOKEN2"), 
        "spam_channel": 1459841583536148601, 
        "name": "Alt Account 1"
    },
    {
        "token": os.getenv("TOKEN3"), 
        "spam_channel": 1459841583536148601, 
        "name": "Alt Account 2"
    }
]
