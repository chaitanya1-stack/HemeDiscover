import os
import glob
import subprocess
import math
import numpy as np
import pandas as pd
import concurrent.futures
from functools import partial
from tqdm import tqdm

# Directories
HEME_DIR = "../data_fetch/heme_proteins"
NON_HEME_DIR = "../data_fetch/non_heme_proteins"
OUTPUT_CSV = "labeled_pocket_features.csv"

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

def process_single_pdb(pdb_path, data_dir, is_positive_class):
    pdb_id = os.path.basename(pdb_path).split('.')[0]
    hem_centroid = get_hem_centroid(pdb_path) if is_positive_class else None
        
    try:
        subprocess.run(['fpocket', '-f', pdb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []
    
    info_file = os.path.join(data_dir, f"{pdb_id}_out", f"{pdb_id}_info.txt")
    
    if not os.path.exists(info_file):
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
            if pockets_extracted >= 5: 
                break
            
            pocket_name = line.split(":")[0].strip()
            pocket_num = pocket_name.replace("Pocket", "").strip()
            
            # ---------------------------------------------------------
            # ADVANCED BIOLOGICAL FEATURE EXTRACTION (Based on Literature)
            # ---------------------------------------------------------
            atm_file = os.path.join(data_dir, f"{pdb_id}_out", "pockets", f"pocket{pocket_num}_atm.pdb")
            
            # Categories based on Rathod et al. & Seki et al.
            res_counts = {'HIS': 0, 'CYS': 0, 'MET': 0, 'TYR': 0, 'PHE': 0, 'TRP': 0, 'ARG': 0, 'LYS': 0}
            aliphatic_count = 0
            aromatic_count = 0
            
            has_cp_motif = 0
            has_cxxch_motif = 0
            
            if os.path.exists(atm_file):
                unique_residues = set()
                sequence_map = {} # Maps chain_id -> {res_seq: res_name}
                
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

                # 1. Tally Specific Amino Acids
                for res_name, _, _ in unique_residues:
                    if res_name in res_counts:
                        res_counts[res_name] += 1
                    if res_name in ['ALA', 'ILE', 'VAL', 'LEU']:
                        aliphatic_count += 1
                    if res_name in ['PHE', 'TYR', 'TRP']:
                        aromatic_count += 1
                        
                # 2. Sequential Motif Detection (CP and CXXCH)
                for chain, seq_dict in sequence_map.items():
                    seq_nums = sorted(seq_dict.keys())
                    for i in range(len(seq_nums) - 1):
                        # Check CP Motif (CYS followed immediately by PRO)
                        if seq_nums[i+1] == seq_nums[i] + 1:
                            if seq_dict[seq_nums[i]] == 'CYS' and seq_dict[seq_nums[i+1]] == 'PRO':
                                has_cp_motif = 1
                    for i in range(len(seq_nums) - 4):
                        # Check CXXCH Motif
                        if seq_nums[i+4] == seq_nums[i] + 4:
                            if seq_dict[seq_nums[i]] == 'CYS' and seq_dict[seq_nums[i+4]] == 'HIS':
                                has_cxxch_motif = 1

            # 3. Spatial Geometry & Asymmetry (PCA of Alpha Spheres)
            vert_file = os.path.join(data_dir, f"{pdb_id}_out", "pockets", f"pocket{pocket_num}_vert.pqr")
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
                
                # Calculate Covariance Matrix to find 3D principal axes
                if len(px) >= 3:
                    coords = np.vstack((px, py, pz)).T
                    cov_mat = np.cov(coords, rowvar=False)
                    try:
                        eigenvalues, _ = np.linalg.eigh(cov_mat)
                        eigenvalues = np.sort(eigenvalues)[::-1] # Sort descending
                        # Flatness Index: (Length * Width) / Depth^2
                        if eigenvalues[2] > 0.001:
                            pocket_flatness = (eigenvalues[0] * eigenvalues[1]) / (eigenvalues[2] ** 2)
                    except Exception: pass

            # Compile all features
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

    # ---------------------------------------------------------
    # SMART TARGET LABELING (Distance + Geometry)
    # ---------------------------------------------------------
    if is_positive_class and hem_centroid and protein_pockets:
        best_idx, best_comp = -1, -float('inf')
        for i, pkt in enumerate(protein_pockets):
            x, y, z = pkt.get('center_of_mass_x'), pkt.get('center_of_mass_y'), pkt.get('center_of_mass_z')
            if x is not None and y is not None and z is not None:
                dist = calculate_distance(hem_centroid, (x, y, z))
                if dist < 12.0:
                    score = float(pkt.get('score', 0))
                    volume = float(pkt.get('volume', 0))
                    # Composite score favors high fpocket score, large volume, and close distance
                    comp = (score * 50) + (volume * 0.1) - (dist * 10)
                    if comp > best_comp:
                        best_comp, best_idx = comp, i
        if best_idx != -1: 
            protein_pockets[best_idx]['Target'] = 1
            
    return protein_pockets

def process_and_save_streaming(data_dir, is_positive_class, is_first_write, global_cols):
    pdb_files = glob.glob(os.path.join(data_dir, "*.pdb"))
    if not pdb_files:
        return is_first_write, global_cols

    safe_cores = max(1, os.cpu_count() - 2)
    print(f"\nProcessing '{data_dir}' (Parallel + Live Saving) with {safe_cores} cores...")
    
    worker_func = partial(process_single_pdb, data_dir=data_dir, is_positive_class=is_positive_class)
    
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
    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)
        
    first_write = True
    global_columns = None
    
    first_write, global_columns = process_and_save_streaming(HEME_DIR, True, first_write, global_columns)
    first_write, global_columns = process_and_save_streaming(NON_HEME_DIR, False, first_write, global_columns)

    if os.path.exists(OUTPUT_CSV):
        final_df = pd.read_csv(OUTPUT_CSV)
        print(f"\n-> Successfully saved {len(final_df)} total pockets to '{OUTPUT_CSV}'.")
        if 'Target' in final_df.columns:
            print(f"-> Total True Heme-Binding Pockets (Target=1): {final_df['Target'].sum()}")