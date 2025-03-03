import os
import openai
import logging
import json
from .models import ChatRequest

# Configure logging
logger = logging.getLogger(__name__)

# Set up OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Initialize the client without proxies
client = openai.OpenAI(
    api_key=api_key,
)

async def generate_chat_response(chat_request: ChatRequest):
    """Generate a chat response using OpenAI API."""
    try:
        # Create parameters for the API call
        params = {
            "model": chat_request.model,
            "messages": [msg.model_dump(exclude_none=True) for msg in chat_request.messages],
            "temperature": chat_request.temperature
        }
        
        # Add tools if they exist
        if chat_request.tools:
            params["tools"] = chat_request.tools
        
        # Add tool_choice if it exists
        if chat_request.tool_choice:
            params["tool_choice"] = chat_request.tool_choice
        
        # Make the API call
        response = client.chat.completions.create(**params)
        return response
        
    except Exception as e:
        logger.error(f"Error generating chat response: {str(e)}")
        raise 