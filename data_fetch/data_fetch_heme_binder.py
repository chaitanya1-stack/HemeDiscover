import os
import requests
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Create directory
os.makedirs("heme_proteins", exist_ok=True)

def download_pdb(pdb_id):
    """Function to download a single PDB file."""
    filename = f"heme_proteins/{pdb_id}.pdb"
    
    # Skip if already downloaded
    if os.path.exists(filename):
        return None  # Return None so tqdm doesn't count this as a 'new' success
    
    pdb_url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        response = requests.get(pdb_url, timeout=10)
        if response.status_code == 200:
            with open(filename, "w") as f:
                f.write(response.text)
            return True
        return False
    except Exception:
        return False

# Search API
url = "https://search.rcsb.org/rcsbsearch/v2/query"
query = {
    "query": {
        "type": "terminal",
        "service": "text",
        "parameters": {
            "attribute": "rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id",
            "operator": "exact_match",
            "value": "HEM"
        }
    },
    "return_type": "entry",
    "request_options": {
        "paginate": {"start": 801, "rows": 10000}
    }
}

print("Querying RCSB...")
response = requests.post(url, json=query)

if response.status_code == 200:
    data = response.json()
    pdb_ids = [result["identifier"] for result in data.get("result_set", [])]
    print(f"Found {len(pdb_ids)} files.")
    
    # Use ThreadPoolExecutor with tqdm progress bar
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(tqdm(executor.map(download_pdb, pdb_ids), total=len(pdb_ids), desc="Downloading PDBs"))
    
    print("Download process complete.")
else:
    print(f"API Error: {response.status_code}")