import os
import glob
import subprocess
import math
import shutil  
import numpy as np
import pandas as pd
import concurrent.futures
from functools import partial
from tqdm import tqdm

# Directories
HOLO_DIR = "../data_fetch/heme_proteins"        
APO_DIR = "../data_fetch/heme_proteins_apo"     
NON_HEME_DIR = "../data_fetch/non_heme_proteins"
OUTPUT_CSV = "labeled_pocket_features.csv"

# CONSTANT: Max file size in bytes (2.5 MB). Skips massive complexes that hang fpocket.
MAX_FILE_SIZE_BYTES = 2.5 * 1024 * 1024 

def create_clean_apo_pdb(input_pdb_path, output_pdb_path):
    """
    Strips HEME and crystallization artifacts, but safely preserves 
    structural metals and covalently modified amino acids to prevent 
    artificial backbone cavities.
    """
    # 1. Structural Metals (Including common oxidation states)
    metals = ['ZN', 'MG', 'CA', 'MN', 'FE', 'FE2', 'FE3', 'CU', 'NI', 'CO', 'MO']
    
    # 2. Modified Amino Acids (Crucial to prevent broken protein chains)
    mod_res = ['MSE', 'SEP', 'TPO', 'PTR', 'PCA', 'CME', 'CSX', 'CSO']
    
    # Combine into a fast lookup set
    approved_hetatms = set(metals + mod_res)
    
    with open(input_pdb_path, 'r') as infile, open(output_pdb_path, 'w') as outfile:
        for line in infile:
            if line.startswith("ATOM"):
                outfile.write(line)
                
            elif line.startswith("HETATM"):
                # Defeat unpredictable PDB whitespace formatting by stripping
                res_name = line[17:20].strip() 
                
                # Keep it if it's a structural metal or a modified amino acid
                if res_name in approved_hetatms:
                    outfile.write(line)
                    
            elif line.startswith("TER") or line.startswith("END"):
                outfile.write(line)

def get_hem_centroid(pdb_path):
    """Parses a PDB file to find HEM or HEC ligand centroid."""
    x_coords, y_coords, z_coords = [], [], []
    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("HETATM") and line[17:20] in ["HEM", "HEC"]:
                try:
                    x_coords.append(float(line[30:38].strip()))
                    y_coords.append(float(line[38:46].strip()))
                    z_coords.append(float(line[46:54].strip()))
                except ValueError:
                    continue
    if not x_coords:
        return None
    return (np.mean(x_coords), np.mean(y_coords), np.mean(z_coords))

def calculate_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)

