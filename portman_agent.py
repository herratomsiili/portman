import sqlite3
import requests
import pg8000
from datetime import datetime
import schedule
import time
import os
import argparse
import json
import glob
import natsort
from config import DATABASE_CONFIG

def log(message):
    """Log a message with a timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def job():
    """Function that runs every 5 minutes."""
    log("Fetching new data...")
    main()  # Calls the existing main function

def get_db_connection(dbName):
    """Establish and return a database connection to a specified database."""
    try:
        conn = pg8000.connect(
            database=dbName,
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"]
        )
        return conn
    except Exception as e:
        log(f"Error connecting to database '{dbName}': {e}")
        return None

def get_tracked_vessels():
    """Get IMO numbers to track from environment variables or command-line arguments."""
    parser = argparse.ArgumentParser(description="Portman Tracking Options")
    parser.add_argument("--imo", help="Comma-separated list of IMO numbers to track")
    args = parser.parse_args()

    # Read from command-line argument first
    if args.imo:
        tracked_set = set(map(int, args.imo.split(",")))
        log(f"Tracking vessels from CLI argument: {tracked_set}")
        return tracked_set

    # Fallback to environment variable
    tracked_env = os.getenv("TRACKED_VESSELS")
    if tracked_env:
        tracked_set = set(map(int, tracked_env.split(",")))
        log(f"Tracking vessels from ENV variable: {tracked_set}")
        return tracked_set

    log("No vessel filtering applied. Tracking all vessels.")
    return None  # No filtering if not set


def create_database_and_tables():
    """Create the database and the necessary tables if they don't exist."""
    try:
        log("Checking if database and tables exist...")

        # Connect to PostgreSQL system database to check existence
        conn = get_db_connection("postgres")
        if conn is None:
            return
        conn.autocommit = True
        cursor = conn.cursor()

        # Create database if it doesn't exist
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", ("portman",))
        if not cursor.fetchone():
            log("Database 'portman' does not exist. Creating...")
            cursor.execute("CREATE DATABASE portman;")
        cursor.close()
        conn.close()

        # Connect to the created database
        conn = get_db_connection(DATABASE_CONFIG["dbname"])
        if conn is None:
            return
        cursor = conn.cursor()

        # Create the 'voyages' table
        create_voyages_table = """
        CREATE TABLE IF NOT EXISTS voyages (
            portCallId INTEGER PRIMARY KEY,
            imoLloyds INTEGER,
            vesselTypeCode TEXT,
            vesselName TEXT,
            prevPort TEXT,
            portToVisit TEXT,
            nextPort TEXT,
            agentName TEXT,
            shippingCompany TEXT,
            eta TIMESTAMP NULL,
            ata TIMESTAMP NULL,
            portAreaCode TEXT,
            portAreaName TEXT,
            berthCode TEXT,
            berthName TEXT,
            etd TIMESTAMP NULL,
            atd TIMESTAMP NULL,
            passengersOnArrival INTEGER DEFAULT 0,
            passengersOnDeparture INTEGER DEFAULT 0,
            crewOnArrival INTEGER DEFAULT 0,
            crewOnDeparture INTEGER DEFAULT 0,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_voyages_table)

        # Create the 'arrivals' table
        create_arrivals_table = """
        CREATE TABLE IF NOT EXISTS arrivals (
            id SERIAL PRIMARY KEY,
            portCallId INTEGER,
            eta TIMESTAMP NULL,
            old_ata TIMESTAMP NULL,
            ata TIMESTAMP NOT NULL,
            vesselName TEXT,
            portAreaName TEXT,
            berthName TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_arrivals_table)

        conn.commit()
        cursor.close()
        conn.close()
        log("Database and tables setup complete.")
    except Exception as e:
        log(f"Error setting up database and tables: {e}")

def parse_arguments():
    """Parse command-line arguments and environment variables."""
    parser = argparse.ArgumentParser(description="Portman JSON Input Options")
    parser.add_argument("--input-file", help="Path to a JSON input file")
    parser.add_argument("--input-dir", help="Directory containing JSON files (portnet*.json)")
    parser.add_argument("--imo", help="Comma-separated list of IMO numbers to track")
    args = parser.parse_args()

    return {
        "input_file": args.input_file or os.getenv("INPUT_FILE"),
        "input_dir": args.input_dir or os.getenv("INPUT_DIR"),
        "tracked_vessels": set(map(int, args.imo.split(","))) if args.imo else set(map(int, os.getenv("TRACKED_VESSELS", "").split(","))) if os.getenv("TRACKED_VESSELS") else None
    }

