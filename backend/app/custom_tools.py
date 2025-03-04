"""
Implement the Amadeus API integration here by creating custom tools. 
"""
import json
import requests
import aiohttp
import asyncio
import os
from .models import (
    FlightSearchResult,
    Flight,
    FlightPrice,
    FlightInfo,
    BookFlightParams,
    BookingResult,
    HotelBasicInfo,
    HotelSearchResult,
    SearchHotelParams,
    HotelBookingParams,
    HotelBookingResult,
    TripBooking,
    TripDetails,
    GetTripDetailsParams,
    TripDetailsResponse,
    TransferSearchParams,
    TransferSearchResult,
    TransferOption,
    TransferBookingParams,
    TransferBookingResult,
    FlightSegment,
    RoomDetails
)
from datetime import datetime
from typing import Dict, List, Union, Optional
import logfire
from dotenv import dotenv_values
from pathlib import Path

# Get the path to the .env file (one directory up from current file)
env_path = Path(__file__).parent.parent / '.env'
# Load config
config = dotenv_values(env_path)

# Configure Logfire
logfire.configure(token=config['LOGFIRE_TOKEN'])

# Move hardcoded values to constants at the top
AMADEUS_TEST_BASE_URL = "https://test.api.amadeus.com"
MAX_HOTELS_TO_FETCH = 5
DEFAULT_HOTEL_RADIUS_KM = 10
DEFAULT_CURRENCY = "USD"

# Search and Book Flight
async def search_flights(origin: str, destination: str, date: str) -> FlightSearchResult:
    """Search for flights using Amadeus API."""
    logfire.info("searching_flights",
        origin=origin,
        destination=destination,
        date=date
    )
    access_token = config['AMADEUS_ACCESS_TOKEN']
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://test.api.amadeus.com/v2/shopping/flight-offers',
                headers={'Authorization': f'Bearer {access_token}'},
                params={
                    'originLocationCode': origin,
                    'destinationLocationCode': destination,
                    'departureDate': date,
                    'adults': 1,
                    'currencyCode': 'USD',
                    'max': 6
                }
            ) as response:
                response_data = await response.json()
                
                # Handle API errors
                if 'errors' in response_data:
                    error_detail = response_data['errors'][0].get('detail', '')
                    error_code = response_data['errors'][0].get('code', '')
                    
                    # Create user-friendly error messages
                    if isinstance(error_code, str):
                        if 'INVALID_PARAMETER' in error_code:
                            if 'originLocationCode' in error_detail:
                                return FlightSearchResult(error=f"Invalid origin airport code: {origin}. Please provide a valid IATA airport code.")
                            elif 'destinationLocationCode' in error_detail:
                                return FlightSearchResult(error=f"Invalid destination airport code: {destination}. Please provide a valid IATA airport code.")
                            elif 'departureDate' in error_detail:
                                return FlightSearchResult(error=f"Invalid date format: {date}. Please provide the date in YYYY-MM-DD format.")
                        elif 'NO_FLIGHT_FOUND' in error_code:
                            return FlightSearchResult(error=f"No flights found from {origin} to {destination} on {date}. Try different dates or airports.")
                    
                    # Handle past date error
                    if "date/time is in the past" in error_detail.lower():
                        return FlightSearchResult(error="Please provide a date in the format: YYYY-MM-DD, and I will try the search again.")
                    
                    # Generic error fallback
                    return FlightSearchResult(error=error_detail or "Failed to search for flights. Please try again.")

                # Process successful response...
                flights = []
                try:
                    for offer in response_data['data'][:5]:
                        # Process all segments in the itinerary
                        segments = []
                        for segment in offer["itineraries"][0]["segments"]:
                            segments.append(FlightSegment(
                                carrier=segment["carrierCode"],
                                number=segment["number"],
                                departure={
                                    "time": segment["departure"]["at"],
                                    "airport": segment["departure"]["iataCode"]
                                },
                                arrival={
                                    "time": segment["arrival"]["at"],
                                    "airport": segment["arrival"]["iataCode"]
                                }
                            ))
                        
                        # Calculate total duration and stops
                        total_duration = offer["itineraries"][0].get("duration", "")
                        stops = len(segments) - 1
                        
                        flight = Flight(
                            price=FlightPrice(
                                amount=offer["price"]["total"],
                                currency=offer["price"]["currency"]
                            ),
                            flight=FlightInfo(
                                segments=segments,
                                total_duration=total_duration,
                                stops=stops
                            )
                        )
                        flights.append(flight)
                    
                    logfire.info("flights_found",
                        flight_count=len(flights),
                        origin=origin,
                        destination=destination
                    )
                    return FlightSearchResult(flights=flights)
                except (KeyError, IndexError) as e:
                    logfire.error(f"Error parsing response: {str(e)}")
                    return FlightSearchResult(error="Unable to process flight search results. Please try again.")
            
    except Exception as e:
        logfire.error("flight_search_error",
            error=str(e),
            origin=origin,
            destination=destination
        )
        raise