def process_single_pdb(pdb_filename, apo_dir, holo_dir, is_positive_class):
    pdb_id = pdb_filename.split('.')[0]
    original_apo_path = os.path.join(apo_dir, pdb_filename)
    holo_path = os.path.join(holo_dir, pdb_filename)
    hem_centroid = get_hem_centroid(holo_path) if is_positive_class else None
    
    # ---> 1. CLEAN THE PDB ON THE FLY <---
    clean_apo_filename = f"{pdb_id}_clean.pdb"
    clean_apo_path = os.path.join(apo_dir, clean_apo_filename)
    
    try:
        create_clean_apo_pdb(original_apo_path, clean_apo_path)
    except Exception:
        return []

    try:
        # ---> 2. RUN FPOCKET WITH COFACTOR-SIZE FILTER (-i 60) <---
        subprocess.run(['fpocket', '-f', clean_apo_path, '-i', '60'], capture_output=True, timeout=30)
    except Exception:
        if os.path.exists(clean_apo_path): os.remove(clean_apo_path)
        return []
    
    # fpocket appends "_clean_out" to our generated filename
    out_dir_path = os.path.join(apo_dir, f"{pdb_id}_clean_out")
    info_file = os.path.join(out_dir_path, f"{pdb_id}_clean_info.txt")
    
    if not os.path.exists(info_file): 
        if os.path.exists(clean_apo_path): os.remove(clean_apo_path)
        if os.path.exists(out_dir_path): shutil.rmtree(out_dir_path)
        return []
        
    with open(info_file, 'r') as f:
        lines = f.readlines()
    
    curr_pkt = {}
    pockets_extracted = 0
    protein_pockets = []
    
    for line in lines:
        line = line.strip()
        if line.startswith("Pocket") and ":" in line and not line.endswith("parameters"):
            if curr_pkt and len(curr_pkt) > 2:
                protein_pockets.append(curr_pkt)
                pockets_extracted += 1
            
            # Extract up to 10 pockets for comprehensive machine learning decoy training
            if pockets_extracted >= 10: 
                break
            
            pocket_name = line.split(":")[0].strip()
            pocket_num = pocket_name.replace("Pocket", "").strip()
            
            # Point to the on-the-fly clean output directory structures
            atm_file = os.path.join(out_dir_path, "pockets", f"pocket{pocket_num}_atm.pdb")
            
            res_counts = {'HIS': 0, 'CYS': 0, 'MET': 0, 'TYR': 0, 'PHE': 0, 'TRP': 0, 'ARG': 0, 'LYS': 0}
            aliphatic_count = 0
            aromatic_count = 0
            has_cp_motif = 0
            has_cxxch_motif = 0
            
            if os.path.exists(atm_file):
                unique_residues = set()
                sequence_map = {}
                
                with open(atm_file, 'r') as f_atm:
                    for atm_line in f_atm:
                        if atm_line.startswith("ATOM") or atm_line.startswith("HETATM"):
                            res_name = atm_line[17:20].strip()
                            chain_id = atm_line[21]
                            try:
                                res_seq = int(atm_line[22:26].strip())
                            except ValueError: continue
                                
                            unique_residues.add((res_name, chain_id, res_seq))
                            
                            if chain_id not in sequence_map:
                                sequence_map[chain_id] = {}
                            sequence_map[chain_id][res_seq] = res_name

                for res_name, _, _ in unique_residues:
                    if res_name in res_counts:
                        res_counts[res_name] += 1
                    if res_name in ['ALA', 'ILE', 'VAL', 'LEU']:
                        aliphatic_count += 1
                    if res_name in ['PHE', 'TYR', 'TRP']:
                        aromatic_count += 1
                        
                for chain, seq_dict in sequence_map.items():
                    seq_nums = sorted(seq_dict.keys())
                    for i in range(len(seq_nums) - 1):
                        if seq_nums[i+1] == seq_nums[i] + 1:
                            if seq_dict[seq_nums[i]] == 'CYS' and seq_dict[seq_nums[i+1]] == 'PRO':
                                has_cp_motif = 1
                    for i in range(len(seq_nums) - 4):
                        if seq_nums[i+4] == seq_nums[i] + 4:
                            if seq_dict[seq_nums[i]] == 'CYS' and seq_dict[seq_nums[i+4]] == 'HIS':
                                has_cxxch_motif = 1

            vert_file = os.path.join(out_dir_path, "pockets", f"pocket{pocket_num}_vert.pqr")
            px, py, pz = [], [], []
            pocket_flatness = 0.0
            
            if os.path.exists(vert_file):
                with open(vert_file, 'r') as f_vert:
                    for vert_line in f_vert:
                        if vert_line.startswith("ATOM") or vert_line.startswith("HETATM"):
                            try:
                                px.append(float(vert_line[30:38].strip()))
                                py.append(float(vert_line[38:46].strip()))
                                pz.append(float(vert_line[46:54].strip()))
                            except ValueError: pass
                
                if len(px) >= 3:
                    coords = np.vstack((px, py, pz)).T
                    cov_mat = np.cov(coords, rowvar=False)
                    try:
                        eigenvalues, _ = np.linalg.eigh(cov_mat)
                        eigenvalues = np.sort(eigenvalues)[::-1]
                        if eigenvalues[2] > 0.001:
                            pocket_flatness = (eigenvalues[0] * eigenvalues[1]) / (eigenvalues[2] ** 2)
                    except Exception: pass

            curr_pkt = {
                'PDB_ID': pdb_id, 
                'Pocket_ID': pocket_name, 
                'Target': 0,
                'count_HIS': res_counts['HIS'],
                'count_CYS': res_counts['CYS'],
                'count_MET': res_counts['MET'],
                'count_TYR': res_counts['TYR'],
                'aliphatic_hydrophobic_count': aliphatic_count,
                'aromatic_count': aromatic_count,
                'propionate_stabilization_score': res_counts['ARG'] + res_counts['LYS'],
                'has_CP_motif': has_cp_motif,
                'has_CXXCH_motif': has_cxxch_motif,
                'pocket_flatness_index': round(pocket_flatness, 3),
                'center_of_mass_x': np.mean(px) if px else None,
                'center_of_mass_y': np.mean(py) if py else None,
                'center_of_mass_z': np.mean(pz) if pz else None
            }
        
        elif curr_pkt is not None and ":" in line:
            parts = line.split(":", 1)
            key_clean = parts[0].strip().lower().replace(' ', '_')
            val = parts[1].strip()
            if key_clean != "residues":
                try: 
                    curr_pkt[key_clean] = float(val)
                except ValueError: 
                    curr_pkt[key_clean] = val
                    
    if curr_pkt and len(curr_pkt) > 2 and pockets_extracted < 10:
        protein_pockets.append(curr_pkt)

    if is_positive_class and hem_centroid and protein_pockets:
        best_idx, best_comp = -1, -float('inf')
        for i, pkt in enumerate(protein_pockets):
            x, y, z = pkt.get('center_of_mass_x'), pkt.get('center_of_mass_y'), pkt.get('center_of_mass_z')
            if x is not None and y is not None and z is not None:
                dist = calculate_distance(hem_centroid, (x, y, z))
                
                # ---> THE FIX: WIDENED THRESHOLD TO 15.0 TO ACCOUNT FOR APO RELAXATION <---
                if dist < 15.0:
                    score = float(pkt.get('score', 0))
                    volume = float(pkt.get('volume', 0))
                    comp = (score * 50) + (volume * 0.1) - (dist * 10)
                    if comp > best_comp:
                        best_comp, best_idx = comp, i
                        
        if best_idx != -1: 
            protein_pockets[best_idx]['Target'] = 1
            
    # ---> 3. SELF-CLEANING DEVOPS PATTERN <---
    # Forcefully deletes the bloated temporary folder structure
    if os.path.exists(out_dir_path):
        try:
            shutil.rmtree(out_dir_path) 
        except Exception:
            pass
            
    # Deletes the temporary intermediate clean .pdb text file
    if os.path.exists(clean_apo_path):
        try:
            os.remove(clean_apo_path) 
        except Exception:
            pass
            
    return protein_pockets

