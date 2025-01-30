# Usage

## python_downloader
Parses json-data and returns it in formatted output.
### Option 1: Use Local JSON File
`python portman_downloader.py --input-file <path_to_json>`

### Option 2: Fetch Data from API
`python portman_downloader.py`

## python_to_db
Json-data is fetched every 5 mins from external api, parsed and saved into 'voyages'-table in postgres db. When detecting a new port arrival, it is saved into 'arrivals'-table.

`python portman_to_db.py`

### Preconditions
Local postgres-instance must be listening in default postgres port *5432*. Database and schema are automatically created if missing.