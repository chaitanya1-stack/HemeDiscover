import os
import requests

# Create a separate directory to save the negative control files
os.makedirs("non_heme_proteins", exist_ok=True)

# Define the PDB API URL
url = "https://search.rcsb.org/rcsbsearch/v2/query"

# Construct a compound query: Must contain ATP, must NOT contain HEM
query = {
    "query": {
        "type": "group",
        "logical_operator": "and",
        "nodes": [
            {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id",
                    "operator": "exact_match",
                    "value": "ATP"
                }
            },
            {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id",
                    "operator": "exact_match",
                    "negation": True,
                    "value": "HEM"
                }
            }
        ]
    },
    "return_type": "entry",
    "request_options": {
        "paginate": {  
            "start": 0,
            "rows": 800
        }
    }
}

print("Querying the RCSB PDB Database for non-heme control structures...")
response = requests.post(url, json=query)

# Check the HTTP status code to ensure the query was accepted
if response.status_code == 200:
    data = response.json()
    
    if "result_set" in data:
        pdb_ids = [result["identifier"] for result in data["result_set"]]
        print(f"Success! Found {len(pdb_ids)} non-heme control proteins. Starting download...")
        
        # Download each PDB file
        for pdb_id in pdb_ids:
            pdb_url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
            pdb_response = requests.get(pdb_url)
            
            if pdb_response.status_code == 200:
                with open(f"non_heme_proteins/{pdb_id}.pdb", "w") as f:
                    f.write(pdb_response.text)
            else:
                print(f"Failed to download {pdb_id}")
                
        print("Negative dataset download complete!")
    else:
        print("Query succeeded, but no 'result_set' found in response. Data:", data)
        
elif response.status_code == 204:
    print("API returned 204 No Content: No structures matched the query filters.")
else:
    print(f"API Error {response.status_code}: {response.text}")