async def book_flight(params: BookFlightParams) -> BookingResult:
    """Store the flight booking."""
    try:
        flight_details = {
            "flight_number": params.flight_id,
            "origin": params.origin,
            "destination": params.destination,
            "departure_date": params.departure_date
        }

        result = BookingResult(
            booking_reference=f"FL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            status="confirmed",
            traveler_info=params.traveler
        )

        if result.status == "confirmed":
            store_booking("flight", result)
            
        return result

    except Exception as e:
        logfire.error(f"Error booking flight: {str(e)}")
        return BookingResult(
            status="error",
            error="Failed to book flight"
        )

# Search for Hotel
async def search_hotels(params: SearchHotelParams) -> HotelSearchResult:
    """Search for hotels using Amadeus API."""
    access_token = config['AMADEUS_ACCESS_TOKEN']
    try:
        async with aiohttp.ClientSession() as session:
            # Search for hotels
            search_params = {
                'cityCode': params.cityCode,
                'radius': params.radius or 5,
                'radiusUnit': 'KM',
                'hotelSource': 'ALL'
            }
            
            if params.chainCodes:
                search_params['chainCodes'] = ','.join(params.chainCodes)
            if params.rating:
                search_params['ratings'] = ','.join(params.rating)

            search_response = await session.get(
                'https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city',
                headers={'Authorization': f'Bearer {access_token}'},
                params=search_params
            )
            hotels_data = await search_response.json()
            
            if 'errors' in hotels_data:
                return HotelSearchResult(
                    error=hotels_data['errors'][0].get('detail', 'Hotel search failed')
                )

            # Get hotel IDs from search results (limit to 5)
            hotel_ids = [hotel.get('hotelId') for hotel in hotels_data.get('data', [])[:5]]
            
            if not hotel_ids:
                return HotelSearchResult(
                    error="No hotels found in the specified location"
                )

            # Get offers for all hotels at once
            offers_response = await session.get(
                'https://test.api.amadeus.com/v3/shopping/hotel-offers',
                headers={'Authorization': f'Bearer {access_token}'},
                params={
                    'hotelIds': ','.join(hotel_ids),
                    'adults': 1,
                    'roomQuantity': 1,
                    'currency': 'USD'
                }
            )
            offers_data = await offers_response.json()

            # Process hotels with their offers
            hotels = []
            if 'data' in offers_data:
                for hotel_offer in offers_data['data']:
                    hotel_data = hotel_offer['hotel']
                    
                    # Process all room offers
                    rooms = []
                    cheapest_price = float('inf')
                    cheapest_currency = 'USD'
                    
                    for offer in hotel_offer.get('offers', []):
                        room = RoomDetails(
                            type=offer.get('room', {}).get('typeEstimated', {}).get('category', 'Standard Room'),
                            description=offer.get('room', {}).get('description', {}).get('text', ''),
                            bedType=offer.get('room', {}).get('typeEstimated', {}).get('bedType', 'Unknown'),
                            price={
                                'amount': offer.get('price', {}).get('total', 'N/A'),
                                'currency': offer.get('price', {}).get('currency', 'USD')
                            },
                            refundable=offer.get('policies', {}).get('refundable', {}).get('cancellationRefund', '') != 'NON_REFUNDABLE',
                            cancellationPolicy=offer.get('policies', {}).get('cancellations', [{}])[0].get('description', {}).get('text', 'Contact hotel for policy')
                        )
                        rooms.append(room)
                        
                        # Track cheapest price
                        try:
                            price = float(offer.get('price', {}).get('total', 'inf'))
                            if price < cheapest_price:
                                cheapest_price = price
                                cheapest_currency = offer.get('price', {}).get('currency', 'USD')
                        except (ValueError, TypeError):
                            continue
                    
                    hotels.append(HotelBasicInfo(
                        hotelId=hotel_data['hotelId'],
                        name=hotel_data.get('name', 'Unknown Hotel'),
                        rating=hotel_data.get('rating', 'N/A'),
                        description=hotel_data.get('description', {}).get('text', 'No description available'),
                        amenities=hotel_data.get('amenities', []),
                        address={
                            'cityName': hotel_data.get('address', {}).get('cityName', ''),
                            'countryCode': hotel_data.get('address', {}).get('countryCode', ''),
                            'stateCode': hotel_data.get('address', {}).get('stateCode', ''),
                            'postalCode': hotel_data.get('address', {}).get('postalCode', ''),
                            'address': hotel_data.get('address', {}).get('lines', [''])[0]
                        },
                        rooms=rooms,  # Add all room details
                        price={
                            'amount': str(cheapest_price) if cheapest_price != float('inf') else 'N/A',
                            'currency': cheapest_currency
                        }
                    ))

            logfire.info(f"Found {len(hotels)} hotels in {params.cityCode}")
            return HotelSearchResult(hotels=hotels)

    except Exception as e:
        logfire.error(f"Error searching hotels: {str(e)}")
        return HotelSearchResult(error="I encountered an issue while trying to search for hotels. This could be due to temporary availability issues. Please try searching for hotels again, and I'll help you complete the booking. Also could be the access token issue, try refreshing it. Sorry for the inconvenience!"
)

