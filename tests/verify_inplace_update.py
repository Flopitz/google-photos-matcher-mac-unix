import os
import json
import shutil
import sys
import subprocess
from PIL import Image
import time

# Setup paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
TEST_DIR = os.path.join(PROJECT_ROOT, 'tests', 'temp_test_data')

def setup_test_data():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

    # Create dummy JPG
    img = Image.new('RGB', (100, 100), color='red')
    img_path = os.path.join(TEST_DIR, 'test_image.jpg')
    img.save(img_path)
    
    # Create dummy JSON
    json_path = os.path.join(TEST_DIR, 'test_image.jpg.json')
    data = {
        "title": "test_image.jpg",
        "description": "",
        "imageViews": "0",
        "creationTime": {
            "timestamp": "1672531200",
            "formatted": "Jan 1, 2023, 12:00:00 AM UTC"
        },
        "photoTakenTime": {
            "timestamp": "1672531200",
            "formatted": "Jan 1, 2023, 12:00:00 AM UTC"
        },
        "geoData": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "altitude": 0.0,
            "latitudeSpan": 0.0,
            "longitudeSpan": 0.0
        },
        "geoDataExif": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "altitude": 0.0,
            "latitudeSpan": 0.0,
            "longitudeSpan": 0.0
        },
        "people": [],
        "url": "https://lh3.googleusercontent.com/..."
    }
    with open(json_path, 'w') as f:
        json.dump(data, f)
    
    print(f"Created test data in {TEST_DIR}")
    return img_path, json_path

def run_matcher():
    main_script = os.path.join(SRC_DIR, 'main.py')
    print(f"Running {main_script} on {TEST_DIR}")
    
    # Run the script
    # Arguments: <target_folder> [edited_word] [convert_all_to_jpg] [convert_if_needed]
    result = subprocess.run(
        [sys.executable, main_script, TEST_DIR, "edited", "false", "true"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT, # Run from root so imports work if needed (though imports in main.py are relative/local)
        env={**os.environ, 'PYTHONPATH': SRC_DIR} # Ensure src is in pythonpath
    )
    
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
        
    return result.returncode

def verify_results(img_path, json_path):
    print("Verifying results...")
    
    # 1. Check if image still exists in original location
    if os.path.exists(img_path):
        print("PASS: Image file remains in original location.")
    else:
        print("FAIL: Image file was moved or deleted!")
        return False
        
    # 2. Check if MatchedMedia folder was created but is empty (or doesn't exist depending on logic)
    # The script creates folders at start.
    matched_media = os.path.join(TEST_DIR, "MatchedMedia")
    if os.path.exists(matched_media):
        files_in_matched = os.listdir(matched_media)
        if not files_in_matched:
            print("PASS: MatchedMedia folder is empty.")
        else:
            print(f"FAIL: MatchedMedia folder is not empty: {files_in_matched}")
            return False
            
    # 3. Check if JSON file is deleted
    if not os.path.exists(json_path):
        print("PASS: JSON file was deleted.")
    else:
        print("FAIL: JSON file was NOT deleted!")
        return False

    return True

if __name__ == "__main__":
    img_path, json_path = setup_test_data()
    exit_code = run_matcher()
    if exit_code != 0:
        print("Scrpt failed to run")
        sys.exit(exit_code)
        
    if verify_results(img_path, json_path):
        print("ALL TESTS PASSED")
        # Cleanup
        shutil.rmtree(TEST_DIR)
        print("Cleanup done.")
    else:
        print("TESTS FAILED")
        sys.exit(1)
