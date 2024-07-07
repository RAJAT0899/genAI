import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
from flask import Flask, render_template, request, jsonify
import logging
import os
import google.generativeai as genai
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from database import init_db, save_website_text, get_website_text

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
WEBSITE_URL = "https://pratiyogitanirdeshika.com/"

# Function to extract text from a URL
def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        return soup.get_text(separator=' ')  # Use space separator to avoid text clumping
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching text from URL: {url} - {e}", exc_info=True)
        return ""

# Function to extract all pages within a website
def extract_all_pages_from_website(url):
    cached_text = get_website_text(url)
    if cached_text:
        logging.info(f"Using cached text for URL: {url}")
        return cached_text

    base_url = urlparse(url).scheme + "://" + urlparse(url).netloc
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        links = [urljoin(base_url, link["href"]) for link in soup.find_all("a", href=True)]

        with ThreadPoolExecutor(max_workers=10) as executor:  # Adjust the number of workers as needed
            pages = list(tqdm(executor.map(extract_text_from_url, links), total=len(links), desc="Fetching pages", unit="page"))

        website_text = " ".join(pages)
        save_website_text(url, website_text)  # Save fetched text to database
        return website_text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching pages from website: {url} - {e}", exc_info=True)
        return ""

# Function to generate a response using the Gemini API
def generate_response_gemini(query, context, max_tokens):
    try:
        # Use only the website text as context
        context_length = min(13000, len(context))
        prompt = f"You are an assistant ChatBot who is Based only on the following content:\n\n{context[:context_length]}...\n\nAnswer the question: {query}with engaging emojis\n\nIf user ask anything apart from the content just gracefully tell them what is in your content\n\nAdditionally, provide three follow-up questions related to the topic."

        logging.info(f"Sending request to Gemini API with prompt: {prompt[:100]}...")  # Log first 100 chars of prompt
        response = gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,  # Adjusted for more coherent responses
                top_p=0.9,
                top_k=40,
                max_output_tokens=max_tokens,
            )
        )
        logging.info(f"Generated response: {response.text}")

        # Split the response into the main answer and follow-up questions
        response_parts = response.text.split("\n\nFollow-up questions:\n")
        answer = response_parts[0].strip()
        follow_up_questions = response_parts[1].strip().split("\n") if len(response_parts) > 1 else []

        # Limit follow-up questions to three
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
        website_text = extract_all_pages_from_website(WEBSITE_URL)
        return jsonify({'website_text': website_text})
    except Exception as e:
        logging.error(f"Error in scrape_website endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()
        user_input = data.get('message', '').strip()
        website_text = data.get('website_text', '')
        max_tokens = 2048
        response = generate_response_gemini(user_input, website_text, max_tokens=max_tokens)
        return jsonify(response)
    except Exception as e:
        logging.error(f"Error in predict endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    init_db()  # Initialize the database when running the script
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000, debug=True)