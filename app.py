import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from datetime import datetime

# 📌 Authenticate Google Sheets (Cached)
@st.cache_resource
def authenticate_google_sheets():
    try:
        creds = Credentials.from_service_account_file("elevate-aut-3a9d095759ee.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Authentication error: {e}")
        return None

# 📌 Load Names for Dropdown (Cached)
@st.cache_data
def load_dropdown_names():
    try:
        gc = authenticate_google_sheets()  # Authenticate inside function
        url_sheets = 'https://docs.google.com/spreadsheets/d/1xrGdZ-wUL0xycHyNhsEk0wV1zp7eBDEtraopU3w_LDM/edit?gid=0#gid=0'
        sheet = gc.open_by_url(url_sheets).worksheet('Keys')

        names_df = pd.DataFrame(sheet.get_all_records())

        return names_df['Name WIW'].dropna().unique().tolist() if 'Name WIW' in names_df.columns else ["Default Name"]
        
    except Exception as e:
        st.error(f"⚠️ Error loading names: {e}")
        return ["Default Name"]

# 📌 Load and Process JSON Files
def load_json_files(uploaded_files):
    records = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for uploaded_file in uploaded_files:
        try:
            json_data = json.load(uploaded_file)
            enlighten_bundles = json_data.get('allParticipants', {}).get('enlightenBundles', [])
            
            model_scores = {model['name']: model['score'] for bundle in enlighten_bundles for model in bundle['models']}
            model_scores["file_name"] = uploaded_file.name
            model_scores["timestamp"] = current_time
            records.append(model_scores)
        except Exception as e:
            st.error(f"⚠️ Error processing {uploaded_file.name}: {e}")
    
    return pd.DataFrame(records) if records else pd.DataFrame()

# 📌 Update Google Sheets
def update_google_sheets(df_scores):
    try:
        gc = authenticate_google_sheets()  # Authenticate inside function
        sheet = gc.open_by_url('https://docs.google.com/spreadsheets/d/1RBZ2Yo-EaU3Nph7sfvDA2VWo6XoJuLKoHE-U6LC9X8Y/edit').worksheet('DB')
        existing_data = sheet.get_all_records()
        set_with_dataframe(sheet, df_scores, row=len(existing_data) + 2, include_index=False, include_column_header=False)
        st.success("✅ Data successfully updated in Google Sheets.")
    except Exception as e:
        st.error(f"⚠️ Error updating Google Sheets: {e}")

# 📌 Streamlit UI
st.title("📊 AI call analysis")

# Load Dropdown Names (Optimized)
dropdown_names = load_dropdown_names()

# Upload JSON Files
uploaded_files = st.file_uploader("📂 Upload JSON files", type="json", accept_multiple_files=True)

# Process Files Button
if uploaded_files:
    df_scores = load_json_files(uploaded_files)
    
    if not df_scores.empty:
        st.write("📊 **Loaded Data:**")
        st.dataframe(df_scores)

        # Select a Name from Dropdown
        selected_name = st.selectbox("📌 Select a Name:", dropdown_names)

        if st.button("Update Google Sheets"):
            df_scores["name"] = selected_name
            update_google_sheets(df_scores)