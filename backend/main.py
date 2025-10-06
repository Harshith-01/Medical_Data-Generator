import os
import json
import uuid
import pandas as pd
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from io import StringIO
from typing import Optional

# --- Basic Setup & Configuration ---
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","https://medical-data-generator-liart.vercel.app"], # Your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSED_FILES = {}

# --- CSV Columns ---
CSV_COLUMNS = [
    'disease', 'symptom_summary', 'gender', 'age', 'ethnicity', 'severity_level', 'duration_days',
    'smoking_status', 'alcohol_consumption', 'family_history_of_disease', 'pre_existing_conditions', 'occupation_exposure',
    'heart_rate', 'respiratory_rate', 'body_temperature', 'blood_pressure_systolic', 'blood_pressure_diastolic', 'oxygen_saturation',
    'wbc_count', 'rbc_count', 'platelet_count', 'hemoglobin', 'blood_glucose_level', 'cholesterol_total', 'creatinine',
    'fever', 'fatigue', 'malaise', 'weight_loss', 'night_sweats', 'chills', 'loss_of_appetite', 'weakness', 'lymph_node_swelling',
    'cough', 'dry_cough', 'productive_cough', 'shortness_of_breath', 'chest_pain', 'wheezing',
    'sore_throat', 'runny_nose', 'nasal_congestion', 'headache', 'dizziness', 'ear_pain', 'post_nasal_drip',
    'confusion', 'seizures', 'loss_of_consciousness', 'insomnia', 'memory_loss', 'difficulty_concentrating',
    'blurred_vision', 'sensitivity_to_light', 'ringing_in_ears',
    'nausea', 'vomiting', 'diarrhea', 'constipation', 'abdominal_pain', 'bloating', 'heartburn', 'indigestion', 'blood_in_stool', 'jaundice',
    'rash', 'hives', 'petechiae', 'itching', 'redness', 'swelling', 'peeling_skin', 'dryness', 'boils_or_blisters', 'lesions_or_sores',
    'hair_loss', 'nail_changes',
    'palpitations', 'chest_tightness',
    'muscle_aches', 'joint_pain', 'leg_swelling', 'visible_veins', 'fainting',
    'painful_urination', 'frequent_urination', 'urgency_to_urinate', 'blood_in_urine', 'discharge', 'menstrual_irregularity', 'pelvic_pain',
    'excessive_thirst', 'excessive_hunger', 'heat_intolerance', 'cold_intolerance', 'rapid_weight_gain', 'slow_healing_wounds',
    'anxiety', 'depression', 'irritability', 'mood_swings',
    'link'
]

# --- Helper Functions ---
def scrape_text_from_url(url: str) -> str:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        texts = [tag.get_text(separator=' ', strip=True) for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])]
        return '\n'.join(texts)
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {e}")

def clean_pre_existing_conditions(conditions):
    # Handle NaN or None
    if isinstance(conditions, (float, int)) and pd.isna(conditions):
        return 'None'
    
    # Handle list/array
    if isinstance(conditions, (list, tuple)):
        return ', '.join(map(str, conditions)) if conditions else 'None'
    
    # Handle string
    if isinstance(conditions, str):
        conditions = conditions.strip()
        return 'None' if conditions in ["[]", "None", "", "nan"] else conditions
    
    # Handle numpy arrays or pandas Series gracefully
    if hasattr(conditions, '__iter__') and not isinstance(conditions, (str, bytes)):
        return ', '.join(map(str, list(conditions))) if len(conditions) > 0 else 'None'
    
    return 'None'

