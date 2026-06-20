import os
from tqdm import tqdm

# Point this to your existing folder
INPUT_DIR = "heme_proteins"
# This is where the clean files will go
OUTPUT_DIR = "heme_proteins_apo"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get all the .pdb files you already downloaded
pdb_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.pdb')]

print(f"Found {len(pdb_files)} existing PDB files. Cleaning them now...")

for filename in tqdm(pdb_files, desc="Converting to Apo"):
    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    # Skip if we already cleaned this one
    if os.path.exists(output_path):
        continue
        
    with open(input_path, 'r') as f:
        lines = f.readlines()
        
    cleaned_lines = []
    for line in lines:
        # Strip out the Heme molecules
        if line.startswith("HETATM") and "HEM" in line:
            continue
        cleaned_lines.append(line)
        
    with open(output_path, 'w') as f:
        f.writelines(cleaned_lines)

print("✅ Done! Your Apo dataset is ready in milliseconds.")