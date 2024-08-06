import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, request, jsonify
import logging
import os
import google.generativeai as genai
from dotenv import load_dotenv
from database import init_db, save_page_text, get_page_text
import time
import urllib.robotparser as robotparser

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='static', template_folder='templates')

# Ensure the API key is passed as a command-line argument
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

# Configure the Gemini API with the API key
genai.configure(api_key=api_key)

# Initialize the Gemini model
gemini_model = genai.GenerativeModel('gemini-1.5-pro')

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
]

# Define the predefined website URL
WEBSITE_URL = "https://flair-solution.com/"
CRAWL_DELAY = 1  # 1 second delay between requests
MAX_DEPTH = 5  # Maximum depth for crawling

# Initialize robots.txt parser
rp = robotparser.RobotFileParser()
rp.set_url(urljoin(WEBSITE_URL, "/robots.txt"))
rp.read()

# Headers to mimic a browser
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def test_website_access():
    try:
        response = requests.get(WEBSITE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        logging.info(f"Successfully accessed {WEBSITE_URL}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to access {WEBSITE_URL}: {e}")
        return False

def crawl_website(url, visited=None, depth=0):
    if visited is None:
        visited = set()
    
    logging.info(f"Attempting to crawl: {url} at depth {depth}")
    
    if url in visited or depth > MAX_DEPTH:
        logging.info(f"Skipping {url}: Already visited or max depth reached")
        return ""

    # Log robots.txt content
    logging.info(f"Robots.txt content: {rp.read()}")
    
    if not rp.can_fetch("*", url):
        logging.warning(f"robots.txt disallows crawling {url}, but proceeding anyway for testing")
    
    visited.add(url)
    
    cached_text = get_page_text(url)
    if cached_text:
        logging.info(f"Using cached text for URL: {url}")
        return cached_text

    try:
        logging.info(f"Fetching content from: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        text = soup.get_text(separator=' ')
        
        logging.info(f"Successfully extracted text from: {url}")
        save_page_text(url, text)
        
        if depth < MAX_DEPTH:
            links = soup.find_all("a", href=True)
            logging.info(f"Found {len(links)} links on {url}")
            
            for link in links:
                href = urljoin(url, link["href"])
                if href.startswith(WEBSITE_URL) and href not in visited:
                    logging.info(f"Queueing {href} for crawling")
                    time.sleep(CRAWL_DELAY)
                    text += crawl_website(href, visited, depth + 1)
        
        return text
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error crawling URL: {url} - {e}", exc_info=True)
        return ""

def extract_all_pages_from_website(url):
    return crawl_website(url)

def generate_response_gemini(query, context, max_tokens):
    try:
        context_length = min(13000, len(context))
        prompt = f"""You are an AI assistant. Your knowledge is based solely on the following content from the website:

{context[:context_length]}...

Using only this information, please answer the following question:

{query}

Provide a clear and concise response, focusing on relevant information and provide source url. If the question is not directly related to the content on the website, politely inform the user that you can only provide information available related to the content of the website.

Include relevant facts, figures, and examples from the website when applicable. If appropriate, use emoji to make your response more engaging, but don't overuse them.

If you're unsure about any information or if it's not covered in the provided content, state that clearly rather than making assumptions."""

        logging.info(f"Sending request to Gemini API with prompt: {prompt[:100]}...")  # Log first 100 chars of prompt
        response = gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                top_p=0.9,
                top_k=40,
                max_output_tokens=max_tokens,
            )
        )
        logging.info(f"Generated response: {response.text}")

        response_parts = response.text.split("\n\nFollow-up questions:\n")
        answer = response_parts[0].strip()
        follow_up_questions = response_parts[1].strip().split("\n") if len(response_parts) > 1 else []

        follow_up_questions = follow_up_questions[:3]

        return {
            'answer': answer,
            'follow_up_questions': follow_up_questions
        }
    except Exception as e:
        logging.error(f"Error generating response: {e}", exc_info=True)
        return {
            'answer': f"Error generating response: {str(e)}",
            'follow_up_questions': []
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape_website', methods=['GET'])
def scrape_website():
    try:
        if not test_website_access():
            return jsonify({'error': 'Unable to access the website'}), 500
        
        website_text = extract_all_pages_from_website(WEBSITE_URL)
        if not website_text:
            return jsonify({'error': 'No content extracted from the website', 'robots_txt': rp.read()}), 500
        
        return jsonify({'website_text': website_text})
    except Exception as e:
        logging.error(f"Error in scrape_website endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e), 'robots_txt': rp.read()}), 500

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()
        user_input = data.get('message', '').strip()
        website_text = extract_all_pages_from_website(WEBSITE_URL)  # Get fresh content for each prediction
        if not website_text:
            return jsonify({'error': 'No content available from the website'}), 500
        max_tokens = 2048
        response = generate_response_gemini(user_input, website_text, max_tokens=max_tokens)
        return jsonify(response)
    except Exception as e:
        logging.error(f"Error in predict endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    init_db()  # Initialize the database when running the script
    app.run(host='0.0.0.0', port=5000, debug=True)