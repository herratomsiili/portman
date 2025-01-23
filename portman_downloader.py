import argparse
import requests
import json

def fetch_data_from_api():
    """Fetch JSON data from the API."""
    url = "https://meri.digitraffic.fi/api/port-call/v1/port-calls"
    print("Downloading data from the API...")
    response = requests.get(url)
    response.raise_for_status()  # Raise an error if the request fails
    return response.json()

def format_port_calls(data):
    """Format and display port call data."""
    # Ensure data is a list
    if isinstance(data, dict):  # If the root is a dictionary, try extracting an array
        if "portCalls" in data:
            data = data["portCalls"]
        else:
            print("Error: JSON data does not contain an array or 'portCalls' key.")
            return
    
    if not isinstance(data, list):  # Still not a list, abort
        print("Error: JSON data should be an array.")
        return
    
    for entry in data:
        # Extract required fields
        port_call_id = entry.get("portCallId", "N/A")
        port_call_timestamp = entry.get("portCallTimestamp", "N/A")
        vessel_name = entry.get("vesselName", "N/A")
        port_to_visit = entry.get("portToVisit", "N/A")
        
        # Extract portAreaName and berthName from "portAreaDetails"
        port_area_details = entry.get("portAreaDetails", [])
        if port_area_details:
            port_area_name = port_area_details[0].get("portAreaName", "N/A")
            berth_name = port_area_details[0].get("berthName", "N/A")
        else:
            port_area_name = "N/A"
            berth_name = "N/A"
        
        # Extract Arrival and Departure data from "imoInformation" array
        imo_info = entry.get("imoInformation", [])
        arrival_info = next((info for info in imo_info if info.get("imoGeneralDeclaration") == "Arrival"), {})
        departure_info = next((info for info in imo_info if info.get("imoGeneralDeclaration") == "Departure"), {})
        
        arrival_crew = arrival_info.get("numberOfCrew", "N/A")
        arrival_passengers = arrival_info.get("numberOfPassangers", "N/A")
        departure_crew = departure_info.get("numberOfCrew", "N/A")
        departure_passengers = departure_info.get("numberOfPassangers", "N/A")
        
        # Format the output
        print(
            f"-----------------------------\n"
            f"Port Call ID: {port_call_id}\n"
            f"Port Call Time Stamp: {port_call_timestamp}\n\n"
            f"Aluksen nimi: {vessel_name}\n\n"
            f"Satamakoodi: {port_to_visit}\n"
            f"Satama: {port_area_name}\n"
            f"Laituri: {berth_name}\n\n"
            f"Arrival\n"
            f"Miehistön lukumäärä: {arrival_crew}\n"
            f"Matkustajien lukumäärä: {arrival_passengers}\n\n"
            f"Departure\n"
            f"Miehistön lukumäärä: {departure_crew}\n"
            f"Matkustajien lukumäärä: {departure_passengers}\n"
        )

def main():
    parser = argparse.ArgumentParser(description="Format port call data from a JSON file or API.")
    parser.add_argument("--input-file", help="Path to the JSON file to analyze. If not provided, data will be fetched from the API.")
    args = parser.parse_args()
    
    try:
        if args.input_file:
            print(f"Reading data from file: {args.input_file}")
            with open(args.input_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
        else:
            data = fetch_data_from_api()
        
        format_port_calls(data)
    
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found.")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format.")
    except requests.RequestException as e:
        print(f"Error fetching data from the API: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
