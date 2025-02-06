import pytest

def pytest_addoption(parser):
    """Add custom command-line options for pytest."""
    parser.addoption("--input-dir", action="store", help="Directory containing test JSON files")
    parser.addoption("--input-file", action="store", help="Path to a single JSON test file")
    parser.addoption("--imo", action="store", help="Comma-separated IMO numbers to track")

def pytest_configure(config):
    """Validate CLI arguments before tests run."""
    input_dir = config.getoption("--input-dir")
    input_file = config.getoption("--input-file")
    imo = config.getoption("--imo")

    if not input_dir and not input_file:
        pytest.exit("ERROR: Either --input-dir or --input-file must be provided.", returncode=1)

    if input_dir and input_file:
        pytest.exit("ERROR: You cannot provide both --input-dir and --input-file at the same time.", returncode=1)

    if not imo:
        pytest.exit("ERROR: --imo must be provided.", returncode=1)

@pytest.fixture
def input_dir(request):
    """Fixture to get the input directory from pytest command-line options."""
    return request.config.getoption("--input-dir")

@pytest.fixture
def input_file(request):
    """Fixture to get the input file from pytest command-line options."""
    return request.config.getoption("--input-file")

@pytest.fixture
def tracked_vessels(request):
    """Fixture to get IMO numbers from pytest command-line options."""
    return set(map(int, request.config.getoption("--imo").split(",")))
