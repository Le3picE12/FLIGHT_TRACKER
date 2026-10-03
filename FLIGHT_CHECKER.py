import requests
import json
import os

# -----------------------------
# Keys
# -----------------------------

SERPAPI_KEY = os.getenv("SERAPI_KEY")
DISCORDWEBHOOK_URL = os.getenv("DISCORDWEBHOOK_URL")

PRICE_FILE = "last_price.json"

# -----------------------------
# Flights (General)
# -----------------------------

OUTBOUND = {
    "name": "Outbound",
    "from": "LAS",
    "to": "KIX",
    "date": "2027-02-07",
    "airline": "KE"
}

RETURN = {
    "name": "Return",
    "from": "HND",
    "to": "LAS",
    "date": "2027-02-22",
    "airline": "AA"
}

# -----------------------------
# Flights (Exact Legs)
# -----------------------------

OUTBOUND_EXPECTED_LEGS = [
    [
        {"from": "LAS", "to": "ICN", "flight_number": "KE6"},
        {"from": "ICN", "to": "KIX", "flight_number": "KE723"}
    ],

    # SFO 

    [
        {"from": "LAS", "to": "SFO"},
        {"from": "SFO", "to": "ICN"},
        {"from": "ICN", "to": "KIX"}
    ]
]

RETURN_EXPECTED_LEGS = [
    [
        {"from": "HND", "to": "LAX", "flight_number": "AA26"},
        {"from": "LAX", "to": "LAS", "flight_number": "AA2424"}
    ],

    # SFO

    [
        {"from": "HND", "to": "SFO"},
        {"from": "SFO", "to": "LAS"}
    ]
]

# -----------------------------
# Google Flights Search and Processing
# -----------------------------

def search_google_flights(trip):
    url = "https://serpapi.com/search"

    params = {
        "engine": "google_flights",
        "api_key": SERPAPI_KEY,
        "departure_id": trip["from"],
        "arrival_id": trip["to"],
        "outbound_date": trip["date"],
        "type": "2",
        "currency": "USD",
        "hl": "en",
        "gl": "us",
        "deep_search": "true",
        "show_hidden": "true"
    }

    if trip.get("airline"):
        params["include_airlines"] = trip["airline"]

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        print("SerpApi error:", data["error"])

    return data

#------------------------------
# Normaize Flight Number removes spaces and converts to uppercase for consistent comparison.
#------------------------------

def normalize_flight_number(flight_number):
    if flight_number is None:
        return ""

    return str(flight_number).replace(" ", "").upper()


# ------------------------------
# Flight Matching and Discord Alerting
# ------------------------------

def get_all_flights(data):
    all_flights = []
    all_flights.extend(data.get("best_flights", []))
    all_flights.extend(data.get("other_flights", []))
    return all_flights

# ------------------------------
# itinerary_matches checks if the actual flight legs match the expected legs for a given option.
# It compares the departure and arrival airports as well as the flight numbers for each leg.
# If all legs match, it returns True. Otherwise, it returns False.
# ------------------------------
def itinerary_matches(actual_legs, expected_legs):

    if len(actual_legs) != len(expected_legs):
        return False

    for i in range(len(expected_legs)):

        expected = expected_legs[i]
        actual = actual_legs[i]

        actual_from = actual.get("departure_airport", {}).get("id")
        actual_to = actual.get("arrival_airport", {}).get("id")

        if actual_from != expected["from"]:
            return False

        if actual_to != expected["to"]:
            return False

        if "flight_number" in expected:

            expected_num = normalize_flight_number(
                expected["flight_number"]
            )

            actual_num = normalize_flight_number(
                actual.get("flight_number")
            )

            if expected_num != actual_num:
                return False

    return True

# ------------------------------
# This function checks if any flight in the data matches the expected legs exactly.
# It compares the departure and arrival airports as well as the flight numbers for each leg.
# If a match is found, it returns the price and flight details. Otherwise, it returns None.
# ------------------------------

def extract_matching_flight(data, itinerary_options):

    all_flights = get_all_flights(data)

    for flight in all_flights:

        actual_legs = flight.get("flights", [])

        for option in itinerary_options:

            if itinerary_matches(actual_legs, option):
                return flight.get("price"), flight

    return None

# ------------------------------
# This function checks if any leg of the flight has a layover at SFO by examining
# the departure and arrival airports of each leg. If it finds a leg that departs from or arrives at SFO, it returns True. If no legs involve SFO, it returns False.
# ------------------------------

def has_sfo_layover(flight):
    for leg in flight.get("flights", []):
        dep = leg.get("departure_airport", {}).get("id")
        arr = leg.get("arrival_airport", {}).get("id")

        if dep == "SFO" or arr == "SFO":
            return True

    return False

