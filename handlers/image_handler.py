# handlers/image_handler.py
import logging
from bs4 import BeautifulSoup
import requests
import base64
from urllib.parse import urlparse
from api_calls import get_xai_auth_header

logger = logging.getLogger()

def handle_image_request(content, query):
    image_url = extract_image_url_from_content(content)
    if image_url:
        logger.info(f"Image URL found: {image_url}, sending for analysis.")
        return analyze_image(image_url=image_url, query=query)
    else:
        logger.warning("No image found in the content.")
        return "Nie znaleziono obrazu w treści zapytania."

def extract_image_url_from_content(content):
    soup = BeautifulSoup(content, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and 'src' in img_tag.attrs:
        return img_tag['src']
    
    # Jeśli nie znaleziono tagu <img>, sprawdź linki w treści
    for a_tag in soup.find_all('a', href=True):
        parsed_url = urlparse(a_tag['href'])
        if parsed_url.path.lower().endswith(('.png', '.jpg', '.jpeg')):
            return a_tag['href']
    
    # Dodatkowe sprawdzanie bez tagów HTML
    text_content = soup.get_text()
    for word in text_content.split():
        parsed_url = urlparse(word)
        if parsed_url.path.lower().endswith(('.png', '.jpg', '.jpeg')):
            return word
    
    return None

def analyze_image(image_url=None, image_path=None, query="What is in this image?"):
    logging.info("Sending image analysis request to xAI Vision")
    headers = {
        "Content-Type": "application/json",
        **get_xai_auth_header()
    }

    if image_url:
        image_content = {
            "type": "image_url",
            "image_url": {
                "url": image_url,
                "detail": "high",
            },
        }
    elif image_path:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        # Determine image MIME type based on file extension
        mime_type = "image/jpeg" if image_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"
        image_content = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded_string}",
                "detail": "high",
            },
        }
    else:
        raise ValueError("Either image_url or image_path must be provided")

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    image_content,
                    {
                        "type": "text",
                        "text": query,
                    },
                ],
            },
        ],
        "model": "grok-2-vision-latest",
        "stream": False,
        "temperature": 0.01,
    }
    response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "Brak odpowiedzi od xAI Vision.")