def generate_profiles_with_gemini(disease_name: str, context: str) -> list:
    # Using a standard, reliable model name
    model = genai.GenerativeModel("gemini-2.5-flash")

    # --- REVISED AND SIMPLIFIED PROMPT ---
    prompt = f"""
    You are a meticulous clinical data scientist AI. Your mission is to generate a diverse cohort of 3 clinically plausible, hypothetical patient profiles based **exclusively** on the provided disease context.

    **CRITICAL RULE: AVOIDING EXAMPLE BIAS**
    The `EXAMPLE` is for showing the required JSON structure only. For the `ACTUAL CONTEXT`, you MUST evaluate **every single field** in the `SCHEMA OF ALL POSSIBLE FIELDS` and populate any that are mentioned or logically implied. Your goal is to extract as much relevant data as possible.

    **SCHEMA OF ALL POSSIBLE FIELDS:**
    {str(CSV_COLUMNS)}

    **OUTPUT FORMAT:**
    You MUST output a single, valid JSON array containing exactly 3 patient profile objects. Do not include any other text or markdown.

    ---
    ### GUIDING PRINCIPLES
    1.  **Clinical Diversity:** The 3 profiles MUST be distinct. Vary demographics (`age`, `gender`, `ethnicity`) and `severity_level` ('Mild', 'Moderate', 'Severe').
    2.  **Symptom Coherence:** All data must align with the `severity_level`. A 'Severe' case should have more pronounced symptoms/vitals.
    3.  **Handling Ambiguity:** If the context is qualitative (e.g., "high fever"), generate a plausible number (e.g., `"body_temperature": 39.5`). If not mentioned, use `null`.

    ---
    ### DETAILED FIELD INSTRUCTIONS
    -   **For all symptom columns (e.g., 'fever', 'cough'):** The output value must be a single floating-point number between 0.0 and 1.0, representing the probability of the symptom based on the context and severity. If a symptom is not mentioned, its probability MUST be `0.0`.
    -   **`pre_existing_conditions`:** Output as a JSON array of strings, or `null` if none.

    ---
    ### EXAMPLE (FOR FORMATTING REFERENCE ONLY)
    ```json
    [
      {{
        "disease": "Aqua-fever",
        "symptom_summary": "A 42-year-old female presents with a characteristic blue skin rash and a persistent dry cough.",
        "gender": "Female",
        "age": 42,
        "severity_level": "Moderate",
        "body_temperature": 38.1,
        "rash": 1.0,
        "dry_cough": 0.95,
        "shortness_of_breath": 0.05,
        "chest_pain": 0.0
      }}
    ]
    ```
    ---
    **ACTUAL CONTEXT TO USE:**
    **Disease:** "{disease_name}"
    **Text:**
    {context[:30000]}
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json", "temperature": 0.7},
            safety_settings={'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE', 'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                             'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE', 'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'}
        )
        return json.loads(response.text)
    except Exception as e:
        # Simplified error handling for brevity
        print(f"An unexpected error occurred during Gemini call: {e}")
        if 'response' in locals():
            print("--- Gemini Response Text ---")
            print(response.text)
        raise HTTPException(status_code=500, detail="An error occurred while generating profiles.")

# --- API Endpoints ---
@app.post("/process")
async def process_data(
    disease_name: str = Form(...),
    url: str = Form(...),
    file: UploadFile = File(...)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    try:
        df_base = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse uploaded CSV: {e}")

    scraped_text = scrape_text_from_url(url)
    if not scraped_text:
        raise HTTPException(status_code=400, detail="Could not extract text from the URL.")

    profiles = generate_profiles_with_gemini(disease_name, scraped_text)
    if not profiles:
         raise HTTPException(status_code=500, detail="Failed to generate new profiles.")

    # --- EFFICIENT DATA PROCESSING ---
    # 1. Create DataFrame directly from the AI's JSON output
    df_new = pd.DataFrame(profiles)

    # 2. Add the source link to each new row
    df_new['link'] = url

    # 3. Clean the 'pre_existing_conditions' column (do this only once)
    if 'pre_existing_conditions' in df_new.columns:
        df_new['pre_existing_conditions'] = df_new['pre_existing_conditions'].apply(clean_pre_existing_conditions)

    # 4. Ensure column order matches the base file before concatenation
    df_new = df_new.reindex(columns=df_base.columns)

    # 5. Combine the old and new data
    combined_df = pd.concat([df_base, df_new], ignore_index=True)
    # -----------------------------------

    file_id = str(uuid.uuid4())
    PROCESSED_FILES[file_id] = combined_df.to_csv(index=False)

    return {"message": "Processing complete! Click 'Download Result' to get your file.", "file_id": file_id}

@app.get("/download/{file_id}")
async def download_processed_file(file_id: str):
    if file_id not in PROCESSED_FILES:
        raise HTTPException(status_code=404, detail="File not found or has expired.")

    csv_data = PROCESSED_FILES.pop(file_id)
    response = StreamingResponse(iter([csv_data]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=updated_data_{file_id[:8]}.csv"
    return response

@app.get("/template")
async def download_template():
    df_template = pd.DataFrame(columns=CSV_COLUMNS)
    stream = StringIO()
    df_template.to_csv(stream, index=False)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=template.csv"
    return response

