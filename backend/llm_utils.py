import httpx
from typing import List, Dict, Optional
from memory import MemoryStore


async def ollama_chat(messages: List[Dict[str, str]], ollama_host: str, ollama_model: str) -> str:
    """Send chat messages to Ollama and return the response."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ollama_host}/api/chat",
                json={
                    "model": ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "top_k": 40,
                    }
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
    except httpx.HTTPStatusError as e:
        print(f"Ollama API error: {e}")
        raise Exception(f"Error communicating with Ollama: {str(e)}")


def build_messages(user_id: str, user_text: str, memory: MemoryStore, system_prompt: str) -> List[Dict[str, str]]:
    """Build the messages list for the LLM, including system prompt and relevant memories."""
    try:
        # Get relevant facts from memory
        facts = memory.get_top_facts(user_id=user_id, query=user_text, limit=6)
        memory_block = "\n".join(f"- {f}" for f in facts) if facts else ""

        # Build system prompt with memories if available
        final_system_prompt = system_prompt
        if memory_block.strip():
            final_system_prompt = f"{system_prompt}\n\nMemórias relevantes sobre o usuário:\n{memory_block}"

        return [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_text},
        ]
    except Exception as e:
        print(f"Error building messages: {e}")
        # Return a basic message structure if there's an error
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]


def maybe_extract_fact(user_text: str) -> Optional[str]:
    """Extract potential facts from user text that should be remembered."""
    t = user_text.strip()
    if not t:
        return None

    lower = t.lower()
    prefixes = (
        "meu nome é ",
        "eu me chamo ",
        "eu gosto de ",
        "eu não gosto de ",
        "minha comida favorita é ",
        "minha cor favorita é ",
        "eu moro em ",
        "eu tenho ",
        "eu não tenho ",
        "eu sou ",
        "eu não sou ",
        "eu trabalho como ",
        "eu estudo ",
        "eu moro em ",
        "eu nasci em ",
        "meu aniversário é ",
        "eu tenho medo de ",
        "eu adoro ",
        "eu odeio ",
        "eu prefiro ",
    )
    
    # Check if the text matches any of the fact patterns
    if any(lower.startswith(p) for p in prefixes):
        return t
        
    # Also check for question patterns that might indicate a fact
    question_prefixes = (
        "quem é ",
        "o que é ",
        "qual é ",
        "quando é ",
        "onde fica ",
        "por que ",
        "como é ",
    )
    
    if any(lower.startswith(p) for p in question_prefixes):
        return None
        
    # If the text is a short statement, it might be a fact
    if len(t.split()) <= 15 and t.endswith(('.', '!', '?')):
        return t
        
    return None
