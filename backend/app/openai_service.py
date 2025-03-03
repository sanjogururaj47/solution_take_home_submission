import openai
import json
from pathlib import Path
from dotenv import dotenv_values
from .models import ChatRequest
import logfire
import logging

logger = logging.getLogger(__name__)
# Get the path to the .env file (one directory up from current file)
env_path = Path(__file__).parent.parent / '.env'

# Load config
config = dotenv_values(env_path)

# Configure Logfire
logfire.configure(token=config['LOGFIRE_TOKEN'])
logfire.instrument_openai()

# Set up OpenAI client
if not config['OPENAI_API_KEY']:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Initialize the client without proxies
client = openai.OpenAI(
    api_key=config['OPENAI_API_KEY']
)

async def generate_chat_response(chat_request: ChatRequest):
    """Generate a chat response using OpenAI API."""
    try:
        logfire.info('openai_request', 
            model=chat_request.model,
            messages_count=len(chat_request.messages),
            has_tools=bool(chat_request.tools)
        )
        
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
        
        logfire.info('openai_response',
            completion_tokens=response.usage.completion_tokens,
            prompt_tokens=response.usage.prompt_tokens,
            total_tokens=response.usage.total_tokens
        )
        
        return response
        
    except Exception as e:
        # More detailed error logging
        logfire.error('openai_error',
            error=str(e),
            error_type=type(e).__name__,
            model=chat_request.model,
            messages_count=len(chat_request.messages)
        )
        raise 