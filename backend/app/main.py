from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
from dotenv import load_dotenv
from datetime import date
from .models import (
    ChatRequest, 
    ChatMessage, 
    SearchFlightAgent,
    BookFlightAgent,
    SearchHotelAgent,
    BookHotelAgent,
    FlightSearchParams,
    BookFlightParams,
    SearchHotelParams,
    HotelBookingParams,
    TripDetailsAgent,
    GetTripDetailsParams,
    TransferSearchAgent,
    TransferSearchParams,
    TransferBookingParams,
    BookTransferAgent,
)
from .openai_service import generate_chat_response

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get today's date for validation
TODAY = date.today().strftime("%Y-%m-%d")

print(f"\n\n\n\n\n\nTODAY: {TODAY}\n\n\n\n\n")

# Define global system prompt
SYSTEM_PROMPT = f"""Today's date is {TODAY}. You are an AI travel agent for Brainbase Airlines. Start by warmly greeting the user and asking how you can help them with their travel plans today.
You help with 3 services: flights, hotels, and transfers. If the user asks for all 3, handle them one at a time, in this order: flights, hotels, then transfers.
Everytime, before booking, present the user with the default name and traveler information you have, and then proceed as instructed by the user.

CRITICAL FLIGHT BOOKING WORKFLOW:
When a user wants to book a flight, do NOT call the search_flights tool UNLESS you have collected ALL of these details:
   - First ask for their origin airport (Airport code or city, e.g., 'LAX' or Los Angeles)
   - Then ask for their destination airport (Airport code or city, e.g., 'JFK' or New York)
   - Then ask if they'd like to book a one-way or round trip flight
   - If they want a round trip, ask for the return date
   - DO NOT CALL THE search_flights tool before asking if one way or round trip, and make SURE to collect the return date if it's a round trip
   - NEVER call the search_flights tool before this date: {TODAY}
   - Once the flight is booked, prompt the user and ask if they'd like to book a hotel.


CRITICAL HOTEL BOOKING WORKFLOW:
1. When user searches for hotels:
   - FIRST ask for check-in and check-out dates. ALWAYS collect these.
   - Call search_hotels with the city code
   - Present each hotel with:
     * Hotel name
     * Rating
     * Location
     * Starting price (lowest room price)
     * Hotel ID (for reference)
   - Ask if they'd like to know more about any specific hotel

2. When user shows interest in a specific hotel:
   - Show all available room types with:
     * Room category
     * Bed type
     * Price
     * Cancellation policy
   - Ask which room type they'd prefer

CRITICAL TRANSFER BOOKING WORKFLOW:
1. When user shows interest in a specific transfer:
   - Ask for the start location code (airport IATA code or city)
   - Ask for the end location (hotel name, address, city, country)
   - Show all available transfer options with:
     * Price
     * Duration
     * Vehicle type
     * Provider name

If you don't know the answer to something, just say so instead of making up information.
You can use tools when appropriate to fulfill user requests.

HANDLING MULTIPLE SERVICES:
When a user requests multiple services (e.g., flight + hotel or flight + hotel + transfer):
1. Handle one service at a time in a logical order:
   - First follow the workflow for booking flights (since hotel dates depend on flight schedule)
   - Then follow the workflow for booking hotels (using flight arrival/departure dates)
   - Finally follow the workflow for booking transfers if needed

2. Be clear about the process:
   - Tell the user you'll handle each request in sequence
   - Confirm completion of each step before moving to the next
   - Keep track of collected information to avoid asking twice

Example Multi-Service Dialog:
User: "I want to book a flight and hotel in New York"
You: "I'll help you book both your flight and hotel. Let's handle this step by step:

First, let's book your flight to New York:
- Which city will you be flying from?
- When would you like to travel?
- Is this a one-way or round trip?

Once we've booked your flight, I'll help you find a hotel that matches your dates."

[After flight is booked]
You: "Great! Now that we have your flight booked for [dates], let's find you a hotel in New York:
- Do you have any preferences for location or amenities?
- Would you like to stay near any particular area?"

[After hotel is booked]
You: "Great! Now that we have your hotel booked for [dates], let's find you a transfer from the airport to the hotel:
- Do you have any preferences for the transfer?
- Would you like to stay near any particular area?"

After any booking is made, ask the user if they'd like to book another service.

"""

