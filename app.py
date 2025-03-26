import os
import json
import http.client
import requests
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from datetime import datetime

# 📈 Authenticate Google Sheets (Cached)
@st.cache_resource
def authenticate_google_sheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        google_credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(google_credentials, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Authentication error: {e}")
        return None

# 📈 Load Names for Dropdown (Cached)
@st.cache_data
def load_dropdown_names():
    try:
        gc = authenticate_google_sheets()
        url_sheets = 'https://docs.google.com/spreadsheets/d/1xrGdZ-wUL0xycHyNhsEk0wV1zp7eBDEtraopU3w_LDM/edit?gid=0#gid=0'
        sheet = gc.open_by_url(url_sheets).worksheet('Keys')
        names_df = pd.DataFrame(sheet.get_all_records())
        return names_df['Name WIW'].dropna().unique().tolist() if 'Name WIW' in names_df.columns else ["Default Name"]
    except Exception as e:
        st.error(f"⚠️ Error loading names: {e}")
        return ["Default Name"]

# 📈 Upload Audio to ElevateAI & Store Interaction IDs
def upload_audio_to_elevateai(uploaded_files):
    API_TOKEN = "affd61af-b12e-491f-8499-fdb7988b09e3"
    interaction_ids = []
    interaction_timestamps = {}
    
    if not uploaded_files:
        st.warning("⚠️ No se seleccionaron archivos.")
        return []
    
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Declarar interacción en ElevateAI
        conn = http.client.HTTPSConnection("api.elevateai.com")
        payload = json.dumps({
            "type": "audio",
            "languageTag": "auto",
            "vertical": "default",
            "model": "echo",
            "originalFileName": file_name,
            "includeAiResults": True
        })
        headers = {
            'Content-Type': 'application/json',
            'X-API-Token': API_TOKEN
        }
        conn.request("POST", "/v1/interactions", body=payload, headers=headers)
        res = conn.getresponse()
        data = res.read()
        response_json = json.loads(data.decode("utf-8"))
        interaction_id = response_json.get("interactionIdentifier")
        
        if interaction_id:
            interaction_ids.append(interaction_id)
            interaction_timestamps[interaction_id] = upload_time
            st.success(f"✅ Interacción declarada con ID: {interaction_id} ({file_name})")
            
            # Subir el archivo de audio
            URL_UPLOAD = f"https://api.elevateai.com/v1/interactions/{interaction_id}/upload"
            files = {f"filename.{file_name.split('.')[-1]}": (file_name, uploaded_file, "application/octet-stream")}
            headers_upload = {'X-API-Token': API_TOKEN}
            response_upload = requests.post(URL_UPLOAD, headers=headers_upload, files=files)
            st.info(f"Subida de {file_name}: {response_upload.status_code}, {response_upload.text}")
        else:
            st.error("⚠️ Error: No se pudo obtener el interactionIdentifier.")
    
    return interaction_ids

# 📈 Retrieve AI Analysis from ElevateAI
def fetch_ai_results(interaction_ids):
    API_TOKEN = "affd61af-b12e-491f-8499-fdb7988b09e3"
    all_records = []
    
    if not interaction_ids:
        st.warning("No hay interaction_ids almacenados. Asegúrate de subir audios primero.")
        return pd.DataFrame()
    
    for interaction_id in interaction_ids:
        conn = http.client.HTTPSConnection("api.elevateai.com")
        headers = {
            'X-API-Token': API_TOKEN,
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        conn.request("GET", f"/v1/interactions/{interaction_id}/ai", headers=headers)
        res = conn.getresponse()
        data_scores = res.read()
        
        try:
            json_data = json.loads(data_scores.decode("utf-8"))
            enlighten_bundles = json_data.get('allParticipants', {}).get('enlightenBundles', [])
            model_scores = {model['name']: model['score'] for bundle in enlighten_bundles for model in bundle['models']}
            model_scores["interaction_id"] = interaction_id
            model_scores["Fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            all_records.append(model_scores)
        except json.JSONDecodeError:
            st.error("⚠️ Error al decodificar la respuesta JSON de ElevateAI.")
    
    return pd.DataFrame(all_records) if all_records else pd.DataFrame()

# 📈 Update Google Sheets
def update_google_sheets(df_scores):
    try:
        gc = authenticate_google_sheets()
        sheet = gc.open_by_url('https://docs.google.com/spreadsheets/d/1RBZ2Yo-EaU3Nph7sfvDA2VWo6XoJuLKoHE-U6LC9X8Y/edit').worksheet('DB')
        existing_data = sheet.get_all_records()
        set_with_dataframe(sheet, df_scores, row=len(existing_data) + 2, include_index=False, include_column_header=False)
        st.success("✅ Data successfully updated in Google Sheets.")
    except Exception as e:
        st.error(f"⚠️ Error updating Google Sheets: {e}")

# 📈 Streamlit UI
st.title("🎙️ AI Audio Processor")

dropdown_names = load_dropdown_names()
if "df_scores" not in st.session_state:
    st.session_state["df_scores"] = pd.DataFrame()

uploaded_files = st.file_uploader("Upload audio files", type=["wav", "mp3", "ogg"], accept_multiple_files=True)
if st.button("📤 Upload files"):
    interaction_ids = upload_audio_to_elevateai(uploaded_files)
    st.session_state["interaction_ids"] = interaction_ids

if "interaction_ids" in st.session_state and st.session_state["interaction_ids"]:
    if st.button("🔍 Evaluar Interacciones"):
        st.session_state["df_scores"] = fetch_ai_results(st.session_state["interaction_ids"])
    
    if not st.session_state["df_scores"].empty:
        selected_name = st.selectbox("📌 Selecciona un agente:", dropdown_names)
        st.session_state["df_scores"]["Agente"] = selected_name
        st.dataframe(st.session_state["df_scores"])
        if st.button("Upload to Google Sheets"):
            update_google_sheets(st.session_state["df_scores"])