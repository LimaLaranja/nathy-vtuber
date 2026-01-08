import os
import httpx
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

class OpenAIClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.base_url = "https://api.openai.com/v1"
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY não encontrada nas variáveis de ambiente")
    
    async def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """Send chat completion request to OpenAI."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except httpx.HTTPStatusError as e:
            print(f"OpenAI API error: {e}")
            raise Exception(f"Error communicating with OpenAI: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise Exception(f"Unexpected error: {str(e)}")

# Singleton instance
_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client

async def openai_chat(messages: List[Dict[str, str]]) -> str:
    """Convenient function for OpenAI chat completion."""
    client = get_openai_client()
    return await client.chat_completion(messages)