# Initialize all agents
search_flight_agent = SearchFlightAgent()
book_flight_agent = BookFlightAgent()
search_hotel_agent = SearchHotelAgent()
book_hotel_agent = BookHotelAgent()
trip_details_agent = TripDetailsAgent()
transfer_search_agent = TransferSearchAgent()
book_transfer_agent = BookTransferAgent()


AVAILABLE_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for available flights between airports using IATA codes",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin airport IATA code (3 letters, e.g., 'LAX' for Los Angeles)"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination airport IATA code (3 letters, e.g., 'JFK' for New York)"
                    },
                    "departure_date": {
                        "type": "string",
                        "description": "Departure date in YYYY-MM-DD format"
                    }
                },
                "required": ["origin", "destination", "departure_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_flight",
            "description": "Book a flight for a traveler",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_id": {
                        "type": "string",
                        "description": "ID of the selected flight"
                    },
                    "origin": {
                        "type": "string",
                        "description": "Origin airport IATA code"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination airport IATA code"
                    },
                    "departure_date": {
                        "type": "string",
                        "description": "Departure date in YYYY-MM-DD format"
                    },
                    "traveler": {
                        "type": "object",
                        "properties": {
                            "dateOfBirth": {
                                "type": "string",
                                "description": "Date of birth in YYYY-MM-DD format"
                            },
                            "name": {
                                "type": "object",
                                "properties": {
                                    "firstName": {
                                        "type": "string",
                                        "description": "Traveler's first name"
                                    },
                                    "lastName": {
                                        "type": "string",
                                        "description": "Traveler's last name"
                                    }
                                },
                                "required": ["firstName", "lastName"]
                            },
                            "gender": {
                                "type": "string",
                                "description": "Traveler's gender (MALE or FEMALE)",
                                "enum": ["MALE", "FEMALE"]
                            },
                            "contact": {
                                "type": "object",
                                "properties": {
                                    "emailAddress": {
                                        "type": "string",
                                        "description": "Traveler's email address"
                                    },
                                    "phones": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "countryCallingCode": {
                                                    "type": "string",
                                                    "description": "Country calling code (e.g., '1' for USA)"
                                                },
                                                "number": {
                                                    "type": "string",
                                                    "description": "Phone number without country code"
                                                }
                                            },
                                            "required": ["countryCallingCode", "number"]
                                        }
                                    }
                                },
                                "required": ["emailAddress", "phones"]
                            }
                        },
                        "required": ["dateOfBirth", "name", "gender", "contact"]
                    }
                },
                "required": ["flight_id", "origin", "destination", "departure_date", "traveler"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Search for available hotels in a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "cityCode": {
                        "type": "string",
                        "description": "City IATA code (e.g., 'PAR' for Paris)"
                    },
                    "radius": {
                        "type": "integer",
                        "description": "Search radius in KM from city center",
                        "default": 5
                    },
                    "chainCodes": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of hotel chain codes to filter by"
                    },
                    "rating": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of hotel ratings to filter by"
                    }
                },
                "required": ["cityCode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_hotel",
            "description": "Book a hotel. Requires check-in and check-out dates. Requires hotel details from search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hotel_name": {
                        "type": "string",
                        "description": "Name of the hotel from search results"
                    },
                    "address": {
                        "type": "object",
                        "description": "Full address of the hotel from search results",
                        "properties": {
                            "cityName": {"type": "string"},
                            "countryCode": {"type": "string"},
                            "stateCode": {"type": "string"},
                            "postalCode": {"type": "string"},
                            "address": {"type": "string"}
                        }
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format"
                    },
                    "price": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "string"},
                            "currency": {"type": "string"}
                        }
                    },
                    "guests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "firstName": {"type": "string"},
                                "lastName": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["hotel_name", "address", "check_in", "check_out", "price", "guests"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trip_details",
            "description": "Get details of all booked flights, hotels, and transfers for a trip",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {
                        "type": "string",
                        "description": "Optional trip ID. If not provided, returns all trips."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_transfers",
            "description": "Search for available transfers from airport to hotel",
            "parameters": {
                "type": "object",
                "properties": {
                    "startLocationCode": {
                        "type": "string",
                        "description": "Airport IATA code (e.g., 'CDG')"
                    },
                    "endAddressLine": {
                        "type": "string",
                        "description": "Hotel street address"
                    },
                    "endCityName": {
                        "type": "string",
                        "description": "Hotel city"
                    },
                    "endZipCode": {
                        "type": "string",
                        "description": "Hotel postal code"
                    },
                    "endCountryCode": {
                        "type": "string",
                        "description": "Hotel country code (e.g., 'FR')"
                    },
                    "endName": {
                        "type": "string",
                        "description": "Hotel name"
                    },
                    "startDateTime": {
                        "type": "string",
                        "description": "Transfer start time in ISO format (YYYY-MM-DDTHH:mm:ss)"
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Number of passengers"
                    },
                    "endGeoCode": {
                        "type": "string",
                        "description": "Hotel coordinates in 'latitude,longitude' format (e.g., '34.0522,-118.2437')",
                        "pattern": "^-?\\d+\\.\\d+,-?\\d+\\.\\d+$"
                    }
                },
                "required": ["startLocationCode", "endAddressLine", "endCityName", "endZipCode", 
                           "endCountryCode", "endName", "startDateTime", "passengers"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_transfer",
            "description": "Book an airport transfer service",
            "parameters": {
                "type": "object",
                "properties": {
                    "transfer_id": {
                        "type": "string",
                        "description": "ID of the selected transfer offer"
                    },
                    "start_location": {
                        "type": "string",
                        "description": "Airport IATA code"
                    },
                    "end_location": {
                        "type": "string",
                        "description": "Hotel name and address"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Transfer start time in ISO format"
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Number of passengers"
                    },
                    "price": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "string"},
                            "currency": {"type": "string"}
                        }
                    },
                    "vehicle_type": {
                        "type": "string",
                        "description": "Type of vehicle"
                    },
                    "provider_name": {
                        "type": "string",
                        "description": "Name of the transfer service provider"
                    }
                },
                "required": ["transfer_id", "start_location", "end_location", "start_time", 
                           "passengers", "price", "vehicle_type", "provider_name"]
            }
        }
    }
]


