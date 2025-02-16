import requests
import json
import time

def fetch_data_from_api():
    """Fetch JSON data from the API."""
    url = "https://meri.digitraffic.fi/api/port-call/v1/port-calls"
    print("Fetching data from the API...")
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
        imo_lloyds = entry.get("imoLloyds", "N/A")
        vessel_name = entry.get("vesselName", "N/A")
        port_to_visit = entry.get("portToVisit", "N/A")

        # Extract portAreaName and berthName from "portAreaDetails"
        port_area_details = entry.get("portAreaDetails", [])
        port_area_name = port_area_details[0].get("portAreaName", "N/A") if port_area_details else "N/A"
        berth_name = port_area_details[0].get("berthName", "N/A") if port_area_details else "N/A"
        eta = port_area_details[0].get("eta", "N/A") if port_area_details else "N/A"
        ata = port_area_details[0].get("ata", "N/A") if port_area_details else "N/A"
        etd = port_area_details[0].get("etd", "N/A") if port_area_details else "N/A"
        atd = port_area_details[0].get("atd", "N/A") if port_area_details else "N/A"

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
            f"Aluksen IMO/nimi: {imo_lloyds}/{vessel_name}\n\n"
            f"Satamakoodi: {port_to_visit}\n"
            f"Satama: {port_area_name}\n"
            f"Laituri: {berth_name}\n\n"
            f"Saapuminen\n"
            f"Arvioitu saapumisaika (UTC): {eta}\n"
            f"Toteutunut saapumisaika (UTC): {ata}\n"
            f"Miehistön lukumäärä: {arrival_crew}\n"
            f"Matkustajien lukumäärä: {arrival_passengers}\n\n"
            f"Lähtö\n"
            f"Arvioitu lähtöaika (UTC): {etd}\n"
            f"Toteutunut lähtöaika (UTC): {atd}\n"
            f"Miehistön lukumäärä: {departure_crew}\n"
            f"Matkustajien lukumäärä: {departure_passengers}\n"
        )

def main():
    print("Polling program started. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                # Fetch data from API
                data = fetch_data_from_api()
                # Format and print the data
                format_port_calls(data)
                print("\nWaiting for 5 minute before fetching data again...\n")
            except requests.RequestException as e:
                print(f"Error fetching data from the API: {e}")
            except Exception as e:
                print(f"An error occurred: {e}")

            # Wait for 5 minute before polling again
            time.sleep(300)
    except KeyboardInterrupt:
        print("\nPolling program stopped by user.")

if __name__ == "__main__":
    main()
