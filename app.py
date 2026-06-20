import os
import uuid
import shutil
import time
import json
import asyncio
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import lightgbm as lgb
import shap
from scipy.special import expit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from extraction_engine import download_user_pdb, clean_uploaded_pdb, run_fpocket_and_extract
from docking_engine import setup_and_run_vina

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://heme-discover.vercel.app", 
        "https://heme-discover-chaitanyas-projects-e89ad165.vercel.app",             
        
    ],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

MODEL_PATH = 'heme_binder_lightgbm.txt'
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Critical Error: '{MODEL_PATH}' not found. Ensure model is uploaded.")

model = lgb.Booster(model_file=MODEL_PATH)

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

executor = ThreadPoolExecutor(max_workers=2)

def cleanup_workspace(job_dir: str, delay: int = 120):
    time.sleep(delay) 
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
        print(f"Cleaned up workspace: {job_dir}")

def calculate_etd(size_x, size_y, size_z):
    volume = size_x * size_y * size_z
    return int(((volume / 15000) * 45) + 10)

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

class DockingRequest(BaseModel):
    job_id: str
    pdb_id: str
    pockets_data: list[dict]

# --- ENDPOINTS ---

@app.post("/predict_heme_binding")
async def predict_binding(
    background_tasks: BackgroundTasks,
    pdb_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    if not pdb_id and not file:
        raise HTTPException(status_code=400, detail="Must provide either a PDB ID or upload a PDB file.")

    job_id = str(uuid.uuid4())
    job_dir = f"temp_data/{job_id}"
    os.makedirs(f"{job_dir}/static", exist_ok=True)
    os.makedirs(f"{job_dir}/raw", exist_ok=True)
    os.makedirs(f"{job_dir}/docked", exist_ok=True)
    
    try:
        if file:
            effective_pdb_id = file.filename.split('.')[0].upper()
            raw_path = os.path.join(job_dir, f"{effective_pdb_id}_raw.pdb")
            pdb_path = os.path.join(job_dir, "raw", f"{effective_pdb_id}.pdb")
            
            with open(raw_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            clean_uploaded_pdb(raw_path, pdb_path) 
        else:
            effective_pdb_id = pdb_id.upper()
            pdb_path = download_user_pdb(effective_pdb_id, output_dir=os.path.join(job_dir, "raw"))

        df_pockets = run_fpocket_and_extract(effective_pdb_id, pdb_path, output_dir=job_dir)
        
        if df_pockets is None or df_pockets.empty:
            shutil.rmtree(job_dir)
            return {
                "status": "Non-Binder",
                "message": f"No structural cavities detected in {effective_pdb_id}. Likely a Non-Heme Binder."
            }

        ml_features = df_pockets.reindex(columns=EXPECTED_FEATURES, fill_value=0)
        raw_logits = model.predict(ml_features, raw_score=True)
        df_pockets['Binding_Probability'] = expit(raw_logits)
        
        valid_pockets = df_pockets[df_pockets['Binding_Probability'] >= 0.35]
        
        if valid_pockets.empty:
            shutil.rmtree(job_dir)
            return {
                "status": "Non-Binder",
                "message": f"Scanned pockets in {effective_pdb_id}. None passed the 35% confidence threshold."
            }
            
        top_3_pockets = valid_pockets.sort_values(by='Binding_Probability', ascending=False).head(3)
        pockets_list = top_3_pockets.to_dict(orient='records')
        
        best_idx = top_3_pockets.index[0]
        best_pocket = pockets_list[0]
        
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(ml_features)
        pocket_shap_values = shap_values[1][best_idx] if isinstance(shap_values, list) else shap_values[best_idx]
        
        plt.figure(figsize=(10, 6))
        shap.bar_plot(pocket_shap_values, feature_names=EXPECTED_FEATURES, max_display=10, show=False)
        plt.title(f"Why {best_pocket['Pocket_ID']} binds Heme")
        plt.tight_layout()
        
        shap_image_filename = f"{effective_pdb_id}_shap.png"
        shap_image_path = os.path.join(job_dir, "static", shap_image_filename)
        plt.savefig(shap_image_path)
        plt.close()
        
        feature_impacts = list(zip(EXPECTED_FEATURES, pocket_shap_values))
        feature_impacts.sort(key=lambda x: abs(x[1]), reverse=True)
        
        explanation = f"Top Active Site: {best_pocket['Pocket_ID']} with {best_pocket['Binding_Probability']*100:.1f}% confidence.\n\n"
        for feature, impact in feature_impacts[:4]:
            direction = "strongly supported" if impact > 0 else "reduced"
            explanation += f"- The measurement for '{feature}' {direction} binding probability.\n"
        
        res_list = get_residues_in_pocket(job_dir, effective_pdb_id, best_pocket['Pocket_ID'])
        total_etd = sum([calculate_etd(p.get('size_x', 15), p.get('size_y', 15), p.get('size_z', 15)) for p in pockets_list])
        
        background_tasks.add_task(cleanup_workspace, job_dir, 600)
            
        return {
            "status": "Binder",
            "job_id": job_id,
            "protein_id": effective_pdb_id,
            "top_pockets": pockets_list, 
            "top_pocket_confidence": f"{best_pocket['Binding_Probability']*100:.1f}%",
            "explanation": explanation,
            "shap_chart_url": f"/workspace/{job_id}/static/{shap_image_filename}",
            "residues_involved": res_list[:20],
            "docking_etd_seconds": total_etd
        }

    except Exception as e:
        if os.path.exists(job_dir): shutil.rmtree(job_dir)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run_docking")
async def run_docking(request: DockingRequest):
    job_dir = f"temp_data/{request.job_id}"
    docked_dir = os.path.join(job_dir, "docked")
    os.makedirs(docked_dir, exist_ok=True)
    
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Session expired or invalid Job ID.")
        
    async def docking_stream():
        # 1. Yield initial state sequence
        yield json.dumps({"status": "Started", "message": "Initializing Monte Carlo simulations..."}) + "\n"
        await asyncio.sleep(1.2)  # Short artificial pause to display structural setup state smoothly
        
        best_score = float('inf')
        best_result_url = None
        
        # 2. Iterate and yield specific executing pockets sequentially
        for i, pocket in enumerate(request.pockets_data):
            pocket_id = pocket.get("Pocket_ID", f"Pocket_{i+1}")
            yield json.dumps({"status": "Progress", "message": f"Docking on {pocket_id}..."}) + "\n"
            
            loop = asyncio.get_event_loop()
            try:
                vina_results = await loop.run_in_executor(
                    executor, setup_and_run_vina, request.pdb_id, pocket, docked_dir
                )
                
                score = vina_results.get("affinity_score")
                if score is not None and score < best_score:
                    best_score = score
                    safe_filename = urllib.parse.quote(os.path.basename(vina_results['docked_file']))
                    best_result_url = f"/workspace/{request.job_id}/docked/{safe_filename}"
                    
            except Exception as e:
                yield json.dumps({"status": "Error", "message": f"Failed on {pocket_id}: {str(e)}"}) + "\n"
                
        # 3. Yield the final mathematical comparison message requested
        yield json.dumps({"status": "Calculating", "message": "Calculating best result among them..."}) + "\n"
        await asyncio.sleep(1.5)

        # Trigger cleanup task loop execution window
        loop = asyncio.get_event_loop()
        loop.call_later(120, cleanup_workspace, job_dir)

        yield json.dumps({
            "status": "Complete", 
            "message": "All docking completed.",
            "best_affinity_score": best_score,
            "best_docking_result_url": best_result_url
        }) + "\n"

    return StreamingResponse(docking_stream(), media_type="application/x-ndjson")


@app.get("/workspace/{job_id}/{file_type}/{filename}")
def get_workspace_file(job_id: str, file_type: str, filename: str):
    file_path = f"temp_data/{job_id}/{file_type}/{filename}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found or session expired.")