FUNCTION_MAP = {
    "search_flights": search_flight_agent.run,
    "book_flight": book_flight_agent.run,
    "search_hotels": search_hotel_agent.run,
    "book_hotel": book_hotel_agent.run,
    "get_trip_details": trip_details_agent.run,
    "search_transfers": transfer_search_agent.run,
    "book_transfer": book_transfer_agent.run
}

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "Welcome to the BrainBase AirlinesChat API"}


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
                        
            # Convert the received data to our models
            messages = []
            for msg in data_json.get("messages", []):
                # Handle different message structures
                try:
                    # Create a dictionary with only the fields that exist in the message
                    message_data = {"role": msg["role"]}
                    
                    # Add content if it exists
                    if "content" in msg:
                        # Check if content is a nested dictionary with its own content field
                        if isinstance(msg["content"], dict) and "content" in msg["content"]:
                            message_data["content"] = msg["content"]["content"]
                        else:
                            message_data["content"] = msg["content"]
                    else:
                        message_data["content"] = None
                    
                    # Add tool_calls if they exist
                    if "tool_calls" in msg:
                        message_data["tool_calls"] = msg["tool_calls"]
                    
                    # Add tool_call_id if it exists
                    if "tool_call_id" in msg:
                        message_data["tool_call_id"] = msg["tool_call_id"]
                    
                    # Create the ChatMessage with the appropriate fields
                    chat_message = ChatMessage(**message_data)
                    messages.append(chat_message)
                except Exception as e:
                    logger.error(f"Error creating ChatMessage: {str(e)}, message data: {msg}")
                    raise
            
            # Add system prompt if not already present
            if not any(msg.role == "system" for msg in messages):
                messages.insert(0, ChatMessage(role="system", content=SYSTEM_PROMPT))
            
            # Create the chat request with tools
            chat_request = ChatRequest(
                messages=messages,
                model=data_json.get("model", "gpt-4o"),
                temperature=data_json.get("temperature", 0.7),
                tools=AVAILABLE_FUNCTIONS
            )
            
            # Send acknowledgment that message was received
            await websocket.send_json({
                "type": "message_received",
                "message": "Processing your request..."
            })
            
            try:
                # Get response from OpenAI
                response = await generate_chat_response(chat_request)

                # Send the response back to the client
                await websocket.send_json({
                    "type": "chat_response",
                    "role": "assistant",
                    "message": response.choices[0].message.content
                })

                # If there are tool calls, execute them
                if response.choices[0].message.tool_calls:
                    for tool_call in response.choices[0].message.tool_calls:
                        if tool_call.type == "function":
                            function_name = tool_call.function.name
                            function_args = json.loads(tool_call.function.arguments)
                            
                            print(f"\n\n\n\n\nProcessing function call: {function_name}")
                            
                            try:
                                if function_name in FUNCTION_MAP:
                                    if function_name == "search_flights":
                                        params = FlightSearchParams(
                                            origin=function_args["origin"],
                                            destination=function_args["destination"],
                                            departure_date=function_args["departure_date"]
                                        )
                                    elif function_name == "book_flight":
                                        params = BookFlightParams(**function_args)
                                    elif function_name == "search_hotels":
                                        params = SearchHotelParams(**function_args)
                                    elif function_name == "book_hotel":
                                        params = HotelBookingParams(**function_args)
                                    elif function_name == "get_trip_details":
                                        params = GetTripDetailsParams(**function_args)
                                    elif function_name == "search_transfers":
                                        params = TransferSearchParams(**function_args)
                                    elif function_name == "book_transfer":
                                        params = TransferBookingParams(**function_args)
                                
                                # Pass the params object to the run method
                                function_response = await FUNCTION_MAP[function_name](params)
                                
                                # Send an intermediate message to keep the user informed
                                await websocket.send_json({
                                    "type": "chat_response",
                                    "role": "assistant",
                                    "message": f"Browsing for options..."
                                })
                                
                                # Convert Pydantic model to dict for JSON serialization
                                function_response_dict = function_response.model_dump()
                                                                
                                # Check for errors in the function response
                                if hasattr(function_response, 'error') and function_response.error:
                                    await websocket.send_json({
                                        "type": "chat_response",
                                        "role": "assistant",
                                        "message": f"I encountered an error: {function_response.error}. Let me help you try again."
                                    })
                                    continue

                                # Add the function call and result to messages
                                messages.append(ChatMessage(
                                    role="assistant",
                                    content=None,
                                    tool_calls=[{
                                        "id": tool_call.id,
                                        "type": "function",
                                        "function": {
                                            "name": function_name,
                                            "arguments": tool_call.function.arguments
                                        }
                                    }]
                                ))
                                
                                messages.append(ChatMessage(
                                    role="tool",
                                    content=json.dumps(function_response_dict),
                                    tool_call_id=tool_call.id
                                ))

                            except Exception as e:
                                logger.error(f"Error executing function {function_name}: {str(e)}")
                                await websocket.send_json({
                                    "type": "chat_response",
                                    "role": "assistant",
                                    "message": f"I encountered an error while processing your request. Let me help you try again."
                                })
                                continue

                            # Get a new response from OpenAI with the function result
                            chat_request.messages = messages
                            response = await generate_chat_response(chat_request)
                            
                            if response.choices[0].message.content:
                                await websocket.send_json({
                                    "type": "chat_response",
                                    "role": "assistant",
                                    "message": response.choices[0].message.content
                                })

            except Exception as e:
                logger.error(f"Error in WebSocket handler: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 