import streamlit as st
from google.oauth2 import service_account
from google.cloud import bigquery
import pandas as pd

PROJECT_ID = "revel-city-database"

TABLES = {
    "am_rehab_costs": f"{PROJECT_ID}.AcquisitionManagerRehabCalc.AMRehabCalcCosts",
}


@st.cache_resource
def get_client() -> bigquery.Client:
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)


@st.cache_data(ttl=300)
def run_query(query: str) -> pd.DataFrame:
    client = get_client()
    return client.query(query).to_dataframe()