async def book_hotel(params: HotelBookingParams) -> HotelBookingResult:
    """Book a hotel and return booking details."""
    try:
        result = HotelBookingResult(
            hotel_name=params.hotel_name,
            address=params.address,
            check_in=params.check_in,
            check_out=params.check_out,
            price=params.price,
            status="confirmed"
        )

        if result.status == "confirmed":
            store_booking("hotel", result)
        return result
    except Exception as e:
        logfire.error(f"Error booking hotel: {str(e)}")
        return HotelBookingResult(
            status="error",
            error="Failed to book hotel",
            hotel_name="",
            address={},
            check_in="",
            check_out="",
            price={}
        )

# Search for Transfers
async def search_transfers(params: TransferSearchParams) -> TransferSearchResult:
    """Search for transfers using Amadeus API."""
    access_token = config['AMADEUS_ACCESS_TOKEN']
    try:
        url = "https://test.api.amadeus.com/v1/shopping/transfer-offers"

        payload = json.dumps({
            "startLocationCode": params.startLocationCode,
            "endAddressLine": params.endAddressLine,
            "endCityName": params.endCityName,
            "endZipCode": params.endZipCode,
            "endCountryCode": params.endCountryCode,
            "endName": params.endName,
            "startDateTime": params.startDateTime,
            "passengers": params.passengers
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        response_data = response.json()  # Convert response to JSON

        if 'errors' in response_data:
            error_detail = response_data['errors'][0].get('detail', '')
            if 'NEED GEOCODES' in error_detail:
                return TransferSearchResult(
                    error="GEOCODES_REQUIRED"
                )
            return TransferSearchResult(
                error=error_detail or 'Transfer search failed'
            )

        transfers = []
        for offer in response_data.get('data', []):
            # Calculate duration from start and end times
            start_time = datetime.fromisoformat(offer['start']['dateTime'].replace('Z', ''))
            end_time = datetime.fromisoformat(offer['end']['dateTime'].replace('Z', ''))
            duration = str(end_time - start_time)

            transfers.append(TransferOption(
                id=offer['id'],
                duration=duration,
                price={
                    'amount': offer['quotation']['monetaryAmount'],
                    'currency': offer['quotation']['currencyCode']
                },
                vehicle={
                    'type': offer['vehicle']['code'],
                    'description': offer['vehicle']['description']
                },
                provider={
                    'name': offer['serviceProvider']['name'],
                    'code': offer['serviceProvider']['code']
                }
            ))

        return TransferSearchResult(transfers=transfers)

    except Exception as e:
        logfire.error(f"Error searching transfers: {str(e)}")
        return TransferSearchResult(error="I encountered an issue while trying to search for transfers. This could be due to temporary availability issues. Please try searching for transfers again, and I'll help you complete the booking. Also could be the access token issue, try refreshing it. Sorry for the inconvenience!"
)

async def book_transfer(params: TransferBookingParams) -> TransferBookingResult:
    """Book a transfer and store it in trip storage."""
    try:
        # Create booking details
        booking_details = {
            'transfer_id': params.transfer_id,
            'start_location': params.start_location,
            'end_location': params.end_location,
            'start_time': params.start_time,
            'vehicle_type': params.vehicle_type,
            'provider': params.provider_name
        }

        result = TransferBookingResult(
            booking_id=f"TR-{datetime.now().strftime('%Y%m%d%H%M%S')}",  # Generate a simple booking ID
            status="confirmed",
            transfer_details=booking_details,
            price=params.price
        )

        # Store the booking
        if result.status == "confirmed":
            store_booking("transfer", result)
        
        return result

    except Exception as e:
        logfire.error(f"Error booking transfer: {str(e)}")
        return TransferBookingResult(
            status="error",
            error="An unexpected error occurred while booking the transfer"
        )


# In-memory storage for trip details (replace with database in production)
trip_storage: Dict[str, TripDetails] = {}

def store_booking(booking_type: str, booking_data: Union[BookingResult, HotelBookingResult, TransferBookingResult]) -> None:
    """Store a new booking in the trip storage"""
    from datetime import datetime
    
    # Create a new trip booking
    trip_booking = TripBooking(
        booking_type=booking_type,
        booking_date=datetime.now().strftime("%Y-%m-%d")
    )
    
    # Store the entire booking result
    if booking_type == "flight":
        trip_booking.flight_booking = booking_data
    elif booking_type == "hotel":
        trip_booking.hotel_booking = booking_data
    elif booking_type == "transfer":
        trip_booking.transfer_booking = booking_data
    
    # Create or update trip
    trip_id = f"TRIP_{datetime.now().strftime('%Y%m%d')}"
    if trip_id not in trip_storage:
        trip_storage[trip_id] = TripDetails(trip_id=trip_id)
    trip_storage[trip_id].bookings.append(trip_booking)

async def get_trip_details(params: GetTripDetailsParams) -> TripDetailsResponse:
    """Retrieve trip details"""
    try:
        if params.trip_id:
            if params.trip_id in trip_storage:
                return TripDetailsResponse(trips=[trip_storage[params.trip_id]])
            return TripDetailsResponse(trips=[], error=f"Trip {params.trip_id} not found")
        return TripDetailsResponse(trips=list(trip_storage.values()))
    except Exception as e:
        logfire.error(f"Error getting trip details: {str(e)}")
        return TripDetailsResponse(trips=[], error="Failed to retrieve trip details")
