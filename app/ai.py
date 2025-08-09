import os
from openai import AsyncOpenAI
import logging
from cachetools import TTLCache  # Кэш на 5 мин

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
cache = TTLCache(maxsize=100, ttl=300)  # Кэш AI-ответов

async def generate_reply(system_prompt: str, history: list, user_message: str):
    key = f"{system_prompt}:{user_message}:{str(history[-3:])}"  # Ключ кэша
    if key in cache:
        return cache[key]
    messages = [{'role': 'system', 'content': system_prompt}]
    if history:
        messages += history[-10:]
    messages.append({'role': 'user', 'content': user_message})
    try:
        logger.debug(f"Sending to OpenAI: {messages}")
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=200,
            temperature=0.8,
        )
        reply = response.choices[0].message.content.strip()
        cache[key] = reply
        return reply
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "(NPC временно молчит — ошибка AI)"