def get_json_source(input_file, input_dir, tracked_vessels):
    """Determine JSON data source: single file or directory of files."""
    if input_file:
        log(f"Reading JSON from file: {input_file}")
        return read_json_from_file(input_file)

    elif input_dir:
        log(f"Reading JSON files from directory: {input_dir}")
        read_json_from_directory(input_dir, tracked_vessels)  # Now processes files one by one
        return None  # Processing is already handled

    log("No input file or directory specified. Fetching from API instead.")
    return None  # Fallback to API fetching

def read_json_from_file(filepath):
    """Read JSON data from a specified file."""
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        log(f"Error reading JSON file {filepath}: {e}")
        return None

def read_json_from_directory(directory, tracked_vessels, conn=None):
    """Read and process each JSON file separately, saving its data to the database."""
    try:
        file_pattern = os.path.join(directory, "portnet*.json")  # Match 'portnet*.json'
        files = glob.glob(file_pattern)
        sorted_files = natsort.natsorted(files)

        log(f"Found {len(sorted_files)} matching JSON files in {directory}: {sorted_files}")

        for filepath in sorted_files:
            try:
                log(f"Processing file: {filepath}")
                with open(filepath, "r", encoding="utf-8") as file:
                    data = json.load(file)

                if "portCalls" in data and isinstance(data["portCalls"], list):
                    results = process_query(data, tracked_vessels)
                    save_results_to_db(results, conn)  # Save after processing each file
                    log(f"Finished processing {filepath}, {len(results)} voyages saved.")
                else:
                    log(f"Skipping file {filepath}: No valid 'portCalls' data found.")

            except Exception as e:
                log(f"Skipping file {filepath} due to error: {e}")

    except Exception as e:
        log(f"Error processing JSON directory {directory}: {e}")


def fetch_data_from_api():
    """Fetch JSON data from the API."""
    url = "https://meri.digitraffic.fi/api/port-call/v1/port-calls"
    log("Fetching data from the API...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        log("Data fetched successfully.")
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"Error fetching data from API: {e}")
        return None

def process_query(data, tracked_vessels):
    """Process the JSON data and prepare results for database insertion."""
    if isinstance(data, dict) and "portCalls" in data:
        data = data["portCalls"]

    if not isinstance(data, list):
        log("Error: Expected a list of port calls in the JSON data.")
        return []

    log(f"Tracking only these vessels: {tracked_vessels}" if tracked_vessels else "Tracking all vessels.")

    results = []
    for entry in data:
        try:
            port_call_id = int(entry.get("portCallId"))  # Ensure it's always an integer
            #imo_number = int(entry.get("imoLloyds"))  # Ensure it's always an integer
        except (TypeError, ValueError):
            #log(f"Skipping entry with invalid portCallId {entry.get('portCallId')} or imoLloyds {entry.get('imoLloyds')}")
            log(f"Skipping entry with invalid portCallId {entry.get('portCallId')}")
            continue  # Skip invalid values

        imo_number = int(entry.get("imoLloyds")) if entry.get("imoLloyds") is not None else None  # Ensure it's always an integer
        #log(f"Checking vessel {imo_number} with portCallId {port_call_id}...")  # Debugging

        # Skip if filtering is enabled and the IMO number is not in the list
        if tracked_vessels and imo_number not in tracked_vessels:
            #log(f"Skipping vessel {imo_number} (not in tracked list).")
            continue

        if tracked_vessels:
            log(f"Processing vessel {imo_number} with portCallId {port_call_id}...")  # Log vessel is being processed

        # Extract agentName & shippingCompany from agentInfo[]
        agent_name = None
        shipping_company = None
        for agent in entry.get("agentInfo", []):
            if agent.get("role") == 1:
                agent_name = agent.get("name")
            elif agent.get("role") == 2:
                shipping_company = agent.get("name")

        # Extract passengers & crew from imoInformation[]
        passengers_on_arrival = 0
        passengers_on_departure = 0
        crew_on_arrival = 0
        crew_on_departure = 0

        for imo in entry.get("imoInformation", []):
            if imo.get("imoGeneralDeclaration") == "Arrival":
                passengers_on_arrival = imo.get("numberOfPassangers", 0) or 0
                crew_on_arrival = imo.get("numberOfCrew", 0) or 0
            elif imo.get("imoGeneralDeclaration") == "Departure":
                passengers_on_departure = imo.get("numberOfPassangers", 0) or 0
                crew_on_departure = imo.get("numberOfCrew", 0) or 0

        # Extract timestamps & berth info from portAreaDetails[0]
        port_area_details = entry.get("portAreaDetails", [{}])
        first_area = port_area_details[0] if port_area_details else {}

        results.append({
            "portCallId": port_call_id,
            "portCallTimestamp": entry.get("portCallTimestamp"),
            "imoLloyds": imo_number if imo_number else 0,
            "vesselTypeCode": entry.get("vesselTypeCode"),
            "vesselName": entry.get("vesselName"),
            "prevPort": entry.get("prevPort"),
            "portToVisit": entry.get("portToVisit"),
            "nextPort": entry.get("nextPort"),
            "agentName": agent_name,
            "shippingCompany": shipping_company,
            "eta": first_area.get("eta"),
            "ata": first_area.get("ata"),
            "portAreaCode": first_area.get("portAreaCode"),
            "portAreaName": first_area.get("portAreaName"),
            "berthCode": first_area.get("berthCode"),
            "berthName": first_area.get("berthName"),
            "etd": first_area.get("etd"),
            "atd": first_area.get("atd"),
            "passengersOnArrival": passengers_on_arrival,
            "passengersOnDeparture": passengers_on_departure,
            "crewOnArrival": crew_on_arrival,
            "crewOnDeparture": crew_on_departure
        })
    log(f"Processed {len(results)} records.")
    return results

