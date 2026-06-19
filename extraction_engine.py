import os
import subprocess
import requests
import numpy as np
import pandas as pd

def download_user_pdb(pdb_id, output_dir="temp_data"): 
    """Downloads the PDB file requested by the user into the isolated workspace."""
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{pdb_id}.pdb") # <--- MUST SAY output_dir
    
    if not os.path.exists(filename):
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(filename, "w") as f:
                f.write(response.text)
        else:
            raise FileNotFoundError(f"Could not download PDB {pdb_id}")
    return filename

def run_fpocket_and_extract_15(pdb_id, pdb_path, output_dir="temp_data"):
    """Runs fpocket and extracts pockets, saving them to the isolated workspace."""
    # Run fpocket. It automatically creates a folder named {pdb_id}_out in the same directory as the pdb_path
    subprocess.run(['fpocket', '-f', pdb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    
    # Update paths to look inside the specific output_dir
    info_file = os.path.join(output_dir, f"{pdb_id}_out", f"{pdb_id}_info.txt")
    if not os.path.exists(info_file):
        raise ValueError("fpocket failed to generate pockets.")
        
    with open(info_file, 'r') as f:
        lines = f.readlines()
    
    pockets = []
    curr_pkt = {}
    pockets_extracted = 0
    
    for line in lines:
        line = line.strip()
        if line.startswith("Pocket") and ":" in line and not line.endswith("parameters"):
            if curr_pkt and len(curr_pkt) > 2:
                pockets.append(curr_pkt)
                pockets_extracted += 1
            
            # --- EXTRACT TOP 15 POCKETS ---
            if pockets_extracted >= 50: 
                break
            
            pocket_name = line.split(":")[0].strip()
            pocket_num = pocket_name.replace("Pocket", "").strip()
            
            # Update path for ATM file
            atm_file = os.path.join(output_dir, f"{pdb_id}_out", "pockets", f"pocket{pocket_num}_atm.pdb")
            
            res_counts = {'HIS': 0, 'CYS': 0, 'MET': 0, 'TYR': 0, 'PHE': 0, 'TRP': 0, 'ARG': 0, 'LYS': 0}
            aliphatic_count, aromatic_count = 0, 0
            has_cp_motif, has_cxxch_motif = 0, 0
            
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
                                unique_residues.add((res_name, chain_id, res_seq))
                                if chain_id not in sequence_map:
                                    sequence_map[chain_id] = {}
                                sequence_map[chain_id][res_seq] = res_name
                            except ValueError: continue

                for res_name, _, _ in unique_residues:
                    if res_name in res_counts: res_counts[res_name] += 1
                    if res_name in ['ALA', 'ILE', 'VAL', 'LEU']: aliphatic_count += 1
                    if res_name in ['PHE', 'TYR', 'TRP']: aromatic_count += 1
                        
                for chain, seq_dict in sequence_map.items():
                    seq_nums = sorted(seq_dict.keys())
                    for i in range(len(seq_nums) - 1):
                        if seq_nums[i+1] == seq_nums[i] + 1 and seq_dict[seq_nums[i]] == 'CYS' and seq_dict[seq_nums[i+1]] == 'PRO':
                            has_cp_motif = 1
                    for i in range(len(seq_nums) - 4):
                        if seq_nums[i+4] == seq_nums[i] + 4 and seq_dict[seq_nums[i]] == 'CYS' and seq_dict[seq_nums[i+4]] == 'HIS':
                            has_cxxch_motif = 1

            # Update path for VERT file
            vert_file = os.path.join(output_dir, f"{pdb_id}_out", "pockets", f"pocket{pocket_num}_vert.pqr")
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
            key_clean = parts[0].strip().lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
            if key_clean != "residues":
                try: curr_pkt[key_clean] = float(parts[1].strip())
                except ValueError: curr_pkt[key_clean] = parts[1].strip()

    if curr_pkt and len(curr_pkt) > 2 and pockets_extracted < 15:
        pockets.append(curr_pkt)
            
    df = pd.DataFrame(pockets)
    df.columns = df.columns.astype(str).str.replace(' ', '_').str.replace('(', '').str.replace(')', '').str.replace('-', '_').str.replace(':', '')
    return df