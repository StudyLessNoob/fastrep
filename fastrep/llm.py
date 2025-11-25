import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

class OpenAIClient(LLMClient):
    def __init__(self, api_key, base_url="https://api.openai.com/v1", model="gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        try:
            response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=data, timeout=120)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            if 'response' in locals():
                logger.error(f"Response body: {response.text}")
            raise

class AnthropicClient(LLMClient):
    def __init__(self, api_key, model="claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096
        }
        try:
            response = requests.post(f"{self.base_url}/messages", headers=headers, json=data, timeout=120)
            response.raise_for_status()
            return response.json()['content'][0]['text']
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            if 'response' in locals():
                logger.error(f"Response body: {response.text}")
            raise

class GeminiClient(LLMClient):
    def __init__(self, api_key, model="gemini-pro"):
        self.api_key = api_key
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        data = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }]
        }
        try:
            response = requests.post(self.base_url, params=params, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            if 'response' in locals():
                logger.error(f"Response body: {response.text}")
            raise

def get_llm_client(provider, api_key, model=None, base_url=None):
    if provider == 'openai':
        return OpenAIClient(api_key, model=model or "gpt-3.5-turbo")
    elif provider == 'custom':
        return OpenAIClient(api_key, base_url=base_url, model=model or "local-model")
    elif provider == 'anthropic':
        return AnthropicClient(api_key, model=model or "claude-3-haiku-20240307")
    elif provider == 'gemini':
        return GeminiClient(api_key, model=model or "gemini-pro")
    return None
