import openai
from dotenv import load_dotenv
import os

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

class URLClassifier:
    def classify(self, url):
        prompt = f"Clasifica la siguiente URL de producto de Costco en una de estas categorías: [lista de categorías]. URL: {url}"
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=prompt,
            max_tokens=50
        )
        return response.choices[0].text.strip()