# ------------------------------
# This function retrieves all flights from the SerpApi response, filters them to include only those
# that have a layover at SFO, and then sorts the resulting list of flights by price in ascending order.
# It returns the sorted list of flights with SFO layovers.
# ------------------------------

def get_sfo_flights_sorted(data):
    flights = get_all_flights(data)

    sfo_flights = []

    for flight in flights:
        price = flight.get("price")

        if price is None:
            continue

        if has_sfo_layover(flight):
            sfo_flights.append(flight)

    sfo_flights.sort(key=lambda flight: flight.get("price", float("inf")))

    return sfo_flights

# ------------------------------
# This function generates a human-readable description of the flight details, including the airline, flight number,
# departure and arrival airports, and times for each leg of the flight. If no flight details are found, it returns a message indicating that.
# ------------------------------

def describe_flight(flight):
    if flight is None:
        return "No flight details found."

    lines = []

    for leg in flight.get("flights", []):
        airline = leg.get("airline", "Unknown airline")
        flight_number = leg.get("flight_number", "")
        dep = leg.get("departure_airport", {}).get("id", "?")
        arr = leg.get("arrival_airport", {}).get("id", "?")
        dep_time = leg.get("departure_airport", {}).get("time", "?")
        arr_time = leg.get("arrival_airport", {}).get("time", "?")

        lines.append(
            f"{airline} {flight_number}: {dep} → {arr}\n"
            f"{dep_time} → {arr_time}"
        )

    return "\n\n".join(lines)

