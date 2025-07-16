# device_subscriber_insights.py
"""
Generates Device and Subscriber Insights for the dashboard.
"""
import os
import pandas as pd

def get_device_subscriber_insights(data_dir=None):
    """
    Returns a dictionary with:
      - total_unique_devices (IMEI)
      - total_active_subscribers (MSISDN)
      - average_devices_per_user
      - top_5_device_models
    """
    if data_dir is None:
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
    # Aggregate from all USERTD and All_2025-4-2 files
    usage_files = [f for f in os.listdir(data_dir) if f.startswith('USERTD_') and f.endswith('.txt')]
    session_files = [f for f in os.listdir(data_dir) if f.startswith('All_2025-4-2_') and f.endswith('.txt')]
    usage_df_list = []
    session_df_list = []
    for fname in usage_files:
        df = pd.read_csv(os.path.join(data_dir, fname), sep='\t', dtype={'MSISDN': str})
        usage_df_list.append(df)
    for fname in session_files:
        df = pd.read_csv(os.path.join(data_dir, fname), sep=';', header=None, names=['IMSI','MSISDN','IMEI','Status','Cell','Other'], dtype={'MSISDN': str, 'IMEI': str})
        session_df_list.append(df)
    # Use session files for device/subscriber analysis
    if session_df_list:
        session_df = pd.concat(session_df_list, ignore_index=True)
        total_unique_devices = session_df['IMEI'].nunique()
        total_active_subscribers = session_df['MSISDN'].nunique()
        avg_devices_per_user = round(total_unique_devices / max(1, total_active_subscribers), 2)
        # Top 5 device models (if TACD_UPDATED.csv available)
        tac_file = os.path.join(data_dir, 'TACD_UPDATED.csv')
        top_5_models = []
        if os.path.exists(tac_file):
            tac_df = pd.read_csv(tac_file)
            session_df['TAC'] = session_df['IMEI'].str[:8].astype(str)
            tac_df['tac'] = tac_df['tac'].astype(str)
            model_counts = session_df.merge(tac_df, left_on='TAC', right_on='tac', how='left')['model'].value_counts()
            top_5_models = model_counts.head(5).index.tolist()
        return {
            'total_unique_devices': int(total_unique_devices),
            'total_active_subscribers': int(total_active_subscribers),
            'average_devices_per_user': avg_devices_per_user,
            'top_5_device_models': top_5_models
        }
    return {
        'total_unique_devices': 0,
        'total_active_subscribers': 0,
        'average_devices_per_user': 0,
        'top_5_device_models': []
    }
