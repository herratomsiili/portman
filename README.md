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
### python_to_db

#### Option 1: Fetch data from the API
This will fetch data from the [Digitraffic Marine Port Calls API](https://meri.digitraffic.fi/swagger/#/Port%20Call%20V1/listAllPortCalls) and process it. Json-data is fetched every 5 mins from external api, parsed and saved into 'voyages'-table in postgres db. When detecting a new port arrival, it is saved into 'arrivals'-table.

`python portman_to_db.py`

#### Option 2: Read JSON from a local file (no API request)

`python portman.py --input-file ./data/portnet_2025-02-03T10-00-00.json`

#### Option 2: Read all portnet*.json files in given directory in natural order

`python portman.py --input-dir ./data`

### Track Specific Vessels
Only process voyages for specified vessels by IMO numbers.

#### Option 1: Using CLI Argument

`python portman.py --imo 9878319,9808259`

#### Option 2: Using Environment Variable

```
export TRACKED_VESSELS="9878319,9808259"
python portman.py
```

## python_downloader
Parses json-data and returns it in formatted output.
### Option 1: Use Local JSON File
`python portman_downloader.py --input-file <path_to_json>`

### Option 2: Fetch Data from API
`python portman_downloader.py`

## Stopping the Application
If running in the foreground, press:
```
CTRL + C
```