from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import date

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import Usage, UsageLimits


# Chat Models
class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ToolFunction(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class Tool(BaseModel):
    type: str = "function"
    function: ToolFunction

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "gpt-4o"
    temperature: float = 0.7
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None

# Flight Search Models
class FlightSearchParams(BaseModel):
    origin: str = Field(..., description="Origin airport IATA code (e.g., 'LAX')")
    destination: str = Field(..., description="Destination airport IATA code (e.g., 'JFK')")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format")

class FlightSegment(BaseModel):
    carrier: str
    number: str
    departure: Dict[str, str]  # time and airport
    arrival: Dict[str, str]    # time and airport

class FlightInfo(BaseModel):
    segments: List[FlightSegment]  # List of flight segments
    total_duration: str  # Total trip duration
    stops: int  # Number of stops

class FlightPrice(BaseModel):
    amount: str
    currency: str

class Flight(BaseModel):
    price: FlightPrice
    flight: FlightInfo

class FlightSearchResult(BaseModel):
    flights: Optional[List[Flight]] = None
    error: Optional[str] = None

# Search Flight Agent
class SearchFlightAgent(Agent[FlightSearchParams, FlightSearchResult]):
    """Agent that searches for flights using the Amadeus API"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.name = "search_flights"  # Ensure name is set in constructor
        self.description = "Search for available flights between airports using IATA codes"
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    
    async def run(self, params: FlightSearchParams) -> FlightSearchResult:
        from .custom_tools import search_flights
        return await search_flights(
            origin=params.origin,
            destination=params.destination,
            date=params.departure_date
        )

# Traveler Models
class Document(BaseModel):
    documentType: str = "PASSPORT"
    birthPlace: str = "Boston"
    issuanceLocation: str = "Boston"
    issuanceDate: str = "2020-03-12"
    number: str = "00000000"
    expiryDate: str = "2030-04-14"
    issuanceCountry: str = "US"
    validityCountry: str = "US"
    nationality: str = "US"
    holder: str = "true"

class Phone(BaseModel):
    deviceType: str = "MOBILE"
    countryCallingCode: str
    number: str

class Contact(BaseModel):
    emailAddress: str
    phones: List[Phone]

# Payment Models
class CardInfo(BaseModel):
    vendorCode: str = "VI"  # VI for Visa, MC for Mastercard, etc.
    cardNumber: str = "4111111111111111"  # Default test card number
    expiryDate: str = "2025-12"  # YYYY-MM format
    securityCode: str = "123"  # Only used for initial card info
    holderName: str = "John Smith"  # Added from PaymentCardInfo

class PaymentCard(BaseModel):
    paymentCardInfo: CardInfo

class BillingAddress(BaseModel):
    lines: List[str] = ["123 Main St"]
    postalCode: str = "12345"
    cityName: str = "Boston"
    countryCode: str = "US"
    stateCode: Optional[str] = "MA"

class PaymentInfo(BaseModel):
    method: str = "creditCard"
    card: CardInfo = CardInfo()  # Using the consolidated CardInfo model
    billing_address: BillingAddress = BillingAddress()

# Update the Traveler model to include payment information
class Traveler(BaseModel):
    id: str = "1"
    dateOfBirth: str = "2000-01-16"
    name: dict[str, str] = {
        "firstName": "John",
        "lastName": "Smith"
    }
    gender: str = "MALE"
    contact: Contact = Contact(
        emailAddress="john@smith.com",
        phones=[
            Phone(
                deviceType="MOBILE",
                countryCallingCode="1",
                number="4792781794"
            )
        ]
    )
    documents: List[Document] = [
        Document()  # Uses all the defaults defined above
    ]
    payment: PaymentInfo = PaymentInfo()  # Add payment information with defaults

# Book Flight Models
class BookFlightParams(BaseModel):
    flight_id: str  # ID of the selected flight
    origin: str
    destination: str
    departure_date: str
    traveler: Traveler

class FlightDetails(BaseModel):
    segments: List[Dict[str, str]]  # List of segment dictionaries
    total_segments: int
    origin: str
    destination: str
    departure: str
    arrival: str

class BookingResult(BaseModel):
    booking_reference: Optional[str] = None
    status: str
    error: Optional[str] = None
    price: Optional[str] = None
    flight_details: Optional[FlightDetails] = None
    traveler_info: Optional[Traveler] = None

# Add the BookFlightAgent
class BookFlightAgent(Agent[BookFlightParams, BookingResult]):
    """Agent that handles flight booking using the Amadeus API"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.name = "book_flight"
        self.description = "Book a flight for a traveler"
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    
    async def run(self, params: BookFlightParams) -> BookingResult:
        from .custom_tools import book_flight
        return await book_flight(params) 

# Book Hotel Models
class SearchHotelParams(BaseModel):
    cityCode: str
    radius: Optional[int] = None
    chainCodes: Optional[List[str]] = None
    rating: Optional[List[str]] = None

# Hotel Search Models
class RoomDetails(BaseModel):
    type: str
    description: str
    bedType: str
    price: Dict[str, str]
    refundable: bool
    cancellationPolicy: str

class HotelBasicInfo(BaseModel):
    hotelId: str
    name: str
    rating: str
    address: Dict[str, str]
    amenities: Optional[List[str]] = None
    description: Optional[str] = None
    rooms: Optional[List[RoomDetails]] = None
    price: Dict[str, str]

class HotelSearchResult(BaseModel):
    hotels: Optional[List[HotelBasicInfo]] = None
    error: Optional[str] = None


# Update Hotel Booking Models
class GuestReference(BaseModel):
    guestReference: str = "1"

class RoomAssociation(BaseModel):
    guestReferences: List[GuestReference]
    hotelOfferId: str

class PaymentCard(BaseModel):
    paymentCardInfo: CardInfo

class Payment(BaseModel):
    method: str = "CREDIT_CARD"
    paymentCard: PaymentCard = PaymentCard(paymentCardInfo=CardInfo())

class TravelAgent(BaseModel):
    contact: dict = {"email": "bob.smith@email.com"}

class HotelGuest(BaseModel):
    tid: int = 1
    title: str = "MR"
    firstName: str = "John"
    lastName: str = "Smith"
    phone: str = "+33679278416"
    email: str = "bob.smith@email.com"

class HotelBookingParams(BaseModel):
    hotel_name: str
    address: Dict[str, str]
    check_in: str  # YYYY-MM-DD
    check_out: str  # YYYY-MM-DD
    price: Dict[str, str]
    guests: List[HotelGuest] = [
        HotelGuest(
            firstName="John",
            lastName="Smith"
        )
    ]

class HotelBookingResult(BaseModel):
    booking_id: Optional[str] = None
    status: str = "confirmed"
    error: Optional[str] = None
    hotel_name: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    room_type: Optional[str] = None
    price: Optional[Dict[str, str]] = None
    guest_info: Optional[List[HotelGuest]] = None

class BookHotelAgent(Agent[HotelBookingParams, HotelBookingResult]):
    """Agent that handles hotel booking using the Amadeus API"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.name = "book_hotel"
        self.description = "Book a hotel room for travelers"
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    
    async def run(self, params: HotelBookingParams) -> HotelBookingResult:
        from .custom_tools import book_hotel
        return await book_hotel(params)

# Transfer Search Models
class TransportSegment(BaseModel):
    transportationType: str = "FLIGHT"
    transportationNumber: str
    departure: Dict[str, str]  # localDateTime and iataCode
    arrival: Dict[str, str]    # localDateTime and iataCode

class PassengerCharacteristic(BaseModel):
    passengerTypeCode: str = "ADT"
    age: int = 20

class TransferSearchParams(BaseModel):
    startLocationCode: str 
    endAddressLine: str
    endCityName: str
    endZipCode: str
    endCountryCode: str
    endName: str  # Hotel name
    transferType: str = "PRIVATE"
    startDateTime: str  # ISO format
    passengers: int
    endGeoCode: Optional[str] = None  # Format: "latitude,longitude" (e.g., "34.0522,-118.2437")
    startConnectedSegment: Optional[TransportSegment] = None
    passengerCharacteristics: Optional[List[PassengerCharacteristic]] = None

class TransferOption(BaseModel):
    id: str
    duration: str = "1 hour"  # Default duration based on end.dateTime - start.dateTime
    price: Dict[str, str]  # amount and currency from quotation
    vehicle: Dict[str, str]  # code, category, description from vehicle
    provider: Dict[str, str]  # code, name from serviceProvider

class TransferSearchResult(BaseModel):
    transfers: Optional[List[TransferOption]] = None
    error: Optional[str] = None

class TransferSearchAgent(Agent[TransferSearchParams, TransferSearchResult]):
    """Agent that searches for transfers using the Amadeus API"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.name = "search_transfers"
        self.description = "Search for available transfers from airport to hotel"
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    
    async def run(self, params: TransferSearchParams) -> TransferSearchResult:
        from .custom_tools import search_transfers
        return await search_transfers(params)

# Transfer Booking Models
class TransferBookingParams(BaseModel):
    transfer_id: str
    start_location: str  # Airport IATA code
    end_location: str  # Hotel name/address
    start_time: str  # ISO format
    passengers: int
    price: Dict[str, str]  # amount and currency
    vehicle_type: str
    provider_name: str

class TransferBookingResult(BaseModel):
    booking_id: Optional[str] = None
    status: str = "confirmed"
    error: Optional[str] = None
    transfer_details: Optional[Dict[str, Any]] = None
    price: Optional[Dict[str, str]] = None

class BookTransferAgent(Agent[TransferBookingParams, TransferBookingResult]):
    """Agent that handles transfer booking"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.name = "book_transfer"
        self.description = "Book an airport transfer service"
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    
    async def run(self, params: TransferBookingParams) -> TransferBookingResult:
        from .custom_tools import book_transfer
        return await book_transfer(params)

# Trip Details Models
class TripBooking(BaseModel):
    booking_type: str  # "flight", "hotel", or "transfer"
    booking_date: str  # When the booking was made
    # Store the actual booking result
    flight_booking: Optional[BookingResult] = None
    hotel_booking: Optional[HotelBookingResult] = None
    transfer_booking: Optional[TransferBookingResult] = None
    # Common fields
    price: Optional[Dict[str, str]] = None
    guest_info: Optional[List[Dict[str, str]]] = None
    status: str = "confirmed"

class TripDetails(BaseModel):
    trip_id: str
    bookings: List[TripBooking] = []

class TripDetailsResponse(BaseModel):
    trips: List[TripDetails]
    error: Optional[str] = None

class GetTripDetailsParams(BaseModel):
    trip_id: Optional[str] = None  # If None, return all trips

# Add TripDetails Agent
class TripDetailsAgent(Agent[GetTripDetailsParams, TripDetailsResponse]):
    """Agent that retrieves trip details"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.name = "get_trip_details"
        self.description = "Get details of booked flights and hotels"
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    
    async def run(self, params: GetTripDetailsParams) -> TripDetailsResponse:
        from .custom_tools import get_trip_details
        return await get_trip_details(params)

# Add back the SearchHotelAgent class
class SearchHotelAgent(Agent[SearchHotelParams, HotelSearchResult]):
    """Agent that searches for hotels using the Amadeus API"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.name = "search_hotels"
        self.description = "Search for available hotels in a city"
    
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    
    async def run(self, params: SearchHotelParams) -> HotelSearchResult:
        from .custom_tools import search_hotels
        return await search_hotels(params)