def process_and_save_streaming(apo_dir, holo_dir, is_positive_class, is_first_write, global_cols, processed_pdbs):
    all_files = glob.glob(os.path.join(apo_dir, "*.pdb"))
    
    pdb_files = []
    skipped_count = 0
    for f in all_files:
        filename = os.path.basename(f)
        if "_clean" in filename:
            continue
            
        pdb_id = filename.split('.')[0]
        
        if pdb_id not in processed_pdbs:
            if os.path.getsize(f) < MAX_FILE_SIZE_BYTES:
                pdb_files.append(filename)
            else:
                skipped_count += 1

    if skipped_count > 0:
        print(f" Auto-skipped {skipped_count} overly massive PDB complexes to save time.")

    if not pdb_files:
        print(f"\n  All valid files in '{apo_dir}' are already processed. Skipping!")
        return is_first_write, global_cols

    safe_cores = min(8, max(1, os.cpu_count() - 1))
    print(f"\n Processing '{apo_dir}' ({len(pdb_files)} files) with {safe_cores} cores...")
    
    worker_func = partial(process_single_pdb, apo_dir=apo_dir, holo_dir=holo_dir, is_positive_class=is_positive_class)
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=safe_cores) as executor:
        futures = {executor.submit(worker_func, pdb): pdb for pdb in pdb_files}
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(pdb_files), desc="Extracting", unit="file"):
            file_pockets = future.result()
            
            if file_pockets:
                df = pd.DataFrame(file_pockets)
                df.columns = df.columns.astype(str).str.replace(' ', '_').str.replace('(', '').str.replace(')', '').str.replace('-', '_').str.replace(':', '')
                
                if is_first_write:
                    global_cols = df.columns
                    df.to_csv(OUTPUT_CSV, mode='w', header=True, index=False)
                    is_first_write = False
                else:
                    df = df.reindex(columns=global_cols)
                    df.to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
                    
    return is_first_write, global_cols

if __name__ == '__main__':
    processed_pdbs = set()
    first_write = True
    global_columns = None
    
    if os.path.exists(OUTPUT_CSV):
        try:
            existing_df = pd.read_csv(OUTPUT_CSV, usecols=['PDB_ID'])
            processed_pdbs = set(existing_df['PDB_ID'].astype(str).unique())
            first_write = False
            
            global_columns = pd.read_csv(OUTPUT_CSV, nrows=0).columns
            print(f"Found {len(processed_pdbs)} proteins already saved in {OUTPUT_CSV}. Resuming...")
        except Exception as e:
            print(f"Warning: Could not read existing CSV ({e}). Starting fresh.")
            first_write = True
            global_columns = None

    # Step 1: Process Heme-binding proteins (Positives)
    first_write, global_columns = process_and_save_streaming(APO_DIR, HOLO_DIR, True, first_write, global_columns, processed_pdbs)
    
    # Step 2: Process Non-Heme proteins (Negatives)
    first_write, global_columns = process_and_save_streaming(NON_HEME_DIR, NON_HEME_DIR, False, first_write, global_columns, processed_pdbs)

    if os.path.exists(OUTPUT_CSV):
        final_df = pd.read_csv(OUTPUT_CSV)
        print(f"\n-> Successfully finished! {len(final_df)} total pockets are in '{OUTPUT_CSV}'.")
        if 'Target' in final_df.columns:
            print(f"-> Total True Heme-Binding Pockets (Target=1): {final_df['Target'].sum()}")