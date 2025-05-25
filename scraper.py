import os
import time
import csv
import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Load environment variables
load_dotenv()

# Debug prints
print("Debug: Environment variables:")
print(f"EMAIL value: {os.getenv('EMAIL')}")
print(f"USERNAME value: {os.getenv('USERNAME')}")  # Check what system username is
print("-------------------")

class FleetScraper:
    def __init__(self):
        self.url = os.getenv("FLEET_URL", "https://companyname.com/fleet/")  # Default URL as fallback
        # Using EMAIL instead of USERNAME for clarity
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.acceptable_destinations = os.getenv("ACCEPTABLE_DESTINATIONS", "Genting,Melaka").split(",")
        self.refresh_interval = int(os.getenv("REFRESH_INTERVAL", "30"))  # Default 30 seconds
        self.session_duration = int(os.getenv("SESSION_DURATION", "300"))  # Default 5 minutes (300 seconds)
        self.use_reload_button = os.getenv("USE_RELOAD_BUTTON", "true").lower() == "true"  # Default to true
        self.monitoring_mode = os.getenv("MONITORING_MODE", "false").lower() == "true"  # Default to false
        self.api_data = None  # Store API data here
        
        # Setup CSV logging
        self.csv_file = 'job_history.csv'
        self.csv_headers = [
            'timestamp',
            'ride_id',
            'vehicle_type',
            'scheduled_pickup_time',
            'auction_start_time',
            'auction_amount',
            'auction_currency',
            'pickup_location',
            'dropoff_location',
            'distance',
            'duration',
            'meet_and_greet',
            'has_driver_instruction',
            'is_available',
            'can_accept',
            'meets_criteria',
            'rejection_reason'
        ]
        self.setup_csv()
        
        print(f"Initializing with email: {self.email}")
        print(f"Acceptable destinations: {self.acceptable_destinations}")
        if not self.email or not self.password:
            raise ValueError("Please create a .env file with your EMAIL and PASSWORD")
        
        # Setup Chrome DevTools Protocol
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Enable Performance Logging
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        
        # Use local ChromeDriver
        service = Service(executable_path="./chromedriver.exe")
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)  # 30 second timeout

    def setup_csv(self):
        """Setup CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.csv_headers)

    def save_api_response(self, response_data, index):
        """Save API response to a JSON file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'api_response_{timestamp}_{index}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved API response to {filename}")
        except Exception as e:
            print(f"❌ Error saving API response: {str(e)}")

    def capture_api_response(self):
        """Capture API response from the network logs"""
        try:
            logs = self.driver.get_log("performance")
            matching_responses = []
            response_index = 1
            
            # First collect all matching responses
            for log in logs:
                try:
                    log_entry = json.loads(log["message"])["message"]
                    
                    # Check if this is a Network.responseReceived event
                    if "Network.responseReceived" in log_entry["method"]:
                        url = log_entry["params"]["response"]["url"]
                        if "mfmyyv2bjh.execute-api.us-east-2.amazonaws.com/prod/sql-templates/run" in url:
                            request_id = log_entry["params"]["requestId"]
                            
                            # Get response body
                            response_body = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                            if response_body and "body" in response_body:
                                try:
                                    data = json.loads(response_body["body"])
                                    results = data.get("results", [])
                                    
                                    # Check if this is the ride data response
                                    if results and isinstance(results, list) and len(results) > 0:
                                        first_item = results[0]
                                        if all(key in first_item for key in ['ride_id', 'vehicle_class', 'from_name']):
                                            print(f"\nFound ride data response with {len(results)} jobs")
                                            # Save only the ride data response
                                            self.save_api_response(data, response_index)
                                            response_index += 1
                                            matching_responses.append(results)
                                except json.JSONDecodeError:
                                    continue
                except Exception as e:
                    print(f"Error processing log entry: {str(e)}")
                    continue
            
            # Use the response with the most jobs
            if matching_responses:
                best_response = max(matching_responses, key=len)
                self.api_data = best_response
                print(f"\nUsing response with {len(best_response)} jobs")
                return best_response
            
            print("No ride data API responses found")
            return []
        except Exception as e:
            print(f"Error capturing API response: {str(e)}")
            return []

    def get_api_data(self):
        """Get job data from the captured API response"""
        if self.api_data:
            return self.api_data
        return self.capture_api_response()

    def merge_job_data(self, api_jobs, visual_job_info):
        """Merge API and visual job data"""
        try:
            # Try to match API job with visual job based on location, vehicle type and pickup time
            for api_job in api_jobs:
                try:
                    # Get vehicle type from API job
                    api_vehicle_type = api_job.get('vehicle_class', {}).get('name')
                    api_pickup_location = api_job.get('from_name', '')
                    api_pickup_time = api_job.get('from_time_str', '')
                    
                    # Debug matching info
                    print(f"\nMatching attempt:")
                    print(f"API Job: {api_vehicle_type} at {api_pickup_time} from {api_pickup_location}")
                    print(f"Visual Job: {visual_job_info['vehicle_type']} from {visual_job_info['pickup_location']}")
                    
                    # Match based on vehicle type and pickup location
                    if (api_vehicle_type == visual_job_info['vehicle_type'] and
                        api_pickup_location == visual_job_info['pickup_location']):
                        
                        print("✅ Found matching job!")
                        merged_info = {
                            'ride_id': str(api_job.get('ride_id', 'N/A')),
                            'vehicle_type': api_vehicle_type,
                            'scheduled_pickup_time': api_pickup_time,
                            'auction_start_time_str': api_job.get('auction_start_time_str', 'N/A'),
                            'auction_amount': f"{float(api_job.get('auction_amount', 0)):.2f}",
                            'auction_currency': api_job.get('auction_currency', 'N/A'),
                            'pickup_location': api_pickup_location,
                            'dropoff_location': api_job.get('to_name', 'N/A'),
                            'distance': api_job.get('distance', 'N/A'),
                            'duration': api_job.get('duration', 'N/A'),
                            'meet_and_greet': bool(api_job.get('meet_and_greet', 0)),
                            'has_driver_instruction': bool(api_job.get('has_driver_instruction', 0)),
                            'can_accept': visual_job_info['can_accept'],
                            'accept_button': visual_job_info.get('accept_button')
                        }
                        return merged_info
                except Exception as e:
                    print(f"Error processing individual API job: {str(e)}")
                    continue
            
            print("❌ No matching API job found")
            # Return visual info with defaults if no API match found
            return {
                'ride_id': 'N/A',
                'vehicle_type': visual_job_info['vehicle_type'],
                'scheduled_pickup_time': visual_job_info.get('scheduled_pickup_time', 'N/A'),
                'auction_start_time_str': 'N/A',
                'auction_amount': '0.00',
                'auction_currency': 'N/A',
                'pickup_location': visual_job_info['pickup_location'],
                'dropoff_location': visual_job_info['dropoff_location'],
                'distance': 'N/A',
                'duration': 'N/A',
                'meet_and_greet': False,
                'has_driver_instruction': False,
                'can_accept': visual_job_info['can_accept'],
                'accept_button': visual_job_info.get('accept_button')
            }
            
        except Exception as e:
            print(f"Error in merge_job_data: {str(e)}")
            return visual_job_info

    def log_job_to_csv(self, job_info, meets_criteria, rejection_reason):
        """Log job information to CSV file"""
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    job_info.get('ride_id', 'N/A'),
                    job_info.get('vehicle_type', 'N/A'),
                    job_info.get('scheduled_pickup_time', 'N/A'),
                    job_info.get('auction_start_time_str', 'N/A'),
                    job_info.get('auction_amount', 'N/A'),
                    job_info.get('auction_currency', 'N/A'),
                    job_info.get('pickup_location', 'N/A'),
                    job_info.get('dropoff_location', 'N/A'),
                    job_info.get('distance', 'N/A'),
                    job_info.get('duration', 'N/A'),
                    job_info.get('meet_and_greet', False),
                    job_info.get('has_driver_instruction', False),
                    True,  # is_available (always true since we're logging it)
                    job_info.get('can_accept', False),
                    meets_criteria,
                    rejection_reason or 'N/A'
                ])
        except Exception as e:
            print(f"Error logging to CSV: {str(e)}")

    def wait_and_find_element(self, by, value, timeout=30, parent=None):
        """Wait for element to be present and return it"""
        try:
            print(f"Looking for element: {by}={value}")
            if parent:
                element = WebDriverWait(parent, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
            else:
                element = self.wait.until(
                    EC.presence_of_element_located((by, value))
                )
            print(f"Found element: {by}={value}")
            return element
        except TimeoutException:
            print(f"Timeout waiting for element: {by}={value}")
            print("Current page source:")
            print(self.driver.page_source[:1000])
            raise

    def login(self):
        """Log in to the fleet portal"""
        try:
            print("\nNavigating to login page...")
            self.driver.get(self.url)
            
            print("Waiting for page to load...")
            time.sleep(5)
            
            print("\nCurrent URL:", self.driver.current_url)
            print("Page title:", self.driver.title)
            
            # Find email input using exact selectors
            print("\nLooking for email input...")
            email_field = self.wait_and_find_element(
                By.CSS_SELECTOR, 
                "input[ref='emailInput'][is='e-input'][type='text'][class='--grow --bg-transparent --text-sm']"
            )
            
            # Find password input using exact selectors
            print("\nLooking for password input...")
            password_field = self.wait_and_find_element(
                By.CSS_SELECTOR, 
                "input[ref='passwordInput'][is='e-input'][type='password'][class='--grow --bg-transparent --text-sm']"
            )
            
            print("\nEntering credentials...")
            email_field.clear()
            email_field.send_keys(self.email)
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Find login button using exact selector
            print("\nLooking for login button...")
            login_button = self.wait_and_find_element(
                By.CSS_SELECTOR,
                "div[ref='submitBtn'][class*='--mt-12'][class*='--flex'][class*='--h-11']"
            )
            
            print("Clicking login button...")
            login_button.click()
            
            # Wait a bit for the agreement to appear
            time.sleep(3)
            
            # Handle user agreement
            print("\nLooking for user agreement button...")
            agreement_button = self.wait_and_find_element(
                By.CSS_SELECTOR,
                "div[class*='--bg-gradient-to-tr'][class*='--from-[#FF993C]'][class*='--to-[#FE7A1F]']"
            )
            
            print("Accepting user agreement...")
            agreement_button.click()
            
            # Wait for redirect and proceed
            print("\nWaiting for redirect...")
            try:
                # Wait for job cards to be present (indicates successful login and page load)
                self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[class*='--bg-white'][class*='--rounded-lg'][class*='--flex-col']")
                ))
                print("Successfully logged in and found job cards!")
                return True
            except TimeoutException:
                print("Failed to find job cards after login")
                return False

        except Exception as e:
            print(f"\nLogin failed with error: {str(e)}")
            print("\nFinal page source:")
            print(self.driver.page_source[:1000])
            return False

    def parse_job_card(self, job_card):
        """Extract all relevant information from a job card"""
        try:
            # Get vehicle type
            vehicle_type = job_card.find_element(
                By.CSS_SELECTOR, 
                "div[class*='--text-sm'][class*='--font-bold']"
            ).text

            # Get scheduled pickup time from the specific div
            scheduled_pickup_time = job_card.find_element(
                By.CSS_SELECTOR,
                "div[class*='--shrink-0'] div[class*='--text-sm'][class*='--font-bold']"
            ).text

            # Get pickup time
            pickup_time = job_card.find_element(
                By.CSS_SELECTOR,
                "div[class*='--text-sm'][class*='--font-bold']:last-child"
            ).text

            # Get locations
            locations = job_card.find_elements(
                By.CSS_SELECTOR,
                "div[class*='--line-clamp-1'][class*='--text-sm']"
            )
            pickup_location = locations[0].text
            dropoff_location = locations[1].text

            # Get price
            price = job_card.find_element(
                By.CSS_SELECTOR,
                "div[class*='--text-base'][class*='--text-primary']"
            ).text

            # Get accept button
            accept_button = job_card.find_element(
                By.CSS_SELECTOR,
                "div[is='e-tracing'][class*='--rounded-lg']"
            )
            can_accept = "bg-[#ddd]" not in accept_button.get_attribute("class")

            return {
                'vehicle_type': vehicle_type,
                'scheduled_pickup_time': scheduled_pickup_time,
                'pickup_time': pickup_time,
                'pickup_location': pickup_location,
                'dropoff_location': dropoff_location,
                'price': price,
                'can_accept': can_accept,
                'accept_button': accept_button if can_accept else None
            }
        except Exception as e:
            print(f"Error parsing job card: {str(e)}")
            return None

    def is_acceptable_job(self, job_card, merged_info):
        """Check if the job meets acceptance criteria"""
        try:
            job_info = self.parse_job_card(job_card)
            if not job_info:
                return False

            # Check if job can be accepted
            if not job_info['can_accept']:
                print("❌ Job cannot be accepted (button disabled)")
                return False

            # Check if auction has started
            if merged_info and 'auction_start_time_str' in merged_info:
                try:
                    auction_start = datetime.strptime(merged_info['auction_start_time_str'], '%Y-%m-%d %H:%M')
                    current_time = datetime.now()
                    if current_time < auction_start:
                        print(f"❌ Auction hasn't started yet. Starts at {auction_start}")
                        return False
                except ValueError as e:
                    print(f"❌ Invalid auction start time format: {merged_info['auction_start_time_str']}")
                    return False

            # Check if destination is acceptable (using substring matching)
            destination = merged_info.get('dropoff_location', '') if merged_info else job_info.get('dropoff_location', '')
            if not any(acceptable.lower() in destination.lower() for acceptable in self.acceptable_destinations):
                print("❌ Destination not in acceptable list")
                return False

            return True
        except Exception as e:
            print(f"Error checking job acceptance criteria: {str(e)}")
            return False

    def accept_job(self, job_card):
        """Accept a job that meets the criteria"""
        try:
            # Find the accept button with exact selector
            accept_button = job_card.find_element(
                By.CSS_SELECTOR,
                "div[is='e-tracing'][tracing-name='user_available_accept'][class*='--rounded-lg'][class*='--text-white']"
            )

            if not accept_button:
                return False

            print("\nAccepting job:")
            job_info = self.parse_job_card(job_card)
            print(f"Vehicle: {job_info['vehicle_type']}")
            print(f"Time: {job_info['pickup_time']}")
            print(f"From: {job_info['pickup_location']}")
            print(f"To: {job_info['dropoff_location']}")
            print(f"Price: {job_info['price']}")

            # Click the accept button
            print("Clicking initial accept button...")
            self.driver.execute_script("arguments[0].click();", accept_button)

            # Wait for and click the confirmation button
            try:
                print("Looking for confirmation button...")
                confirm_button = self.wait_and_find_element(
                    By.CSS_SELECTOR,
                    "div[class='--w-full --h-full --absolute --top-0 --left-0']"
                )
                print("Found confirmation button, clicking...")
                self.driver.execute_script("arguments[0].click();", confirm_button)
                
                # Wait longer for the bid to be processed
                print("Waiting for bid to be processed...")
                time.sleep(5)  # Increased wait time
                
                # Try to verify if bid was accepted by checking if the job card is still visible
                try:
                    job_cards = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        "div[class*='--bg-white'][class*='--rounded-lg'][class*='--flex-col']"
                    )
                    if len(job_cards) > 0:
                        print("⚠️ Job cards still visible - bid may not have been accepted")
                        return False
                    else:
                        print("✅ Job cards no longer visible - bid likely accepted!")
                        return True
                except:
                    print("Could not verify bid status")
                    return True  # Return True since we clicked both buttons successfully
                
            except Exception as e:
                print(f"Error clicking confirmation button: {str(e)}")
                return False

        except Exception as e:
            print(f"Error accepting job: {str(e)}")
            return False

    def scroll_to_bottom(self):
        """Scroll down until no more new jobs appear"""
        try:
            print("\nScrolling to load all jobs...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            job_count = 0
            
            while True:
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # Wait for content to load
                
                # Get current job count
                current_jobs = len(self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "div[class*='--bg-white'][class*='--rounded-lg'][class*='--flex-col']"
                ))
                
                # Check if more jobs were loaded
                if current_jobs > job_count:
                    print(f"Found {current_jobs} jobs...")
                    job_count = current_jobs
                    continue
                
                # Get new height
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                # Break if no new content loaded
                if new_height == last_height:
                    print(f"No more jobs to load. Total jobs found: {job_count}")
                    break
                    
                last_height = new_height
                
        except Exception as e:
            print(f"Error while scrolling: {str(e)}")

    def process_jobs(self):
        """Process all available jobs. Returns True if a job was accepted."""
        try:
            # Scroll to load all jobs first
            self.scroll_to_bottom()
            
            # Get populated API data
            print("\nGetting API response data...")
            api_jobs = self.get_api_data()
            if api_jobs:
                print(f"Found {len(api_jobs)} jobs in API response")

            # Get all loaded job cards
            print("\nLooking for visual job cards...")
            job_cards = self.wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div[class*='--bg-white'][class*='--rounded-lg'][class*='--flex-col']")
            ))
            
            total_cards = len(job_cards)
            print(f"\nFound {total_cards} visual job cards")
            
            if total_cards == 0:
                print("No jobs available at the moment")
                return False
            
            print("\nAnalyzing all job cards:")
            print("-" * 50)
            
            available_jobs = 0
            rejected_jobs = 0
            rejection_reasons = []
            
            for index, job_card in enumerate(job_cards, 1):
                print(f"\nJob Card {index}/{total_cards}:")
                
                # Parse visual job information
                visual_job_info = self.parse_job_card(job_card)
                if not visual_job_info:
                    print("❌ Failed to parse job card")
                    continue
                
                # Merge with API data
                job_info = self.merge_job_data(api_jobs, visual_job_info)
                
                # Print job details
                print(f"🆔 Ride ID: {job_info.get('ride_id', 'N/A')}")
                print(f"🚗 Vehicle: {job_info['vehicle_type']}")
                print(f"📅 Pickup Time: {job_info.get('scheduled_pickup_time', 'N/A')}")
                print(f"⏰ Auction Start: {job_info.get('auction_start_time_str', 'N/A')}")
                print(f"💰 Price: {job_info.get('auction_currency', '')} {job_info.get('auction_amount', '')}")
                print(f"📍 From: {job_info['pickup_location']}")
                print(f"🎯 To: {job_info['dropoff_location']}")
                print(f"📏 Distance: {job_info.get('distance', 'N/A')}m")
                print(f"⏱️ Duration: {job_info.get('duration', 'N/A')}s")
                print(f"🤝 Meet & Greet: {job_info.get('meet_and_greet', 'N/A')}")
                print(f"📝 Has Instructions: {job_info.get('has_driver_instruction', 'N/A')}")
                print(f"🔓 Can Accept: {job_info['can_accept']}")
                
                # Check if job meets acceptance criteria
                if job_info['can_accept']:
                    available_jobs += 1
                    rejection_reason = None
                    
                    # Check if job meets all criteria
                    if self.is_acceptable_job(job_card, job_info):
                        # Job meets all criteria
                        self.log_job_to_csv(job_info, True, None)
                        print("✅ Job meets all criteria!")
                        
                        # Try to accept the job
                        print("\nAttempting to accept job...")
                        if self.accept_job(job_card):
                            print("🎉 Successfully accepted the job!")
                            return True
                        else:
                            print("❌ Failed to accept job, trying next one")
                            rejection_reason = "Failed to accept job"
                    else:
                        rejection_reason = "Does not meet acceptance criteria"
                    
                    if rejection_reason:
                        rejected_jobs += 1
                        rejection_reasons.append({
                            'ride_id': job_info.get('ride_id', 'N/A'),
                            'vehicle': job_info['vehicle_type'],
                            'from': job_info['pickup_location'],
                            'to': job_info['dropoff_location'],
                            'reason': rejection_reason
                        })
                        self.log_job_to_csv(job_info, False, rejection_reason)
                else:
                    print("❌ Cannot accept this job")
                    self.log_job_to_csv(job_info, False, "Cannot accept")
            
            print("\n" + "-" * 50)
            print(f"Summary:")
            print(f"Total jobs: {total_cards}")
            print(f"Available to accept: {available_jobs}")
            print(f"Rejected: {rejected_jobs}")
            if rejected_jobs > 0:
                print("\nRejected jobs:")
                for job in rejection_reasons:
                    print(f"- Ride {job['ride_id']} ({job['vehicle']}) from {job['from']} to {job['to']}")
                    print(f"  Reason: {job['reason']}")
            print("-" * 50)
            
            return False

        except Exception as e:
            print(f"Error processing jobs: {str(e)}")
            return False

    def click_reload_button(self):
        """Click the reload button if it exists"""
        try:
            # Find the refresh button container first
            print("Looking for reload button...")
            refresh_container = self.wait_and_find_element(
                By.CSS_SELECTOR,
                "div.--flex.--h-full.--items-center.--px-2",
                timeout=10  # Shorter timeout for reload button
            )
            
            # Then find the reload icon within it
            reload_button = refresh_container.find_element(
                By.CSS_SELECTOR,
                "i.icon.--inline-block.--relative.i-reload"
            )
            
            print("Found reload button, clicking...")
            reload_button.click()
            
            # Wait for page to start refreshing
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"Error finding/clicking reload button: {str(e)}")
            return False

    def refresh_page(self):
        """Refresh the page either using button or browser refresh"""
        try:
            if self.use_reload_button:
                success = self.click_reload_button()
                if not success:
                    print("Failed to use reload button, falling back to browser refresh")
                    self.driver.refresh()
            else:
                self.driver.refresh()
            
            # Wait for page to load after refresh
            print("Waiting for page to load after refresh...")
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[class*='--bg-white'][class*='--rounded-lg'][class*='--flex-col']")
            ))
            print("Page refreshed successfully")
            
        except Exception as e:
            print(f"Error during refresh: {str(e)}")
            print("Attempting to recover...")
            try:
                self.driver.refresh()
                time.sleep(5)  # Give extra time for recovery
            except:
                print("Could not recover from refresh error")

    def run(self):
        """Main execution method"""
        try:
            if not self.login():
                return

            if self.monitoring_mode:
                print("\nStarting monitoring session...")
                print(f"Session duration: {self.session_duration} seconds")
                print(f"Refresh interval: {self.refresh_interval} seconds")
                print(f"Using reload button: {self.use_reload_button}")
                
                start_time = time.time()
                end_time = start_time + self.session_duration

                while time.time() < end_time:
                    remaining_time = int(end_time - time.time())
                    print(f"\nTime remaining: {remaining_time} seconds")
                    
                    print("\nChecking for jobs...")
                    if self.process_jobs():
                        print("✅ Successfully accepted a job! Ending session...")
                        break
                    
                    if time.time() < end_time:
                        next_refresh = min(self.refresh_interval, remaining_time)
                        if next_refresh > 0:
                            print(f"\nWaiting {next_refresh} seconds before next refresh...")
                            time.sleep(next_refresh)
                            print("\nRefreshing page...")
                            self.refresh_page()
                
                print("\nMonitoring session completed!")
            else:
                print("\nStarting single job check...")
                if self.process_jobs():
                    print("✅ Successfully accepted a job!")
                print("\nCheck completed!")

        except Exception as e:
            print(f"\nError in main loop: {str(e)}")
        finally:
            print("\nClosing browser...")
            self.driver.quit()

if __name__ == "__main__":
    # Check for environment variables
    if not os.getenv("EMAIL") or not os.getenv("PASSWORD"):
        print("Please set EMAIL and PASSWORD in .env file")
    else:
        print("\nScript Settings:")
        print(f"Monitoring Mode: {os.getenv('MONITORING_MODE', 'false')}")
        if os.getenv("MONITORING_MODE", "false").lower() == "true":
            print(f"Refresh Interval: {os.getenv('REFRESH_INTERVAL', '30')} seconds")
            print(f"Session Duration: {os.getenv('SESSION_DURATION', '300')} seconds")
            print(f"Use Reload Button: {os.getenv('USE_RELOAD_BUTTON', 'true')}")
        print("-" * 50)
        scraper = FleetScraper()
        scraper.run() 