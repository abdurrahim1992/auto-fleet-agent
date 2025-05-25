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
ACCEPTABLE_DESTINATIONS=Genting,Melaka
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
   - Pickup location is not KLIA
   - Destination matches one of the acceptable destinations
4. Automatically refresh the page every minute if no acceptable jobs are found

## Notes

- The script will automatically handle browser initialization and cleanup
- It will stop after successfully accepting a job
- Make sure your credentials in the `.env` file are correct
- The script uses explicit waits to handle dynamic page loading 