import requests
import pg8000
from datetime import datetime
import schedule
import time

# Default database connection parameters
DB_USER = "postgres"
DB_PASSWORD = "password"
DB_HOST = "127.0.0.1"
DB_PORT = 5432

def log(message):
    """Log a message with a timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def job():
    """Function that runs every 5 minutes."""
    log("Fetching new data...")
    main()  # Calls the existing main function

def get_db_connection(database):
    """Establish and return a database connection to a specified database."""
    try:
        conn = pg8000.connect(
            user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT, database=database
        )
        return conn
    except Exception as e:
        log(f"Error connecting to database '{database}': {e}")
        return None

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
        conn = get_db_connection("portman")
        if conn is None:
            return
        cursor = conn.cursor()

        # Create the 'voyages' table
        create_voyages_table = """
        CREATE TABLE IF NOT EXISTS voyages (
            portCallId TEXT PRIMARY KEY,
            imoLloyds TEXT,
            vesselTypeCode TEXT,
            vesselName TEXT,
            prevPort TEXT,
            portToVisit TEXT,
            nextPort TEXT,
            agentName TEXT,
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
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_voyages_table)

        # Create the 'arrivals' table
        create_arrivals_table = """
        CREATE TABLE IF NOT EXISTS arrivals (
            id SERIAL PRIMARY KEY,
            portCallId TEXT,
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

def process_query(data):
    """Process the JSON data and prepare results for database insertion."""
    if isinstance(data, dict) and "portCalls" in data:
        data = data["portCalls"]

    if not isinstance(data, list):
        log("Error: Expected a list of port calls in the JSON data.")
        return []

    results = []
    for entry in data:
        results.append({
            "portCallId": entry.get("portCallId", "N/A"),
            "imoLloyds": entry.get("imoLloyds", "N/A"),
            "vesselTypeCode": entry.get("vesselTypeCode", "N/A"),
            "vesselName": entry.get("vesselName", "N/A"),
            "prevPort": entry.get("prevPort", "N/A"),
            "portToVisit": entry.get("portToVisit", "N/A"),
            "nextPort": entry.get("nextPort", "N/A"),
            "agentName": entry.get("agentInfo", [{}])[0].get("name", "N/A"),
            "eta": entry.get("portAreaDetails", [{}])[0].get("eta"),
            "ata": entry.get("portAreaDetails", [{}])[0].get("ata"),
            "portAreaCode": entry.get("portAreaDetails", [{}])[0].get("portAreaCode", "N/A"),
            "portAreaName": entry.get("portAreaDetails", [{}])[0].get("portAreaName", "N/A"),
            "berthCode": entry.get("portAreaDetails", [{}])[0].get("berthCode", "N/A"),
            "berthName": entry.get("portAreaDetails", [{}])[0].get("berthName", "N/A"),
            "etd": entry.get("portAreaDetails", [{}])[0].get("etd"),
            "atd": entry.get("portAreaDetails", [{}])[0].get("atd"),
            "passengersOnArrival": sum(info.get("numberOfPassangers", 0) or 0 for info in entry.get("imoInformation", []) if info.get("imoGeneralDeclaration") == "Arrival"),
            "passengersOnDeparture": sum(info.get("numberOfPassangers", 0) or 0 for info in entry.get("imoInformation", []) if info.get("imoGeneralDeclaration") == "Departure"),
        })
    log(f"Processed {len(results)} records.")
    return results

def save_results_to_db(results):
    """Save processed results into the 'voyages' table and trigger arrivals only when `ata` is updated at the minute level."""
    try:
        log(f"Saving {len(results)} records to the database...")
        conn = get_db_connection("portman")
        if conn is None:
            return
        cursor = conn.cursor()

        new_arrival_count = 0  # Track the count of new arrivals

        # Extract unique portCallIds from JSON data (ensure all are strings)
        port_call_ids = list(set(str(entry["portCallId"]) for entry in results))

        # Fetch all old ata values in one query
        old_ata_map = {}
        if port_call_ids:
            query = f"""
                SELECT portCallId::TEXT, ata FROM voyages WHERE portCallId IN ({','.join(['%s'] * len(port_call_ids))});
            """
            cursor.execute(query, tuple(port_call_ids))
            fetched_data = cursor.fetchall()

            # Populate old_ata_map with correctly formatted timestamps (ignore NULL values)
            for row in fetched_data:
                port_call_id, old_ata = row
                if old_ata:  # Only store valid timestamps
                    formatted_ata = old_ata.strftime("%Y-%m-%d %H:%M:00")
                    old_ata_map[str(port_call_id)] = formatted_ata  # Ensure keys are strings

        for entry in results:
            port_call_id = str(entry["portCallId"])  # Ensure lookup key is a string
            new_ata = entry["ata"]

            # Convert new_ata from JSON format to PostgreSQL TIMESTAMP format
            new_ata_minute = None
            if new_ata:
                new_ata = datetime.strptime(new_ata[:19], "%Y-%m-%dT%H:%M:%S")  # Remove milliseconds & timezone
                new_ata_minute = new_ata.strftime("%Y-%m-%d %H:%M:00")  # Format as "YYYY-MM-DD HH:MM:00"

            # Fetch old ata from the map (default to None)
            old_ata_minute = old_ata_map.get(port_call_id, None)  # Now correctly handles mismatched types

            # Insert or update voyages
            cursor.execute("""
            INSERT INTO voyages (
                portCallId, imoLloyds, vesselTypeCode, vesselName, prevPort,
                portToVisit, nextPort, agentName, eta, ata, portAreaCode, 
                portAreaName, berthCode, berthName, etd, atd, 
                passengersOnArrival, passengersOnDeparture, modified
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (portCallId) 
            DO UPDATE SET 
                imoLloyds = EXCLUDED.imoLloyds,
                vesselTypeCode = EXCLUDED.vesselTypeCode,
                vesselName = EXCLUDED.vesselName,
                prevPort = EXCLUDED.prevPort,
                portToVisit = EXCLUDED.portToVisit,
                nextPort = EXCLUDED.nextPort,
                agentName = EXCLUDED.agentName,
                eta = EXCLUDED.eta,
                ata = EXCLUDED.ata,
                portAreaCode = EXCLUDED.portAreaCode,
                portAreaName = EXCLUDED.portAreaName,
                berthCode = EXCLUDED.berthCode,
                berthName = EXCLUDED.berthName,
                etd = EXCLUDED.etd,
                atd = EXCLUDED.atd,
                passengersOnArrival = EXCLUDED.passengersOnArrival,
                passengersOnDeparture = EXCLUDED.passengersOnDeparture,
                modified = CURRENT_TIMESTAMP;
            """, (
                entry["portCallId"], entry["imoLloyds"], entry["vesselTypeCode"], entry["vesselName"],
                entry["prevPort"], entry["portToVisit"], entry["nextPort"], entry["agentName"],
                entry["eta"], new_ata, entry["portAreaCode"], entry["portAreaName"],
                entry["berthCode"], entry["berthName"], entry["etd"], entry["atd"],
                entry["passengersOnArrival"], entry["passengersOnDeparture"]
            ))

            # Trigger notification if ata has changed at the minute level
            if old_ata_minute != new_ata_minute and new_ata_minute is not None:
                cursor.execute("""
                INSERT INTO arrivals (portCallId, eta, old_ata, ata, vesselName, portAreaName, berthName)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (port_call_id, entry["eta"], old_ata_minute, new_ata_minute, entry["vesselName"], entry["portAreaName"], entry["berthName"]))
                new_arrival_count += 1
                log(f"Trigger executed: New arrival detected for portCallId {port_call_id} (old_ata: {old_ata_minute}, new_ata: {new_ata_minute})")

        conn.commit()
        cursor.close()
        conn.close()
        log(f"{len(results)} records saved/updated in the database.")
        log(f"Total new arrivals detected: {new_arrival_count}")

    except Exception as e:
        log(f"Error saving results to the database: {e}")

def main():
    log("Program started.")
    create_database_and_tables()
    data = fetch_data_from_api()
    if data:
        results = process_query(data)
        save_results_to_db(results)
    log("Program completed.")

# Run the job once at startup
log("Running initial fetch...")
job()

# Schedule the job every 5 minutes
schedule.every(5).minutes.do(job)

log("Scheduler started. Fetching data every 5 minutes...")

# Keep the program running, handle shutdown gracefully
try:
    while True:
        schedule.run_pending()
        time.sleep(1)  # Prevent CPU overuse
except KeyboardInterrupt:
    log("Shutting down scheduler gracefully. Goodbye!")
