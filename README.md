# Portman Python Project - Usage & Installation Guide

The Portman Python project fetches, processes, and stores port call data in a PostgreSQL database.
It can process data from API requests or local JSON files (portnet*.json).

✅ Fetch data from an API (Default mode)\
✅ Read JSON data from a single file or directory (No API calls if input file/directory is provided)\
✅ Track specific vessels using IMO numbers\
✅ Automatically detect new arrivals and update the database

## Local usage
Download project to local machine:

```
git clone ...
cd portman
```

Setup a virtual environment (venv):

```
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate      # Windows
```

Install depencies:

```
pip install -r requirements.txt
```

### Database

Local postgres-instance must be installed and running. Database and schema are automatically created if missing.

Set the right db-credentials in [config.py](config.py) 
```
DATABASE_CONFIG = {
    "dbname": "portman",
    "user": "postgres",
    "password": "your_password",
    "host": "localhost",
    "port": 5432
}
```

Or set the credentials by environment variables:

```
export DB_NAME="portman_db"
export DB_USER="custom_user"
export DB_PASSWORD="secure_password"
export DB_HOST="192.168.1.100"
export DB_PORT="5432"
```

## Running the applications
### portman_agent

#### Option 1: Fetch data from the API
This will fetch data from the [Digitraffic Marine Port Calls API](https://meri.digitraffic.fi/swagger/#/Port%20Call%20V1/listAllPortCalls) and process it. Json-data is fetched every 5 mins from external api, parsed and saved into 'voyages'-table in postgres db. When detecting a new port arrival, it is saved into 'arrivals'-table.

`python portman_agent.py`

#### Option 2: Read JSON from a local file (no API request)

`python portman_agent.py --input-file ./tests/data/portnet_2025-02-03T10-00-00.json`

#### Option 3: Read all portnet*.json files in given directory in natural order

`python portman_agent.py --input-dir ./tests/data`

### Track Specific Vessels
Only process voyages for specified vessels by IMO numbers.

#### Option 1: Using CLI Argument

`python portman_agent.py --imo 9878319,9808259`

#### Option 2: Using Environment Variable

```
export TRACKED_VESSELS="9878319,9808259"
python portman.py
```

## python_poller
Fetches data from external API, parses and returns it in formatted output. Poller scheduled to run every 5 mins.
### Running the application
`python portman_poller.py`

### Stopping the Application
If running in the foreground, press:
```
CTRL + C
```

## Tests

### test_portman
Tests if json-data contains voyage(s) and arrival(s) of certain vessel by imo-number. 
Produces the route of the vessel as a test output. Utilisized by `pytest` and `sqlite3` in-memory database. 

#### Usage
```
pytest -s tests/test_portman.py --input-file ./tests/data/portnet-20250101000032.json --imo 9878319
```

#### Arguments
- Either argument `--input-dir` or `--input-file` must be provided.
- Argument `--imo` must be provided.

#### Options
- With option `-s` stdout logs and print-messages are always displayed. 

#### Validations
- ✅ Passes if there is at least 1 arrival (with `ata`) found in json-data.
- ❌ Failes if not.