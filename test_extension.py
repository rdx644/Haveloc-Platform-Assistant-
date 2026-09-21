from playwright.sync_api import sync_playwright
import os
import sys
import time

extension_path = os.path.abspath("extension")

print(f"Loading extension from {extension_path}")

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        "",
        headless=False,
        args=[
            f"--disable-extensions-except={extension_path}",
            f"--load-extension={extension_path}",
        ]
    )
    
    page = browser.new_page()
    page.goto('http://localhost:8080/jobs/HVL-LTM-2026/apply')
    page.wait_for_load_state('networkidle')
    
    print("Navigated to job apply page.")
    time.sleep(2)
    try:
        print("Triggering EXTRACT_AND_PREPARE via service worker...")
        # Get the service worker (background script)
        background = browser.service_workers[0]
        
        # Trigger the pipeline by sending a message to the active tab
        response = background.evaluate('''async () => {
            return new Promise((resolve) => {
                chrome.tabs.query({active: true}, (tabs) => {
                    chrome.tabs.sendMessage(tabs[0].id, { type: "EXTRACT_AND_PREPARE" }, (resp) => {
                        resolve(resp);
                    });
                });
            });
        }''')
        
        print(f"Pipeline started: {response}")
        
        # Wait 3 seconds for the backend to process the payload
        import time
        time.sleep(3)
        
        # Now fetch the backend to see if the student profile was synced correctly
        import requests
        res = requests.get("http://localhost:8000/student/RA2311028010135/profile")
        if res.status_code == 200:
            student = res.json()
            print(f"SUCCESS! Profile synced for student: {student.get('name')} with CGPA: {student.get('cgpa')}")
        else:
            print("Failed to find student in backend.")
        
    except Exception as e:
        print(f"Error: {e}")
        
    browser.close()
