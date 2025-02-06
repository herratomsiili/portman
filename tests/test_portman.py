import sys
import os
import pytest
import sqlite3
from tabulate import tabulate

# Ensure src is in the Python module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from portman_agent import process_query, save_results_to_db, read_json_from_file, read_json_from_directory

@pytest.fixture(scope="module")
def setup_database():
    """Set up a fresh database for testing."""
    conn = sqlite3.connect(":memory:")  # Use PostgreSQL if needed
    cursor = conn.cursor()

    # Create tables (use same schema as main program)
    cursor.execute("""
    CREATE TABLE voyages (
        portCallId INTEGER PRIMARY KEY,
        imoLloyds INTEGER,
        vesselTypeCode TEXT,
        vesselName TEXT,
        prevPort TEXT,
        portToVisit TEXT,
        nextPort TEXT,
        agentName TEXT,
        shippingCompany TEXT,
        eta TEXT,
        ata TEXT,
        portAreaCode TEXT,
        portAreaName TEXT,
        berthCode TEXT,
        berthName TEXT,
        etd TEXT,
        atd TEXT,
        passengersOnArrival INTEGER DEFAULT 0,
        passengersOnDeparture INTEGER DEFAULT 0,
        crewOnArrival INTEGER DEFAULT 0,
        crewOnDeparture INTEGER DEFAULT 0,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE arrivals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portCallId INTEGER,
        eta TEXT,
        old_ata TEXT,
        ata TEXT,
        vesselName TEXT,
        portAreaName TEXT,
        berthName TEXT,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    yield conn  # Provide the database connection to tests
    conn.close()

def test_process_json_files(setup_database, input_file, input_dir, tracked_vessels, capsys):
    """Test processing portnet.json files from a directory for a specific vessel."""
    conn = setup_database
    cursor = conn.cursor()


    # ✅ Read data from the correct source (validated in conftest.py)
    if input_file:
        json_data = read_json_from_file(input_file)
        assert json_data is not None, f"Failed to read JSON from {input_file}"
        results = process_query(json_data, tracked_vessels)
        save_results_to_db(results, conn)

    elif input_dir:
        read_json_from_directory(input_dir, tracked_vessels, conn)

    # Use the actual function to process JSON data
    #json_data = read_json_from_directory(input_dir, tracked_vessels)  # Track one vessel
    read_json_from_directory(input_dir, tracked_vessels, conn)  # Track one vessel
    #assert json_data is not None, "No data found in test JSON files."

    # Process and save data
    #results = process_query(json_data, tracked_vessels)
    #assert len(results) > 0, "No voyages found for the tracked vessel."

    #save_results_to_db(results, conn)

    tracked_vessel_imo = list(tracked_vessels)[0]
    # Step 1: Check if vessel appears in `voyages`
    cursor.execute("SELECT COUNT(*) FROM voyages WHERE imoLloyds = ?", (tracked_vessel_imo,))
    voyage_count = cursor.fetchone()[0]
    assert voyage_count > 0, f"No voyages found in DB for vessel IMO {tracked_vessels}"

    # Step 2: Check if at least one arrival is logged
    cursor.execute("SELECT COUNT(*) FROM arrivals WHERE portCallId IN (SELECT portCallId FROM voyages WHERE imoLloyds = ?)", (tracked_vessel_imo,))
    arrival_count = cursor.fetchone()[0]
    assert arrival_count > 0, "No new arrivals logged for tracked vessel."

    # Step 3: Fetch vessel name
    cursor.execute("SELECT DISTINCT vesselName FROM voyages WHERE imoLloyds = ?", (tracked_vessel_imo,))
    vessel_name = cursor.fetchone()[0] or "Unknown Vessel"

    # Step 4: Print vessel route after assertions in a structured format
    cursor.execute("""
    SELECT portToVisit, prevPort, nextPort, ata, atd 
    FROM voyages 
    WHERE imoLloyds = ? 
    ORDER BY portToVisit, prevPort, nextPort;
    """, (tracked_vessel_imo,))

    route = cursor.fetchall()
    if route:
        print(f"\n🛳️ **Vessel Route Summary - {vessel_name}** 🛳️\n")
        headers = ["Port", "Previous Port", "Next Port", "Arrival (UTC)", "Departure (UTC)"]
        print(tabulate(route, headers=headers, tablefmt="fancy_grid"))

        print("\n🌍 **Route Flow** 🌍\n")
        for i, row in enumerate(route):
            port, prev_port, next_port, ata, atd = row
            print(f"📍 {port} ({prev_port} → {port} → {next_port}) 🕓 Arrival: {ata} | Departure: {atd}")
            if i < len(route) - 1:
                print("    ↓")
                print("    ↓")

    else:
        print("\n⚠️ No voyage route found.\n")

    # Ensure test output includes route print
    assert len(route) > 0, "No valid voyage route found."
