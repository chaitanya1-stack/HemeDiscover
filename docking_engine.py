import os
import subprocess

def convert_pdb_to_pdbqt(pdb_id, pdb_path, workspace):
    pdbqt_path = f"{workspace}/{pdb_id}.pdbqt"
    
    if os.path.exists(pdbqt_path):
        os.remove(pdbqt_path)
        
    command = f"obabel {pdb_path} -O {pdbqt_path} -p 7.4 -xr"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"OpenBabel conversion failed: {result.stderr}")
        
    with open(pdbqt_path, 'r') as file:
        lines = file.readlines()
        
    with open(pdbqt_path, 'w') as file:
        for line in lines:
            clean_line = line.strip()
            if clean_line.startswith(("ROOT", "ENDROOT", "BRANCH", "ENDBRANCH", "TORSDOF")):
                continue
            file.write(line)
            
    return pdbqt_path

def setup_and_run_vina(pdb_id, best_pocket, workspace):
    pdb_path = f"{workspace}/{pdb_id}.pdb"
    ligand_file = os.path.abspath("HEME_ligand.pdbqt") 
    
    config_file = f"{workspace}/{pdb_id}_vina_config.txt"
    output_file = f"{workspace}/{pdb_id}_docking_results.pdbqt" # Saves strictly in workspace
    
    receptor_file = convert_pdb_to_pdbqt(pdb_id, pdb_path, workspace)
    
    center_x = best_pocket.get('center_of_mass_x', 0)
    center_y = best_pocket.get('center_of_mass_y', 0)
    center_z = best_pocket.get('center_of_mass_z', 0)
    
    buffer = 10.0 
    size_x = max(best_pocket.get('size_x', 15.0) + buffer, 25.0)
    size_y = max(best_pocket.get('size_y', 15.0) + buffer, 25.0)
    size_z = max(best_pocket.get('size_z', 15.0) + buffer, 25.0)
    
    config_content = f"""receptor = {receptor_file}
ligand = {ligand_file}

center_x = {center_x:.3f}
center_y = {center_y:.3f}
center_z = {center_z:.3f}

size_x = {size_x:.3f}
size_y = {size_y:.3f}
size_z = {size_z:.3f}

exhaustiveness = 8
"""
    with open(config_file, "w") as f:
        f.write(config_content)
        
    command = f"vina --config {config_file} --out {output_file}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Vina Docking failed: {result.stderr}")
        
    return output_file