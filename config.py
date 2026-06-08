import os

# --- 👥 MULTI-ACCOUNT CONFIGURATION ---
# Groups your account tokens, spam channels, and custom tracking names cleanly
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
    },
    {
        "token": os.getenv("TOKEN4"),
        "spam_channel": 1459841583536148601,
        "name": "Alt Account 3"
    }
]

# --- 🤖 HUGGING FACE INFERENCE GATEWAY SETTINGS ---
# These variables tell your api_client.py exactly how to contact your ONNX brain
PREDICT_API_URL = os.getenv("PREDICT_API_URL", "https://discordbotnhihun-poketwo.hf.space/predict")
PREDICT_API_KEY = os.getenv("PREDICT_API_KEY", "jeetendraiscool")

# Safe network configuration boundary to prevent your script from lagging
PREDICT_TIMEOUT_SECONDS = 2.0
