import logging
import aiohttp
# Open your api_client.py and ensure line 3 looks locally like this:
from config import PREDICT_API_URL, PREDICT_API_KEY, PREDICT_TIMEOUT_SECONDS

logger = logging.getLogger("namebot.api")

async def predict_pokemon(image_url):
    if not PREDICT_API_URL:
        logger.warning("Prediction API URL is not configured.")
        return None

    headers = {}
    if PREDICT_API_KEY:
        headers["x-license-key"] = PREDICT_API_KEY

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                PREDICT_API_URL,
                headers=headers,
                json={"imageUrl": image_url},
                timeout=aiohttp.ClientTimeout(total=PREDICT_TIMEOUT_SECONDS)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Prediction API returned {response.status}")
                    return None
    except Exception as exc:
        logger.warning(f"Prediction request failed: {exc}")
        return None
