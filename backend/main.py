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
    allow_origins=["http://localhost:3000"], # Or your specific frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSED_FILES = {}

# --- CSV Columns (No Change) ---
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

# --- Helper and Gemini Functions (No Change) ---
def scrape_text_from_url(url: str) -> str:
    """Scrapes textual content from a given URL."""
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        texts = [tag.get_text(separator=' ', strip=True) for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])]
        return '\n'.join(texts)
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {e}")

def generate_profiles_with_gemini(disease_name: str, context: str) -> list:
    """
    Generates patient profiles using Gemini with a robust, example-driven prompt and dedicated JSON mode.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
You are a meticulous clinical data scientist AI. Your primary mission is to generate a diverse cohort of 3 clinically plausible, hypothetical patient profiles.

**CORE MANDATE:**
Base your entire output **exclusively** on the provided `CONTEXT` about the disease. Do not use any outside knowledge.

** CRITICAL RULE: AVOIDING EXAMPLE BIAS**
The `EXAMPLE` section below is **only for showing the required JSON structure and tone**. The specific fields populated in the example (e.g., `fever`, `rash`) are NOT a restrictive list. For the `ACTUAL CONTEXT`, you MUST evaluate **every single field** listed in the `SCHEMA OF ALL POSSIBLE FIELDS` and populate any that are mentioned or logically implied in the text. Your goal is to extract as much relevant data as possible into the full schema, not to mimic the example's limited fields.
    
** SCHEMA OF ALL POSSIBLE FIELDS**
This is the complete list of fields you can populate. Check the context for evidence for each one.
{str(CSV_COLUMNS)}

### **[CRITICAL QUALITY CHECK]**

-   **AVOID LAZY OUTPUTS:** You must diligently fill all relevant fields based on the instructions above.
-   **Excessive `null` values are a failure.** Profiles where common vitals, labs, and symptoms are `null` are incorrect.
-   **Your primary goal is to create complete and plausible profiles.**

**OUTPUT FORMAT:**
You MUST output a single, valid JSON array containing exactly 3 patient profile objects. Do not output any other text, explanations, or markdown formatting (like ```json).

---

### GUIDING PRINCIPLES FOR PROFILE GENERATION

1.  **Clinical Diversity:** The 3 profiles MUST be distinct. Intentionally vary demographics (`age`, `gender`, `ethnicity`) and, most importantly, `severity_level`. Use a logical range of severities (e.g., 'Mild', 'Moderate', 'Severe', 'Asymptomatic' if context supports it).
2.  **Symptom Coherence:** The presence and probability of symptoms, as well as lab/vital values, MUST align logically with the profile's `severity_level`. A 'Severe' case should present with more pronounced or a wider range of symptoms than a 'Mild' case, based on the context.
3.  **Plausible Narratives:** The `symptom_summary` should be a brief, realistic clinical narrative that logically weaves together the key data points of the profile.
4.  **Handling Ambiguity:** If the context mentions a value qualitatively (e.g., "high fever," "elevated WBC count"), generate a clinically plausible number that fits that description (e.g., `"body_temperature": 39.5`, `"wbc_count": 18.5`). If there is absolutely no mention, use `null`.

---

### DETAILED FIELD INSTRUCTIONS

-   **`symptoms` (e.g., `fever`, `cough`):**
    -   Use the format `{{"value": boolean, "probability": float}}`.
    -   The probability MUST reflect how common that symptom is according to the context.
    -   If a symptom is NOT mentioned in the context, its probability MUST be `0.0`.
    -   **Relevant Negatives:** If the context explicitly states a symptom is *absent* or rare (e.g., "cough is uncommon"), set its `value` to `false` and `probability` to a low number (e.g., `0.05`). This is critical data.
-   **`vitals` & `labs`:** Use plausible numbers based on the context and the profile's severity. Otherwise, `null`.
-   **`history` & `risk_factors`:** Only populate fields like `smoking_status` if the context identifies them as relevant risk factors. Otherwise, `null`.

---

    ### EXAMPLE (FOR FORMATTING REFERENCE ONLY)
    **Hypothetical Context:** "Aqua-fever causes a blue skin rash and a dry cough. A low-grade fever is common. Shortness of breath is notably absent."
    **Expected JSON Output Structure:**
    ```json
    [
      {{
        "disease": "Aqua-fever",
        "symptom_summary": "A 42-year-old female presents with a characteristic blue skin rash and a persistent dry cough.",
        "gender": "Female",
        "age": "42",
        "severity_level": "Moderate",
        "body_temperature": 38.1,
        "rash": {{"value": true, "probability": 1.0}},
        "dry_cough": {{"value": true, "probability": 0.95}},
        "shortness_of_breath": {{"value": false, "probability": 0.05}},
        "chest_pain": {{"value": false, "probability": 0.0}}
      }}
    ]
    ```
    (Your final output must contain 3 diverse profiles in the array, using the full schema.)

    ---
    **ACTUAL CONTEXT TO USE:**
    **Disease:** "{disease_name}"
    **Text:**
    {context[:20000]}
    ---
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.6
            },
            safety_settings={
                'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
            }
        )
        
        return json.loads(response.text)

    except json.JSONDecodeError as e:
        print("--- Gemini text that failed JSON parsing ---")
        print(response.text if 'response' in locals() else "Response object not available.")
        print("------------------------------------------")
        raise HTTPException(status_code=500, detail=f"Failed to decode JSON from Gemini response: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred while generating profiles: {e}")

# --- CHANGE: New helper function to clean the pre_existing_conditions column ---
def clean_pre_existing_conditions(conditions):
    """
    Normalizes the 'pre_existing_conditions' field to a consistent, comma-separated string.
    Handles various inconsistent formats like [], ['Condition'], or "['Condition']".
    """
    if pd.isna(conditions) or conditions in ["[]", ""]:
        return "None"
    
    # Try to evaluate the string if it looks like a list
    try:
        # This handles cases like "['Heart disease', 'Diabetes']"
        from ast import literal_eval
        evaluated = literal_eval(conditions)
        if isinstance(evaluated, list):
            return ', '.join(evaluated) if evaluated else "None"
    except (ValueError, SyntaxError):
        # It's not a list-like string, so treat it as a plain string
        pass
    
    # Clean up string if it still has brackets or quotes
    cleaned_conditions = str(conditions).strip("[]'\" ")
    
    return cleaned_conditions if cleaned_conditions else "None"

@app.post("/process")
async def process_data(
    disease_name: str = Form(...),
    url: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Processes data from a URL, generates new patient profiles, cleans the data,
    and appends them to the content of the uploaded CSV file.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    df_base = pd.read_csv(file.file)

    scraped_text = scrape_text_from_url(url)
    if not scraped_text:
        raise HTTPException(status_code=400, detail="Could not extract text from the URL.")
    
    profiles = generate_profiles_with_gemini(disease_name, scraped_text)

    new_rows = []
    for profile in profiles:
        row = {
            col: (item['probability'] if isinstance(item := profile.get(col), dict) and 'probability' in item else item)
            for col in CSV_COLUMNS if col != 'link'
        }
        row['link'] = url
        new_rows.append(row)

    df_new = pd.DataFrame(new_rows)
    
    # --- CHANGE: Apply the cleaning function to the new data ---
    if 'pre_existing_conditions' in df_new.columns:
        df_new['pre_existing_conditions'] = df_new['pre_existing_conditions'].apply(clean_pre_existing_conditions)


    # Ensure columns match perfectly before concatenating
    df_new = df_new.reindex(columns=df_base.columns)

    combined_df = pd.concat([df_base, df_new], ignore_index=True)
    
    # --- CHANGE: Apply the cleaning function to the entire combined DataFrame for full consistency ---
    if 'pre_existing_conditions' in combined_df.columns:
        combined_df['pre_existing_conditions'] = combined_df['pre_existing_conditions'].apply(clean_pre_existing_conditions)


    file_id = str(uuid.uuid4())
    PROCESSED_FILES[file_id] = combined_df.to_csv(index=False)

    return {"message": "Processing complete! Click 'Download Result' to get your file.", "file_id": file_id}


@app.get("/download/{file_id}")
async def download_processed_file(file_id: str):
    """Downloads the processed CSV file."""
    if file_id not in PROCESSED_FILES:
        raise HTTPException(status_code=404, detail="File not found or has expired.")
    
    csv_data = PROCESSED_FILES.pop(file_id) # Use pop to remove after download
    response = StreamingResponse(iter([csv_data]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=updated_data_{file_id[:8]}.csv"
    return response


@app.get("/template")
async def download_template():
    """Serves an empty CSV file with only the required headers."""
    df_template = pd.DataFrame(columns=CSV_COLUMNS)

    stream = StringIO()
    df_template.to_csv(stream, index=False)

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=template.csv"
    return response