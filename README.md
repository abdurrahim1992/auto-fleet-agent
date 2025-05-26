# Auto Fleet Agent

This script automates the process of monitoring and accepting jobs from the Company fleet portal based on specific criteria.

## Requirements

- Python 3.7+
- Chrome browser installed
- ChromeDriver (will be automatically managed by webdriver-manager)

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the following content:
```
EMAIL=your_username
PASSWORD=your_password
FLEET_URL=https://companyname.com/fleet/
ACCEPTABLE_DESTINATIONS=Genting,Melaka,Kuala Lumpur International Airport,Kuala Lumpur Airport
```

Replace `your_username` and `your_password` with your actual fleet portal credentials. You can modify the `ACCEPTABLE_DESTINATIONS` list to include other destinations you want to accept.

## Usage

Run the script:
```bash
python scraper.py
```

The script will:
1. Log in to the fleet portal
2. Monitor available jobs
3. Accept jobs that match the criteria:
   - Destination matches one of the acceptable destinations
   - Job is available for acceptance (timing and other restrictions are met)
4. Save API responses to JSON files for debugging and tracking
5. Track job history in a CSV file

## Features

- Automated login with user agreement handling
- Comprehensive job analysis including:
  - Vehicle type (Sedan, MPV-4, etc.)
  - Pickup time and location
  - Destination
  - Price
  - Distance and duration
  - Meet & Greet status
  - Special instructions
- Detailed logging and job tracking
- API response archiving with timestamps
- Multiple job processing in a single run

## Notes

- The script will automatically handle browser initialization and cleanup
- It will analyze all available jobs in each run
- Each job is checked against multiple criteria before acceptance
- API responses are saved with timestamps for tracking
- The script uses explicit waits to handle dynamic page loading
- Job history is maintained in a CSV file for reference

## Output Files

- `api_response_[DATE]_[TIME]_[INDEX].json`: API response data for each run
- `job_history.csv`: Record of all processed jobs 