def save_results_to_db(results, conn=None):
    """Save processed results into the 'voyages' table and trigger arrivals only when `ata` is updated at the minute level."""
    try:
        log(f"Saving {len(results)} records to the database...")
        connection_managed_elsewhere = conn is not None

        if conn is None:
            conn = get_db_connection(DATABASE_CONFIG["dbname"])

        if conn is None:
            return
        cursor = conn.cursor()

        new_arrival_count = 0  # Track the count of new arrivals

        # Extract unique portCallIds from JSON data
        port_call_ids = list(set(entry["portCallId"] for entry in results))

        # Fetch all old ata values in one query
        old_ata_map = {}
        if port_call_ids:
            # Detect if using SQLite
            is_sqlite = isinstance(conn, sqlite3.Connection)
            placeholder = "?" if is_sqlite else "%s"

            # Fetch old ATA values using proper placeholders
            port_call_ids = list(set(entry["portCallId"] for entry in results))
            query = f"""
                SELECT portCallId, ata FROM voyages WHERE portCallId IN ({','.join([placeholder] * len(port_call_ids))});
            """
            cursor.execute(query, tuple(port_call_ids))

            fetched_data = cursor.fetchall()

            # Debugging: Log fetched data
            log(f"Fetched {len(fetched_data)} existing records from voyages table.")

            # Populate old_ata_map with correctly formatted timestamps (ignore NULL values)
            for row in fetched_data:
                port_call_id, old_ata = row
                if old_ata:  # Only store valid timestamps
                    old_ata_map[int(port_call_id)] = old_ata.strftime("%Y-%m-%dT%H:%M:00.000Z")  # Normalize to minute level

        for entry in results:
            port_call_id = int(entry["portCallId"])  # Ensure it's stored as an integer
            imo_number = int(entry["imoLloyds"])  # Ensure it's stored as an integer
            new_ata = entry["ata"]
            if new_ata:
                new_ata = datetime.strptime(new_ata, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%dT%H:%M:00.000Z")  # Normalize

            # Fetch old ata from the map (default to None)
            old_ata = old_ata_map.get(port_call_id, None)

            # Insert or update voyages
            insert_query = f"""
            INSERT INTO voyages (portCallId, imoLloyds, vesselTypeCode, vesselName, prevPort,
                portToVisit, nextPort, agentName, shippingCompany, eta, ata, portAreaCode,
                portAreaName, berthCode, berthName, etd, atd,
                passengersOnArrival, passengersOnDeparture, crewOnArrival, crewOnDeparture,
                modified
            ) VALUES ({','.join([placeholder] * 21)}, CURRENT_TIMESTAMP)
            ON CONFLICT (portCallId) DO UPDATE SET
                imoLloyds = excluded.imoLloyds,
                vesselTypeCode = excluded.vesselTypeCode,
                vesselName = excluded.vesselName,
                prevPort = excluded.prevPort,
                portToVisit = excluded.portToVisit,
                nextPort = excluded.nextPort,
                agentName = excluded.agentName,
                shippingCompany = excluded.shippingCompany,
                eta = excluded.eta,
                ata = excluded.ata,
                portAreaCode = excluded.portAreaCode,
                portAreaName = excluded.portAreaName,
                berthCode = excluded.berthCode,
                berthName = excluded.berthName,
                etd = excluded.etd,
                atd = excluded.atd,
                passengersOnArrival = excluded.passengersOnArrival,
                passengersOnDeparture = excluded.passengersOnDeparture,
                crewOnArrival = excluded.crewOnArrival,
                crewOnDeparture = excluded.crewOnDeparture,
                modified = CURRENT_TIMESTAMP;
            """

            cursor.execute(insert_query, (
                port_call_id, imo_number, entry["vesselTypeCode"], entry["vesselName"],
                entry["prevPort"], entry["portToVisit"], entry["nextPort"], entry["agentName"],
                entry["shippingCompany"], entry["eta"], new_ata, entry["portAreaCode"], entry["portAreaName"],
                entry["berthCode"], entry["berthName"], entry["etd"], entry["atd"],
                entry["passengersOnArrival"], entry["passengersOnDeparture"], entry["crewOnArrival"],
                entry["crewOnDeparture"]
            ))

            if old_ata != new_ata and new_ata is not None:
                insert_arrival_query = f"""
                INSERT INTO arrivals (portCallId, eta, old_ata, ata, vesselName, portAreaName, berthName, created)
                VALUES ({','.join([placeholder] * 7)}, CURRENT_TIMESTAMP);
                """
                cursor.execute(insert_arrival_query, (
                    port_call_id, entry["eta"], old_ata, new_ata,
                    entry["vesselName"], entry["portAreaName"], entry["berthName"]
                ))
                new_arrival_count += 1
                print(
                    f"-----------------------------\n"
                    f"Port Call ID: {port_call_id}\n"
                    f"Port Call Time Stamp: {entry["portCallTimestamp"]}\n\n"
                    f"Aluksen IMO/nimi: {imo_number}/{entry["vesselName"]}\n\n"
                    f"Satamakoodi: {entry["portToVisit"]}\n"
                    f"Satama: {entry["portAreaName"]}\n"
                    f"Laituri: {entry["berthName"]}\n\n"
                    f"Saapuminen\n"
                    f"Arvioitu saapumisaika (UTC): {datetime.strptime(entry['eta'], '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d %H:%M') if entry.get('eta') else 'N/A'}\n"
                    f"Toteutunut saapumisaika (UTC): {datetime.strptime(new_ata, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d %H:%M") if new_ata else 'N/A'}\n"
                    f"Miehistön lukumäärä: {entry["crewOnArrival"]}\n"
                    f"Matkustajien lukumäärä: {entry["passengersOnArrival"]}\n\n"
                    f"Lähtö\n"
                    f"Arvioitu lähtöaika (UTC): {datetime.strptime(entry['etd'], '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d %H:%M') if entry.get('etd') else 'N/A'}\n"
                    f"Toteutunut lähtöaika (UTC): {datetime.strptime(entry['atd'], '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d %H:%M') if entry.get('atd') else 'N/A'}\n"
                    f"Miehistön lukumäärä: {entry["crewOnDeparture"]}\n"
                    f"Matkustajien lukumäärä: {entry["passengersOnDeparture"]}\n"
                )
                #log(f"Trigger executed: New arrival detected for portCallId {port_call_id} (old_ata: {old_ata}, new_ata: {new_ata})")

        conn.commit()
        cursor.close()
        if not connection_managed_elsewhere:
            conn.close()
        log(f"{len(results)} records saved/updated in the database.")
        log(f"Total new arrivals detected: {new_arrival_count}")

    except Exception as e:
        log(f"Error saving results to the database: {e}")

def main():
    log("Program started.")
    create_database_and_tables()

    # Parse CLI arguments and environment variables
    args = parse_arguments()

    # Process JSON from input file or directory
    data = None
    if args["input_file"] or args["input_dir"]:
        data = get_json_source(args["input_file"], args["input_dir"], args["tracked_vessels"])
    else:
        # If no file/directory is specified, fetch data from API
        log("No input file or directory specified. Fetching from API...")
        data = fetch_data_from_api()

    if data:
        results = process_query(data, args["tracked_vessels"])
        save_results_to_db(results)
    else:
        log("No data available to process.")

    log("Program completed.")

if __name__ == "__main__":
    main()

# Run the job once at startup
#log("Running initial fetch...")
#job()

# Schedule the job every 5 minutes
#schedule.every(5).minutes.do(job)

#log("Scheduler started. Fetching data every 5 minutes...")

# Keep the program running, handle shutdown gracefully
#try:
#    while True:
#        schedule.run_pending()
#        time.sleep(1)  # Prevent CPU overuse
#except KeyboardInterrupt:
#    log("Shutting down scheduler gracefully. Goodbye!")
