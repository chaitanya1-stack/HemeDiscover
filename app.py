import os
import uuid
import shutil
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import lightgbm as lgb
import shap
from scipy.special import expit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from extraction_engine import download_user_pdb, run_fpocket_and_extract_15
from docking_engine import setup_and_run_vina

app = FastAPI()

model = lgb.Booster(model_file='heme_binder_lightgbm.txt')

EXPECTED_FEATURES = [
    'count_HIS', 'count_CYS', 'count_MET', 'count_TYR', 'aliphatic_hydrophobic_count', 
    'aromatic_count', 'propionate_stabilization_score', 'has_CP_motif', 'has_CXXCH_motif', 
    'pocket_flatness_index', 'score', 'druggability_score', 'number_of_alpha_spheres', 
    'total_sasa', 'polar_sasa', 'apolar_sasa', 'volume', 'mean_local_hydrophobic_density', 
    'mean_alpha_sphere_radius', 'mean_alp._sph._solvent_access', 'apolar_alpha_sphere_proportion', 
    'hydrophobicity_score', 'volume_score', 'polarity_score', 'charge_score', 
    'proportion_of_polar_atoms', 'alpha_sphere_density', 'cent._of_mass___alpha_sphere_max_dist', 
    'flexibility'
]

# --- HELPER FUNCTIONS ---

# Added 'delay' parameter. Defaults to 120s (2 minutes)
def cleanup_workspace(job_dir: str, delay: int = 120):
    """Waits 'delay' seconds, then deletes the user's temporary folder."""
    time.sleep(delay) 
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
        print(f"Cleaned up workspace: {job_dir}")

def calculate_etd(size_x, size_y, size_z):
    volume = size_x * size_y * size_z
    etd_seconds = (volume / 15000) * 45
    return int(etd_seconds + 10)

def get_residues_in_pocket(job_dir, pdb_id, pocket_id):
    pocket_num = pocket_id.replace("Pocket", "").strip()
    atm_file = f"{job_dir}/{pdb_id}_out/pockets/pocket{pocket_num}_atm.pdb"
    residues = set()
    if os.path.exists(atm_file):
        with open(atm_file, 'r') as f:
            for line in f:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    res_name = line[17:20].strip()
                    res_seq = line[22:26].strip()
                    residues.add(f"{res_name}{res_seq}")
    return list(residues)

# --- MODELS ---

class PDBRequest(BaseModel):
    pdb_id: str

class DockingRequest(BaseModel):
    job_id: str
    pdb_id: str
    pocket_data: dict

# --- ENDPOINT 1: FAST ML PREDICTION ---

# Added 'background_tasks' to the function signature
@app.post("/predict_heme_binding")
def predict_binding(request: PDBRequest, background_tasks: BackgroundTasks):
    pdb_id = request.pdb_id.upper()
    job_id = str(uuid.uuid4())
    job_dir = f"temp_data/{job_id}"
    os.makedirs(f"{job_dir}/static", exist_ok=True)
    
    try:
        pdb_path = download_user_pdb(pdb_id, output_dir=job_dir)
        df_pockets = run_fpocket_and_extract_15(pdb_id, pdb_path, output_dir=job_dir)
        
        ml_features = df_pockets[EXPECTED_FEATURES].fillna(0)
        raw_logits = model.predict(ml_features)
        df_pockets['Binding_Probability'] = expit(raw_logits)
        
        # LOWERED THRESHOLD: Increased recall to catch Myoglobin (1MBN)
        valid_pockets = df_pockets[df_pockets['Binding_Probability'] >= 0.20]
        
        if valid_pockets.empty:
            shutil.rmtree(job_dir)
            return {
                "status": "Non-Binder",
                "message": f"Scanned 15 pockets in {pdb_id}. None passed threshold. Likely a Non-Heme Binder."
            }
            
        best_pocket = valid_pockets.sort_values(by='Binding_Probability', ascending=False).iloc[0]
        best_idx = best_pocket.name
        
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(ml_features)
        pocket_shap_values = shap_values[1][best_idx] if isinstance(shap_values, list) else shap_values[best_idx]
        
        plt.figure(figsize=(10, 6))
        shap.bar_plot(pocket_shap_values, feature_names=EXPECTED_FEATURES, max_display=10, show=False)
        plt.title(f"Why {best_pocket['Pocket_ID']} binds Heme")
        plt.tight_layout()
        
        shap_image_filename = f"{pdb_id}_shap.png"
        shap_image_path = os.path.join(job_dir, "static", shap_image_filename)
        plt.savefig(shap_image_path)
        plt.close()
        
        feature_impacts = list(zip(EXPECTED_FEATURES, pocket_shap_values))
        feature_impacts.sort(key=lambda x: abs(x[1]), reverse=True)
        
        explanation = f"Protein {pdb_id} is classified as a Heme-Binder. {best_pocket['Pocket_ID']} is the active site with {best_pocket['Binding_Probability']*100:.1f}% confidence.\n\n"
        for feature, impact in feature_impacts[:4]:
            direction = "strongly supported" if impact > 0 else "reduced"
            explanation += f"- The measurement for '{feature}' {direction} binding probability.\n"

        res_list = get_residues_in_pocket(job_dir, pdb_id, best_pocket['Pocket_ID'])
        
        buffer = 10.0
        sz_x = max(best_pocket.get('size_x', 15.0) + buffer, 25.0)
        sz_y = max(best_pocket.get('size_y', 15.0) + buffer, 25.0)
        sz_z = max(best_pocket.get('size_z', 15.0) + buffer, 25.0)
        etd = calculate_etd(sz_x, sz_y, sz_z)
        
        # SCHEDULED 10-MINUTE ORPHAN CLEANUP (600 Seconds)
        background_tasks.add_task(cleanup_workspace, job_dir, 600)
            
        return {
            "status": "Binder",
            "job_id": job_id,
            "protein_id": pdb_id,
            "best_pocket": best_pocket.to_dict(),
            "confidence": f"{best_pocket['Binding_Probability']*100:.1f}%",
            "explanation": explanation,
            "shap_chart_url": f"/workspace/{job_id}/static/{shap_image_filename}",
            "residues_involved": res_list[:20],
            "docking_etd_seconds": etd
        }

    except Exception as e:
        if os.path.exists(job_dir): shutil.rmtree(job_dir)
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT 2: RUN DOCKING ---

@app.post("/run_docking")
def run_docking(request: DockingRequest, background_tasks: BackgroundTasks):
    job_dir = f"temp_data/{request.job_id}"
    
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Session expired or invalid Job ID.")
        
    try:
        docking_file_path = setup_and_run_vina(request.pdb_id, request.pocket_data, workspace=job_dir)
        
        # Schedule cleanup exactly 2 minutes (120 seconds) after docking finishes
        background_tasks.add_task(cleanup_workspace, job_dir, 120)
        
        return {
            "status": "Docking Complete",
            "docking_result_url": f"/workspace/{request.job_id}/result/{request.pdb_id}_docking_results.pdbqt"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT 3: SERVE WORKSPACE FILES ---

@app.get("/workspace/{job_id}/{file_type}/{filename}")
def get_workspace_file(job_id: str, file_type: str, filename: str):
    """Securely serves files from the isolated user workspace."""
    if file_type == "static":
        file_path = f"temp_data/{job_id}/static/{filename}"
    else:
        # All other files (like PDBQT results) sit directly in the job_dir
        file_path = f"temp_data/{job_id}/{filename}"
        
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found or session expired.")