def search_google_flights_all_airlines(trip):
    url = "https://serpapi.com/search"

    params = {
        "engine": "google_flights",
        "api_key": SERPAPI_KEY,
        "departure_id": trip["from"],
        "arrival_id": trip["to"],
        "outbound_date": trip["date"],
        "type": "2",
        "currency": "USD",
        "hl": "en",
        "gl": "us",
        "deep_search": "true",
        "show_hidden": "true"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    return response.json()


def load_last_price():
    if not os.path.exists(PRICE_FILE):
        return None

    with open(PRICE_FILE, "r") as file:
        return json.load(file)["total_price"]


def save_price(total_price):
    with open(PRICE_FILE, "w") as file:
        json.dump({"total_price": total_price}, file)


def send_discord_alert(old_price, new_price, outbound_price, return_price, outbound_flight, return_flight):
    difference = new_price - old_price

    if difference < 0:
        change_text = f"Price dropped by ${abs(difference):.2f}"
        color = 3066993
    else:
        change_text = f"Price increased by ${difference:.2f}"
        color = 15158332

    data = {
        "embeds": [
            {
                "title": "Original Flight We're Thinking of, Price Changed!",
                "fields": [
                    {
                        "name": "Outbound",
                        "value": f"{OUTBOUND['from']} → ICN → {OUTBOUND['to']}\n${outbound_price}",
                        "inline": False
                    },
                    {
                        "name": "Outbound Details",
                        "value": describe_flight(outbound_flight),
                        "inline": False
                    },
                    {
                        "name": "Return",
                        "value": f"{RETURN['from']} → LAX → {RETURN['to']}\n${return_price}",
                        "inline": False
                    },
                    {
                        "name": "Return Details",
                        "value": describe_flight(return_flight),
                        "inline": False
                    },
                    {
                        "name": "Old Total",
                        "value": f"${old_price:.2f}",
                        "inline": True
                    },
                    {
                        "name": "New Total",
                        "value": f"${new_price:.2f}",
                        "inline": True
                    },
                    {
                        "name": "Change",
                        "value": change_text,
                        "inline": False
                    },
                    {
                        "name": "Google Flights Link",
                        "value": f"Onboard: https://www.google.com/travel/flights/s/k2D3TeHvgYF9n55x5" + "\n" + f"Return: https://www.google.com/travel/flights/s/th2y99PPhpvffTQQ8",
                        "inline": False
                    }
                ],
                "color": color
            }
        ]
    }

    response = requests.post(DISCORDWEBHOOK_URL, json=data)
    response.raise_for_status()



def send_discord_no_change(current_price, outbound_price, return_price, outbound_flight, return_flight):
    data = {
        "embeds": [
            {
                "title": "Original Flight We're Thinking of, Price Remains The Same!",
                "description": "No price change detected.",
                "fields": [
                    {
                        "name": "Outbound",
                        "value": f"${outbound_price}\n{describe_flight(outbound_flight)}",
                        "inline": False
                    },
                    {
                        "name": "Return",
                        "value": f"${return_price}\n{describe_flight(return_flight)}",
                        "inline": False
                    },
                    {
                        "name": "Current Total",
                        "value": f"${current_price:.2f}",
                        "inline": True
                    },
                    {
                        "name": "Google Flights Link",
                        "value": f"Onboard: https://www.google.com/travel/flights/s/k2D3TeHvgYF9n55x5" + "\n" + f"Return: https://www.google.com/travel/flights/s/th2y99PPhpvffTQQ8",
                        "inline": False
                    }
                ],
                "color": 3447003
            }
        ]
    }

    response = requests.post(DISCORDWEBHOOK_URL, json=data)
    response.raise_for_status()

def send_discord_SFO_flights(outbound_sfo_flights, return_sfo_flights):
    fields = []

    top_outbound = outbound_sfo_flights[:5]
    top_return = return_sfo_flights[:5]

    if top_outbound:
        for i, flight in enumerate(top_outbound, start=1):
            fields.append({
                "name": f"Outbound SFO Option #{i} - ${flight.get('price')}",
                "value": describe_flight(flight),
                "inline": False
            })
    else:
        fields.append({
            "name": "Outbound SFO Options",
            "value": "No outbound SFO layover flights found.",
            "inline": False
        })

    if top_return:
        for i, flight in enumerate(top_return, start=1):
            fields.append({
                "name": f"Return SFO Option #{i} - ${flight.get('price')}",
                "value": describe_flight(flight),
                "inline": False
            })
    else:
        fields.append({
            "name": "Return SFO Options",
            "value": "No return SFO layover flights found.",
            "inline": False
        })

    data = {
        "embeds": [
            {
                "title": "Top 5 Flights With SFO Layover",
                "description": "Sorted from cheapest to most expensive.",
                "fields": fields,
                "color": 16776960
            }
        ]
    }

    response = requests.post(DISCORDWEBHOOK_URL, json=data)
    response.raise_for_status()


def main():
    print("Checking specific Google Flights through SerpApi...")

    # Search for both outbound and return flights using SerpApi and store the JSON responses.

    outbound_json = search_google_flights(OUTBOUND)
    return_json = search_google_flights(RETURN)

    # Get and sort flights with SFO layovers, then send them to Discord before checking for exact matches.

    outbound_all_json = search_google_flights_all_airlines(OUTBOUND)
    return_all_json = search_google_flights_all_airlines(RETURN)

    outbound_sfo_flights = get_sfo_flights_sorted(outbound_all_json)
    return_sfo_flights = get_sfo_flights_sorted(return_all_json)

    # Sends discord message with top 5 SFO layover options for both outbound and return flights before checking for exact matches. 
    # This way we can see if there are any good SFO options even if the exact match isn't found or if the price changes.



    # send_discord_SFO_flights(outbound_sfo_flights, return_sfo_flights) 



    # Print SFO layover flights to console for debugging purposes. This will show the top 5 SFO layover options for both outbound and return flights, sorted by price. This can help us understand what SFO options are being returned by SerpApi and if there are any good deals with SFO layovers.
    print("\nOutbound flights with SFO layovers (sorted by price):")
    for flight in outbound_sfo_flights[:5]:
        print(f"Price: ${flight.get('price')}")
        print(describe_flight(flight))
        print("-" * 40)
    print("\nReturn flights with SFO layovers (sorted by price):")
    for flight in return_sfo_flights[:5]:
        print(f"Price: ${flight.get('price')}")
        print(describe_flight(flight))
        print("-" * 40)

    # Check for exact matches to the expected legs for both outbound and return flights. 
    # If an exact match is found, extract the price and flight details. 
    # If not, print all flights returned by SerpApi for that leg to help with debugging and understanding what options are being returned.

    outbound_result = extract_matching_flight(outbound_json, OUTBOUND_EXPECTED_LEGS)
    return_result = extract_matching_flight(return_json, RETURN_EXPECTED_LEGS)

    # If no exact match is found for either leg, print all the flights returned by SerpApi 
    # for that leg to help with debugging and understanding what options are being returned.

    if outbound_result is None:
        print("\nCould not find exact outbound flight.")
        return

    # If no exact match is found for the return leg, print all the flights 
    # returned by SerpApi for the return leg to help with debugging and understanding what options are being returned.

    if return_result is None:
        print("\nCould not find exact return flight.")
        return

    outbound_price, outbound_flight = outbound_result
    return_price, return_flight = return_result

    total_price = outbound_price + return_price

    print("\nExact outbound found:")
    print(f"Price: ${outbound_price}")
    print(describe_flight(outbound_flight))

    print("\nExact return found:")
    print(f"Price: ${return_price}")
    print(describe_flight(return_flight))

    print(f"\nTotal price: ${total_price}")

    last_price = load_last_price()

    if last_price is None:
        print("No previous price saved. Saving current price.")
        save_price(total_price)
        return

    if total_price != last_price:
        print("Price changed. Sending Discord alert...")
        send_discord_alert(
            last_price,
            total_price,
            outbound_price,
            return_price,
            outbound_flight,
            return_flight
        )
    else:
        print("Price has not changed. Sending Discord status message...")
        send_discord_no_change(
            total_price,
            outbound_price,
            return_price,
            outbound_flight,
            return_flight
        )

    save_price(total_price)

main()