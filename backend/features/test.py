from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from device_subscriber_insights import get_device_subscriber_insights
from datetime import timedelta
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

from usage_graphs import create_dash_app 
from call_drop_rate_dash import create_call_drop_rate_dash_app
from hlr_vlr_subs_dash import create_hlr_vlr_subs_dash_app
from user_location_map import create_location_map
from msisdn_data import get_msisdn_data
from VLR_data import get_user_count
from overview import (
    generate_overall_msisdn_summary, 
    rule_based_pattern_analysis, 
    personalized_recommendations
)
from RSRP_data import (
    fetch_rsrp_data_directly,
    add_calculated_rsrp_columns,
    fetch_rsrp_data_by_site_id,
    filter_and_sort_rsrp_data,
    apply_type_sensitive_filter,
    apply_text_filter,
    apply_numeric_min_filter,
    apply_numeric_max_filter,
    apply_auto_detect_filter,
    apply_wildcard_filter,
    apply_regex_filter
)
from lte_utilization import (
    load_lte_utilization_data,
    get_lte_utilization_by_site_id,
    get_lte_utilization_by_cell_code,
    get_all_lte_utilization_data,
    get_lte_utilization_summary
)

import pandas as pd
import re
import io
import os
import math
import sys
import folium
import calendar
from transformers import pipeline
import numpy as np

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on Earth using Haversine formula"""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c  # Earth radius in km

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static'))

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = "admin12345"
app.permanent_session_lifetime = timedelta(minutes=10)

#auto-detect usage files
def auto_detect_usage_files(data_directory=None):
    data_directory = data_directory or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
    usage_files = {}
    try:
        all_files = os.listdir(data_directory)
    except OSError:
        return usage_files
    for filename in all_files:
        match = re.match(r"USERTD_(\d{4})_(\d{2})\.txt", filename)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            month_name = calendar.month_name[month]
            month_year_key = f"{month_name} {year}"
            usage_files[month_year_key] = {
                'filename': os.path.join(data_directory, filename),
                'year': year,
                'month': month,
                'month_name': month_name
            }
    return usage_files

#monthly data usge
def load_usage_data_with_month():
    df_list = []
    for month_year, file_info in USAGE_FILES.items():
        df = pd.read_csv(file_info['filename'], sep="\t")
        df.columns = [col.upper() for col in df.columns]
        df["MONTH"] = month_year
        df_list.append(df)
    return pd.concat(df_list, ignore_index=True)

# File paths
data_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
REFERENCE_FILE = os.path.join(data_files_dir, "Reference_Data_Cell_Locations_20250403.csv")
TAC_FILE = os.path.join(data_files_dir, "TACD_UPDATED.csv")
INPUT_FILE = os.path.join(data_files_dir, "All_2025-4-2_3.txt")
USAGE_FILES = auto_detect_usage_files() 
VLRD = pd.read_excel(os.path.join(data_files_dir, 'VLRD_Sample.xlsx'))
zte_rsrp_df = pd.read_excel(os.path.join(data_files_dir, 'ZTE RSRP.xlsx'))
huawei_rsrp_df = pd.read_excel(os.path.join(data_files_dir, 'Huawei RSRP.xlsx'))
lte_utilization_df = load_lte_utilization_data()
USERTD = load_usage_data_with_month()

# Load reference data
ref_df = pd.read_csv(REFERENCE_FILE)
tac_df = pd.read_csv(TAC_FILE, low_memory=False)

# Load BART summarization pipeline (load once at startup)
try:
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
except Exception as e:
    summarizer = None
    print(f"[AI Summary] Error loading BART model: {e}")

usage_df = load_usage_data_with_month()

SIM_TYPE_MAPPING = {
    '1': ("ESIM", "PRE"),
    '2': ("USIM", "PRE"),
    '3': ("SIM", "PRE"),
    '7': ("ESIM", "POS"),
    '8': ("USIM", "POS"),
    '9': ("SIM", "POS")
}


latest_result = {}

# Create Dash app for call drop rate graph
call_drop_rate_file = os.path.join(os.path.dirname(__file__), '..', 'data_files', 'Call_Drop_Rate_3G.xls')
call_drop_rate_dash_app = create_call_drop_rate_dash_app(app, call_drop_rate_file)
# Create Dash app for HLR/VLR subscribers graph
hlr_vlr_subbase_file = os.path.join(os.path.dirname(__file__), '..', 'data_files', 'HLR_VLR_Subbase.xls')
hlr_vlr_subbase_dash_app = create_hlr_vlr_subs_dash_app(app, hlr_vlr_subbase_file, url_base_pathname='/hlr-vlr-subbase-graph/')

@app.route('/')
def home():
    insights = get_device_subscriber_insights()
    return render_template('home.html', insights=insights)

@app.route('/index')
def index():
    return render_template('index.html')

@app.before_request
def check_login():
    session.permanent = True
    if not session.get("logged_in"):
        if request.endpoint not in ['login', 'static']:
            return redirect(url_for('login'))

#login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin":
            session.permanent = True
            session["logged_in"] = True
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials, please try again.", "error")
            return render_template('login.html')
    return render_template('login.html')

#logout
@app.route('/logout')
def logout():
    session.pop("logged_in", None)
    return redirect(url_for('login'))

@app.route('/map/<msisdn>')
def show_map(msisdn):  
    result = get_msisdn_data(
        msisdn,
        INPUT_FILE,
        SIM_TYPE_MAPPING,
        ref_df,
        tac_df,
        usage_df,
        USAGE_FILES,
        VLRD,
        lambda site_id: fetch_rsrp_data_by_site_id(site_id, zte_rsrp_df, huawei_rsrp_df),
        lambda cell_code: fetch_rsrp_data_directly(cell_code, zte_rsrp_df, huawei_rsrp_df, ref_df),
        lambda site_id: get_lte_utilization_by_site_id(site_id, lte_utilization_df),
        lambda cell_code: get_lte_utilization_by_cell_code(cell_code, lte_utilization_df)
    )

    if "error" in result:
        map_obj = folium.Map(
            location=[7.8731, 80.7718],  
            zoom_start=7,
            tiles='OpenStreetMap'
        )

        folium.Marker(
            location=[7.8731, 80.7718],
            popup="Error: " + result["error"],
            icon=folium.Icon(color='red', icon='exclamation-sign')
        ).add_to(map_obj)

    else:
        map_obj = create_location_map(result)

    static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static'))
    if not os.path.exists(static_path):
        os.makedirs(static_path)
    
    map_path = os.path.join(static_path, 'temp_map.html')
    map_obj.save(map_path)
    
    return render_template('map_display.html', msisdn=msisdn, result=result)

#search msisdn
@app.route('/search', methods=['POST'])
def search():
    global latest_result
    msisdn = request.form.get("msisdn")
    result = get_msisdn_data(
        msisdn,
        INPUT_FILE,
        SIM_TYPE_MAPPING,
        ref_df,
        tac_df,
        usage_df,
        USAGE_FILES,
        VLRD,
        lambda site_id: fetch_rsrp_data_by_site_id(site_id, zte_rsrp_df, huawei_rsrp_df),
        lambda cell_code: fetch_rsrp_data_directly(cell_code, zte_rsrp_df, huawei_rsrp_df, ref_df),
        lambda site_id: get_lte_utilization_by_site_id(site_id, lte_utilization_df),
        lambda cell_code: get_lte_utilization_by_cell_code(cell_code, lte_utilization_df)
    )
    if "error" in result:
        return render_template('index.html', error=result["error"])
    
    # Store the result and MSISDN in latest_result for other functions to access
    latest_result = result.copy()
    latest_result['MSISDN'] = msisdn

    # Generate AI summary for Overview tab
    ai_summary = generate_overall_msisdn_summary(result, summarizer)

    try:
        map_obj = create_location_map(result)
        static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static'))
        if not os.path.exists(static_path):
            os.makedirs(static_path)
        map_path = os.path.join(static_path, 'temp_map.html')
        map_obj.save(map_path)
        has_map = True
    except Exception as e:
        print(f"Error creating map: {e}")
        has_map = False

    return render_template('index.html', result=result, has_map=has_map, ai_summary=ai_summary)

#user count by site

@app.route('/user_count')
def user_count():
    month = request.args.get('month')
    district = request.args.get('district')
    table_data = get_user_count(month, district, USAGE_FILES, VLRD, ref_df)

    if table_data is None or table_data.empty:
        table_data = pd.DataFrame()  

    return render_template(
        'export_vlr_data.html',
        table_data=table_data.to_dict(orient='records'),
        selected_month=month,
        selected_district=district,
        months=list(USAGE_FILES.keys())
    )


#District Search

@app.route('/user_count/search', methods=['POST'])
def user_count_search():
    month = request.form.get('month')
    district = request.form.get('district')
    table_data = get_user_count(month, district, USAGE_FILES, VLRD, ref_df)
    return render_template(
        'export_vlr_data.html',
        table_data=table_data.to_dict(orient='records'),
        selected_month=month,
        selected_district=district,
        months=list(USAGE_FILES.keys())
    )

#download csv
@app.route('/user_count/download', methods=['POST'])
def download_user_count():
    month = request.form.get('month')
    district = request.form.get('district')
    df = get_user_count(month, district)

    if df.empty:
        return "No data available to download", 204

    csv_stream = io.StringIO()
    df.to_csv(csv_stream, index=False)
    csv_stream.seek(0)

    filename = f"user_count_{month or 'All'}_{district or 'All'}.csv"

    return send_file(
        io.BytesIO(csv_stream.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


@app.route('/rsrp_ranges_direct/<cell_code>', methods=['GET', 'POST'])
def display_rsrp_ranges_direct(cell_code):
    rsrp_data = fetch_rsrp_data_directly(cell_code, zte_rsrp_df, huawei_rsrp_df, ref_df)

    if not rsrp_data:
        flash(f"No RSRP data found for Cell Code {cell_code}", "error")
        return redirect(url_for('index'))

    filters = {}
    sort_by = ''
    sort_order = 'asc'
    
    if request.method == 'POST':
        filters = {
            'Cell_Name': request.form.get('cell_name_filter', ''),
            'Site_ID': request.form.get('site_id_filter', ''),
            'RSRP Range 1 (>-105dBm) %_min': request.form.get('rsrp_range1_min', ''),
            'RSRP Range 1 (>-105dBm) %_max': request.form.get('rsrp_range1_max', ''),
            'RSRP Range 2 (-105~-110dBm) %_min': request.form.get('rsrp_range2_min', ''),
            'RSRP Range 2 (-105~-110dBm) %_max': request.form.get('rsrp_range2_max', ''),
            'RSRP Range 3 (-110~-115dBm) %_min': request.form.get('rsrp_range3_min', ''),
            'RSRP Range 3 (-110~-115dBm) %_max': request.form.get('rsrp_range3_max', ''),
            'RSRP < -115dBm %_min': request.form.get('rsrp_range4_min', ''),
            'RSRP < -115dBm %_max': request.form.get('rsrp_range4_max', '')
        }
        sort_by = request.form.get('sort_by', '')
        sort_order = request.form.get('sort_order', 'asc')
        
        rsrp_data = filter_and_sort_rsrp_data(rsrp_data, filters, sort_by, sort_order)

    return render_template('export_vlr_data.html',
                         table_data=rsrp_data, 
                         is_rsrp_data=True,
                         cell_code=cell_code,
                         current_filters=filters,
                         current_sort_by=sort_by,
                         current_sort_order=sort_order)


@app.route('/rsrp_by_site_id/<site_id>')
def get_rsrp_by_site_id(site_id):
    try:
        rsrp_data = fetch_rsrp_data_by_site_id(site_id, zte_rsrp_df, huawei_rsrp_df)
        if not rsrp_data:
            return jsonify({'error': f'No RSRP data found for Site ID {site_id}'}), 404
        
        return jsonify({
            'site_id': site_id,
            'total_records': len(rsrp_data),
            'data': rsrp_data
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching RSRP data: {str(e)}'}), 500

@app.route('/filter_rsrp_data', methods=['POST'])
def filter_rsrp_data():
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    result = get_msisdn_data(msisdn)
    if "error" in result:
        return jsonify({'error': result["error"]}), 404
    
    cellcode = result.get('Cellcode')
    if not cellcode or cellcode == "Not Found":
        return jsonify({'error': 'No cell code found for this MSISDN'}), 404
    
    rsrp_data = fetch_rsrp_data_directly(cellcode, zte_rsrp_df, huawei_rsrp_df, ref_df)
    if not rsrp_data:
        return jsonify({'error': 'No RSRP data found'}), 404
    
    filters = {
        'Cell_Name': request.form.get('cell_name_filter', ''),
        'Site_ID': request.form.get('site_id_filter', ''),
        'Site_Name': request.form.get('site_name_filter', ''),
        'RSRP Range 1 (>-105dBm) %': request.form.get('rsrp_range1_direct', ''),
        'RSRP Range 2 (-105~-110dBm) %': request.form.get('rsrp_range2_direct', ''),
        'RSRP Range 3 (-110~-115dBm) %': request.form.get('rsrp_range3_direct', ''),
        'RSRP < -115dBm %': request.form.get('rsrp_range4_direct', ''),
        'RSRP Range 1 (>-105dBm) %_min': request.form.get('rsrp_range1_min', ''),
        'RSRP Range 1 (>-105dBm) %_max': request.form.get('rsrp_range1_max', ''),
        'RSRP Range 2 (-105~-110dBm) %_min': request.form.get('rsrp_range2_min', ''),
        'RSRP Range 2 (-105~-110dBm) %_max': request.form.get('rsrp_range2_max', ''),
        'RSRP Range 3 (-110~-115dBm) %_min': request.form.get('rsrp_range3_min', ''),
        'RSRP Range 3 (-110~-115dBm) %_max': request.form.get('rsrp_range3_max', ''),
        'RSRP < -115dBm %_min': request.form.get('rsrp_range4_min', ''),
        'RSRP < -115dBm %_max': request.form.get('rsrp_range4_max', ''),
        'Good Signal (Range 1+2) %_min': request.form.get('good_signal_min', ''),
        'Good Signal (Range 1+2) %_max': request.form.get('good_signal_max', ''),
        'Poor Signal (Range 3+4) %_min': request.form.get('poor_signal_min', ''),
        'Poor Signal (Range 3+4) %_max': request.form.get('poor_signal_max', '')
    }
    sort_by = request.form.get('sort_by', '')
    sort_order = request.form.get('sort_order', 'asc')
    
    filtered_data = filter_and_sort_rsrp_data(rsrp_data, filters, sort_by, sort_order)
    
    return jsonify({
        'data': filtered_data,
        'total_count': len(rsrp_data),
        'filtered_count': len(filtered_data)
    })

@app.route('/filter_common_location_rsrp_data', methods=['POST'])
def filter_common_location_rsrp_data():
    msisdn = request.form.get('msisdn')
    cell_code = request.form.get('cell_code') 
    
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    if not cell_code:
        return jsonify({'error': 'Cell code required'}), 400

    site_id = str(cell_code)[:6]
    
    site_rsrp_data = fetch_rsrp_data_by_site_id(site_id, zte_rsrp_df, huawei_rsrp_df)
    
    if not site_rsrp_data:
        return jsonify({'error': f'No RSRP data found for Cell Code {cell_code}'}), 404

    filters = {
        'Cell_Name': request.form.get('cell_name_filter', ''),
        'Site_ID': request.form.get('site_id_filter', ''),
        'Site_Name': request.form.get('site_name_filter', ''),
        'RSRP Range 1 (>-105dBm) %': request.form.get('rsrp_range1_direct', ''),
        'RSRP Range 2 (-105~-110dBm) %': request.form.get('rsrp_range2_direct', ''),
        'RSRP Range 3 (-110~-115dBm) %': request.form.get('rsrp_range3_direct', ''),
        'RSRP < -115dBm %': request.form.get('rsrp_range4_direct', ''),
        'RSRP Range 1 (>-105dBm) %_min': request.form.get('rsrp_range1_min', ''),
        'RSRP Range 1 (>-105dBm) %_max': request.form.get('rsrp_range1_max', ''),
        'RSRP Range 2 (-105~-110dBm) %_min': request.form.get('rsrp_range2_min', ''),
        'RSRP Range 2 (-105~-110dBm) %_max': request.form.get('rsrp_range2_max', ''),
        'RSRP Range 3 (-110~-115dBm) %_min': request.form.get('rsrp_range3_min', ''),
        'RSRP Range 3 (-110~-115dBm) %_max': request.form.get('rsrp_range3_max', ''),
        'RSRP < -115dBm %_min': request.form.get('rsrp_range4_min', ''),
        'RSRP < -115dBm %_max': request.form.get('rsrp_range4_max', ''),
        'Good Signal (Range 1+2) %_min': request.form.get('good_signal_min', ''),
        'Good Signal (Range 1+2) %_max': request.form.get('good_signal_max', ''),
        'Poor Signal (Range 3+4) %_min': request.form.get('poor_signal_min', ''),
        'Poor Signal (Range 3+4) %_max': request.form.get('poor_signal_max', '')
    }
    sort_by = request.form.get('sort_by', '')
    sort_order = request.form.get('sort_order', 'asc')
    
    filtered_data = filter_and_sort_rsrp_data(site_rsrp_data, filters, sort_by, sort_order)
    
    return jsonify({
        'data': filtered_data,
        'total_count': len(site_rsrp_data),
        'filtered_count': len(filtered_data),
        'cell_code': cell_code,
        'site_id': site_id
    })

@app.route('/filter_common_rsrp_data', methods=['POST'])
def filter_common_rsrp_data():
    """Filter RSRP data for all common locations in the unified table"""
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    # Get the MSISDN data to find common locations
    result = get_msisdn_data(msisdn)
    if "error" in result:
        return jsonify({'error': result["error"]}), 404
    
    common_locations = result.get('Common Cell Locations', [])
    if not common_locations:
        return jsonify({'error': 'No common locations found for this MSISDN'}), 404
    
    # Collect all RSRP data from all common locations
    all_common_rsrp_data = []
    for loc in common_locations:
        loc_rsrp_data = loc.get('RSRP_DATA', [])
        for row in loc_rsrp_data:
            # Just use the row as-is since we're no longer tracking location
            all_common_rsrp_data.append(row.copy())
    
    if not all_common_rsrp_data:
        return jsonify({'error': 'No RSRP data found for common locations'}), 404
    
    # Apply filters
    filters = {
        'Cell_Name': request.form.get('cell_name_filter', ''),
        'Site_ID': request.form.get('site_id_filter', ''),
        'Site_Name': request.form.get('site_name_filter', ''),
        'RSRP Range 1 (>-105dBm) %': request.form.get('rsrp_range1_direct', ''),
        'RSRP Range 2 (-105~-110dBm) %': request.form.get('rsrp_range2_direct', ''),
        'RSRP Range 3 (-110~-115dBm) %': request.form.get('rsrp_range3_direct', ''),
        'RSRP < -115dBm %': request.form.get('rsrp_range4_direct', ''),
        'RSRP Range 1 (>-105dBm) %_min': request.form.get('rsrp_range1_min', ''),
        'RSRP Range 1 (>-105dBm) %_max': request.form.get('rsrp_range1_max', ''),
        'RSRP Range 2 (-105~-110dBm) %_min': request.form.get('rsrp_range2_min', ''),
        'RSRP Range 2 (-105~-110dBm) %_max': request.form.get('rsrp_range2_max', ''),
        'RSRP Range 3 (-110~-115dBm) %_min': request.form.get('rsrp_range3_min', ''),
        'RSRP Range 3 (-110~-115dBm) %_max': request.form.get('rsrp_range3_max', ''),
        'RSRP < -115dBm %_min': request.form.get('rsrp_range4_min', ''),
        'RSRP < -115dBm %_max': request.form.get('rsrp_range4_max', ''),
        'Good Signal (Range 1+2) %_min': request.form.get('good_signal_min', ''),
        'Good Signal (Range 1+2) %_max': request.form.get('good_signal_max', ''),
        'Poor Signal (Range 3+4) %_min': request.form.get('poor_signal_min', ''),
        'Poor Signal (Range 3+4) %_max': request.form.get('poor_signal_max', '')
    }
    
    sort_by = request.form.get('sort_by', '')
    sort_order = request.form.get('sort_order', 'asc')
    
    # Filter and sort the data using the same logic as recent location
    filtered_data = filter_and_sort_rsrp_data(all_common_rsrp_data, filters, sort_by, sort_order)
    
    return jsonify({
        'data': filtered_data,
        'total_count': len(all_common_rsrp_data),
        'filtered_count': len(filtered_data)
    })

@app.route('/ai_overall_summary', methods=['POST'])
def ai_overall_summary():
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    user_data = get_msisdn_data(msisdn)
    if 'error' in user_data:
        return jsonify({'error': user_data['error']}), 404
    summary = generate_overall_msisdn_summary(user_data, summarizer)
    return jsonify({'msisdn': msisdn, 'summary': summary})

# --- 3G Call Drop Rate Data API for JS Plotly Chart ---
@app.route('/call-drop-rate-3g-data')
def call_drop_rate_3g_data():
    from datetime import datetime
    try:
        file_path = os.path.join(data_files_dir, 'Call_Drop_Rate_3G.xls')
        if not os.path.exists(file_path):
            return jsonify({'error': 'Call_Drop_Rate_3G.xls not found'}), 404

        # Try to read sheet 1, fallback to sheet 0 if error
        try:
            df = pd.read_excel(file_path, sheet_name=1)
        except Exception:
            try:
                df = pd.read_excel(file_path, sheet_name=0)
            except Exception as e:
                return jsonify({'error': f'Excel read error: {str(e)}'}), 500

        df = df.rename(columns=lambda x: str(x).strip())
        available_cols = list(df.columns)
        # Robustly detect the date and drop columns
        # Robustly select drop_col
        drop_col = '3G Call Drop Rate'
        if drop_col not in df.columns:
            drop_col = df.columns[-1]  # fallback to last column
        # Robustly select date_col
        if 'Start' in df.columns:
            date_col = 'Start'
        else:
            date_col = df.columns[0]  # fallback to first column

        # Keep original date strings for x-axis
        df = df[df[date_col].notnull()]
        # Save original date strings before conversion
        original_dates = df[date_col].astype(str).tolist()
        # For filtering, convert to datetime (but keep original for x-axis)
        df[date_col + '_dt'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df[df[date_col + '_dt'].notnull()]
        df = df[df[date_col + '_dt'].dt.year >= 2014]
        df = df.sort_values(date_col + '_dt')
        df[drop_col] = df[drop_col].replace({np.nan: None, np.inf: None, -np.inf: None})
        # After filtering/sorting, get the original date strings in the same order
        x = df[date_col].astype(str).tolist()
        y = df[drop_col].tolist()
        # Add a years array for frontend filtering
        years = df[date_col + '_dt'].dt.year.tolist()
        return jsonify({
            "x": x,
            "y": y,
            "years": years,
            "date_col": date_col,
            "drop_col": drop_col,
            "available_columns": available_cols
        })
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# Route for 3G Call Drop Rate Graph HTML page (Plotly/JS visualization)
@app.route('/call-drop-rate-3g-graph')
def call_drop_rate_3g_graph():
    return render_template('call_drop_rate_3g_graph.html')


@app.route('/call_drop_rate_3g_table')
def call_drop_rate_3g_table():
    return render_template('call_drop_rate_3g_table.html')

@app.route('/hlr-vlr-subbase-data')
def hlr_vlr_subbase_data():
    import pandas as pd
    import numpy as np
    from flask import jsonify
    file_path = os.path.join(data_files_dir, 'HLR_VLR_Subbase.xls')
    try:
        df = pd.read_excel(file_path, sheet_name='Daily HLR Subs')
        df = df.rename(columns=lambda x: str(x).strip())
        x_col = df.columns[0]
        x = df[x_col].astype(str).tolist()
        y_series = {col: df[col].replace({np.nan: None, np.inf: None, -np.inf: None}).tolist() for col in df.columns[1:]}
        return jsonify({
            "x": x,
            "y_series": y_series,
            "x_col": x_col,
            "y_cols": list(df.columns[1:])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Route for HLR/VLR Subbase JS-based graph
@app.route('/hlr-vlr-subs-graph')
def hlr_vlr_subs_graph():
    return render_template('hlr_vlr_subs_graph.html')

# LTE Utilization API endpoints
@app.route('/lte-utilization-data')
def lte_utilization_data():
    """Get all LTE utilization data with optional filtering"""
    try:
        # Get query parameters for filtering
        site_id_filter = request.args.get('site_id', '')
        cell_id_filter = request.args.get('cell_id', '')
        district_filter = request.args.get('district', '')
        region_filter = request.args.get('region', '')
        sort_by = request.args.get('sort_by', 'Site ID')
        sort_order = request.args.get('sort_order', 'asc')
        
        # Build filters dictionary
        filters = {}
        if site_id_filter:
            filters['Site ID'] = site_id_filter
        if cell_id_filter:
            filters['Cell ID'] = cell_id_filter
        if district_filter:
            filters['District'] = district_filter
        if region_filter:
            filters['Region'] = region_filter
        
        data = get_all_lte_utilization_data(filters, sort_by, sort_order)
        summary = get_lte_utilization_summary()
        
        return jsonify({
            'data': data,
            'summary': summary,
            'total_count': len(data)
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching LTE utilization data: {str(e)}'}), 500

@app.route('/lte-utilization-by-site/<site_id>')
def lte_utilization_by_site(site_id):
    """Get LTE utilization data for a specific Site ID"""
    try:
        data = get_lte_utilization_by_site_id(site_id, lte_utilization_df)
        
        if not data:
            return jsonify({'error': f'No LTE utilization data found for Site ID {site_id}'}), 404
        
        return jsonify({
            'site_id': site_id,
            'data': data,
            'total_records': len(data)
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching LTE utilization data: {str(e)}'}), 500

@app.route('/lte-utilization-by-cell/<cell_code>')
def lte_utilization_by_cell(cell_code):
    """Get LTE utilization data for a specific Cell Code"""
    try:
        data = get_lte_utilization_by_cell_code(cell_code, lte_utilization_df)
        
        if not data:
            return jsonify({'error': f'No LTE utilization data found for Cell Code {cell_code}'}), 404
        
        return jsonify({
            'cell_code': cell_code,
            'data': data,
            'total_records': len(data)
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching LTE utilization data: {str(e)}'}), 500

@app.route('/filter_lte_utilization_data', methods=['POST'])
def filter_lte_utilization_data():
    """Filter LTE utilization data based on MSISDN"""
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    # Get MSISDN data to find associated site/cell information
    result = get_msisdn_data(msisdn)
    if "error" in result:
        return jsonify({'error': result["error"]}), 404
    
    cellcode = result.get('Cellcode')
    site_id = None
    
    # Extract site ID from cellcode if available
    if cellcode and cellcode != "Not Found":
        site_id = str(cellcode)[:6]  # First 6 characters usually represent site ID
    
    lte_data = []
    
    # Try to get data by site ID first, then by cell code
    if site_id:
        lte_data = get_lte_utilization_by_site_id(site_id, lte_utilization_df)
    
    if not lte_data and cellcode and cellcode != "Not Found":
        lte_data = get_lte_utilization_by_cell_code(cellcode, lte_utilization_df)
    
    if not lte_data:
        return jsonify({'error': 'No LTE utilization data found for this MSISDN'}), 404
    
    return jsonify({
        'msisdn': msisdn,
        'cellcode': cellcode,
        'site_id': site_id,
        'data': lte_data,
        'total_count': len(lte_data)
    })

@app.route('/filter_common_location_lte_data', methods=['POST'])
def filter_common_location_lte_data():
    """Filter LTE utilization data for a specific common location cell code"""
    msisdn = request.form.get('msisdn')
    cell_code = request.form.get('cell_code')
    
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    if not cell_code:
        return jsonify({'error': 'Cell code required'}), 400

    # Extract site ID from cell code
    site_id = str(cell_code)[:6]
    
    # Try to get LTE data by cell code first, then by site ID
    lte_data = []
    try:
        lte_data = get_lte_utilization_by_cell_code(cell_code, lte_utilization_df)
        
        # If no data found by cell code, try by site ID
        if not lte_data:
            lte_data = get_lte_utilization_by_site_id(site_id, lte_utilization_df)
    except Exception as e:
        pass
    
    if not lte_data:
        return jsonify({'error': f'No LTE utilization data found for Cell Code {cell_code}'}), 404

    return jsonify({
        'data': lte_data,
        'total_count': len(lte_data),
        'cell_code': cell_code,
        'site_id': site_id
    })

@app.route('/filter_common_lte_data', methods=['POST'])
def filter_common_lte_data():
    """Filter LTE utilization data for all common locations in the unified view"""
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    # Get the MSISDN data to find common locations
    result = get_msisdn_data(
        msisdn,
        INPUT_FILE,
        SIM_TYPE_MAPPING,
        ref_df,
        tac_df,
        usage_df,
        USAGE_FILES,
        VLRD,
        lambda site_id: fetch_rsrp_data_by_site_id(site_id, zte_rsrp_df, huawei_rsrp_df),
        lambda cell_code: fetch_rsrp_data_directly(cell_code, zte_rsrp_df, huawei_rsrp_df, ref_df),
        lambda site_id: get_lte_utilization_by_site_id(site_id, lte_utilization_df),
        lambda cell_code: get_lte_utilization_by_cell_code(cell_code, lte_utilization_df)
    )
    
    if "error" in result:
        return jsonify({'error': result["error"]}), 404
    
    common_locations = result.get('Common Cell Locations', [])
    if not common_locations:
        return jsonify({'error': 'No common locations found for this MSISDN'}), 404
    
    # Collect all LTE utilization data from all common locations
    all_common_lte_data = []
    for loc in common_locations:
        loc_lte_data = loc.get('LTE_UTIL_DATA', [])
        for row in loc_lte_data:
            # Add location context to each row
            enhanced_row = row.copy()
            enhanced_row['_location_context'] = {
                'cell_code': loc.get('CELL_CODE', 'Unknown'),
                'site_name': loc.get('SITE_NAME', 'Unknown'),
                'district': loc.get('DISTRICT', 'Unknown')
            }
            all_common_lte_data.append(enhanced_row)
    
    if not all_common_lte_data:
        return jsonify({'error': 'No LTE utilization data found for common locations'}), 404
    
    return jsonify({
        'data': all_common_lte_data,
        'total_count': len(all_common_lte_data),
        'locations_count': len(common_locations)
    })

# Route for LTE Utilization table page
@app.route('/lte-utilization-table')
def lte_utilization_table():
    try:
        # Get query parameters for filtering
        site_id_filter = request.args.get('site_id', '')
        cell_id_filter = request.args.get('cell_id', '')
        district_filter = request.args.get('district', '')
        region_filter = request.args.get('region', '')
        sort_by = request.args.get('sort_by', 'Site ID')
        sort_order = request.args.get('sort_order', 'asc')
        
        # Build filters dictionary
        filters = {}
        if site_id_filter:
            filters['Site ID'] = site_id_filter
        if cell_id_filter:
            filters['Cell ID'] = cell_id_filter
        if district_filter:
            filters['District'] = district_filter
        if region_filter:
            filters['Region'] = region_filter
        
        # Get data and summary
        data = get_all_lte_utilization_data(filters, sort_by, sort_order)
        summary = get_lte_utilization_summary()
        
        return render_template('lte_utilization_table.html', 
                             data=data, 
                             summary=summary,
                             total_count=len(data))
    except Exception as e:
        flash(f'Error loading LTE utilization data: {str(e)}', 'error')
        return render_template('lte_utilization_table.html', 
                             data=[], 
                             summary={},
                             total_count=0)

# Route for simple network coverage mapping
# @app.route('/api/get_cell_locations_in_range', methods=['POST'])
# def get_cell_locations_in_range():
#     """Get network performance locations within a specified coordinate range"""
#     def clean_nan_values(obj):
#         """Recursively replace NaN values with None for JSON serialization"""
#         if isinstance(obj, dict):
#             return {k: clean_nan_values(v) for k, v in obj.items()}
#         elif isinstance(obj, list):
#             return [clean_nan_values(item) for item in obj]
#         elif isinstance(obj, float) and (pd.isna(obj) or obj != obj):  # Check for NaN
#             return None
#         else:
#             return obj
    
#     try:
#         data = request.get_json()
#         if not data:
#             return jsonify({'success': False, 'message': 'No data provided'}), 400
        
#         ref_lat = float(data.get('lat', 0))
#         ref_lon = float(data.get('lon', 0))
#         coordinate_range = float(data.get('range', 0.0009))  # Updated default range to 0.0009
        
#         if ref_lat == 0 or ref_lon == 0:
#             return jsonify({'success': False, 'message': 'Invalid coordinates'}), 400
        
#         # Load network performance data
#         data_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
#         performance_file = os.path.join(data_files_dir, 'MobileNetworkPerformance_55432_2025-06-28.csv')
        
#         if not os.path.exists(performance_file):
#             return jsonify({'success': False, 'message': 'Network performance data file not found'}), 404
        
#         # Read network performance data
#         perf_df = pd.read_csv(performance_file, low_memory=False)
        
#         # Convert coordinate columns to numeric
#         perf_df['attr_location_latitude'] = pd.to_numeric(perf_df['attr_location_latitude'], errors='coerce')
#         perf_df['attr_location_longitude'] = pd.to_numeric(perf_df['attr_location_longitude'], errors='coerce')
#         perf_df['attr_location_start_latitude'] = pd.to_numeric(perf_df['attr_location_start_latitude'], errors='coerce')
#         perf_df['attr_location_start_longitude'] = pd.to_numeric(perf_df['attr_location_start_longitude'], errors='coerce')
        
#         # Calculate average coordinates
#         perf_df['avg_lat'] = perf_df[['attr_location_latitude', 'attr_location_start_latitude']].mean(axis=1, skipna=True)
#         perf_df['avg_lon'] = perf_df[['attr_location_longitude', 'attr_location_start_longitude']].mean(axis=1, skipna=True)
        
#         # Remove rows with missing averaged coordinates
#         perf_df = perf_df.dropna(subset=['avg_lat', 'avg_lon'])
        
#         # Filter locations within coordinate range
#         locations_in_range = []
#         min_distance = float('inf')
#         max_distance = 0
        
#         for _, row in perf_df.iterrows():
#             avg_lat = float(row['avg_lat'])
#             avg_lon = float(row['avg_lon'])
            
#             # Check if within coordinate range (+/- 0.0009)
#             if (abs(avg_lat - ref_lat) <= coordinate_range and 
#                 abs(avg_lon - ref_lon) <= coordinate_range):
                
#                 # Calculate actual distance in kilometers
#                 distance_km = calculate_haversine_distance(ref_lat, ref_lon, avg_lat, avg_lon)
                
#                 # Track min/max distances
#                 min_distance = min(min_distance, distance_km)
#                 max_distance = max(max_distance, distance_km)
                
#                 location_data = {
#                     'lat': round(avg_lat, 6),
#                     'lon': round(avg_lon, 6),
#                     'distance_km': round(distance_km, 3),
#                     'operator': str(row.get('attr_sim_operator_common_name', 'Unknown')),
#                     'network_type': str(row.get('attr_network_type', 'Unknown')),
#                     'signal_strength_dbm': row.get('attr_signal_strength_dbm', None),
#                     'download_speed_kbps': row.get('attr_download_speed_kbps', None),
#                     'upload_speed_kbps': row.get('attr_upload_speed_kbps', None),
#                     'ping_latency_ms': row.get('attr_ping_latency_ms', None),
#                     'device_model': str(row.get('attr_device_model', 'Unknown')),
#                     'device_manufacturer': str(row.get('attr_device_manufacturer', 'Unknown')),
#                     'place_name': str(row.get('attr_place_name', 'Unknown')),
#                     'place_locality_type': str(row.get('attr_place_locality_type', 'Unknown')),
#                     'place_region': str(row.get('attr_place_region', 'Unknown')),
#                     'place_subregion': str(row.get('attr_place_subregion', 'Unknown')),
#                     'place_country': str(row.get('attr_place_country', 'Unknown')),
#                     'test_timestamp': str(row.get('ts_result', 'Unknown')),
#                     'server_name': str(row.get('attr_server_name', 'Unknown')),
#                     'server_distance_km': row.get('val_server_distance_km', None),
#                     'packet_loss_percent': row.get('metric_packet_loss_percent', None),
#                     'jitter_ms': row.get('val_jitter_ms', None),
#                     # Original coordinate values for reference
#                     'original_lat': row.get('attr_location_latitude', None),
#                     'original_lon': row.get('attr_location_longitude', None),
#                     'start_lat': row.get('attr_location_start_latitude', None),
#                     'start_lon': row.get('attr_location_start_longitude', None),
#                     'result_id': str(row.get('id_result', 'Unknown'))
#                 }
                
#                 # Clean NaN values in individual location data
#                 location_data = clean_nan_values(location_data)
#                 locations_in_range.append(location_data)
        
#         # Sort by distance
#         locations_in_range.sort(key=lambda x: x['distance_km'])
        
#         # Prepare statistics
#         statistics = {
#             'closest_distance_km': round(min_distance, 3) if min_distance != float('inf') else None,
#             'farthest_distance_km': round(max_distance, 3) if max_distance > 0 else None,
#             'total_locations_found': len(locations_in_range),
#             'coordinate_range_used': coordinate_range,
#             'avg_signal_strength': None,
#             'avg_download_speed': None,
#             'avg_upload_speed': None,
#             'avg_latency': None
#         }
        
#         # Calculate averages for performance metrics
#         if locations_in_range:
#             signal_strengths = [loc['signal_strength_dbm'] for loc in locations_in_range if loc['signal_strength_dbm'] is not None]
#             download_speeds = [loc['download_speed_kbps'] for loc in locations_in_range if loc['download_speed_kbps'] is not None]
#             upload_speeds = [loc['upload_speed_kbps'] for loc in locations_in_range if loc['upload_speed_kbps'] is not None]
#             latencies = [loc['ping_latency_ms'] for loc in locations_in_range if loc['ping_latency_ms'] is not None]
            
#             if signal_strengths:
#                 statistics['avg_signal_strength'] = round(sum(signal_strengths) / len(signal_strengths), 2)
#             if download_speeds:
#                 statistics['avg_download_speed'] = round(sum(download_speeds) / len(download_speeds), 2)
#             if upload_speeds:
#                 statistics['avg_upload_speed'] = round(sum(upload_speeds) / len(upload_speeds), 2)
#             if latencies:
#                 statistics['avg_latency'] = round(sum(latencies) / len(latencies), 2)
        
#         response_data = {
#             'success': True,
#             'locations': locations_in_range,
#             'statistics': statistics,
#             'search_center': {
#                 'lat': round(ref_lat, 6),
#                 'lon': round(ref_lon, 6)
#             },
#             'coordinate_range': coordinate_range,
#             'data_source': 'MobileNetworkPerformance_55432_2025-06-28.csv',
#             'coordinate_method': 'Average of attr_location_latitude + attr_location_start_latitude and attr_location_longitude + attr_location_start_longitude'
#         }
        
#         return jsonify(clean_nan_values(response_data))
        
#     except Exception as e:
#         return jsonify({
#             'success': False, 
#             'message': f'Error fetching network performance locations in range: {str(e)}'
#         }), 500

# @app.route('/api/get_network_coverage', methods=['POST'])
# def get_network_coverage():
#     def clean_nan_values(obj):
#         """Recursively replace NaN values with None for JSON serialization"""
#         if isinstance(obj, dict):
#             return {k: clean_nan_values(v) for k, v in obj.items()}
#         elif isinstance(obj, list):
#             return [clean_nan_values(item) for item in obj]
#         elif isinstance(obj, float) and (pd.isna(obj) or obj != obj):  # Check for NaN
#             return None
#         else:
#             return obj
    
#     try:
#         data = request.get_json()
#         if not data:
#             return jsonify({'success': False, 'message': 'No data provided'}), 400
        
#         ref_lat = float(data.get('lat', 0))
#         ref_lon = float(data.get('lon', 0))
#         search_radius_km = float(data.get('radius_km', 5))  # Default 5km radius
        
#         if ref_lat == 0 or ref_lon == 0:
#             return jsonify({'success': False, 'message': 'Invalid coordinates'}), 400
        
#         # Load performance data
#         data_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
#         performance_file = os.path.join(data_files_dir, 'MobileNetworkPerformance_55432_2025-06-28.csv')
        
#         if not os.path.exists(performance_file):
#             return jsonify({'success': False, 'message': 'Performance data file not found'}), 404
        
#         # Read performance data
#         df = pd.read_csv(performance_file, low_memory=False)
        
#         # Convert coordinates to numeric and calculate averages
#         df['attr_location_latitude'] = pd.to_numeric(df['attr_location_latitude'], errors='coerce')
#         df['attr_location_longitude'] = pd.to_numeric(df['attr_location_longitude'], errors='coerce')
#         df['attr_location_start_latitude'] = pd.to_numeric(df['attr_location_start_latitude'], errors='coerce')
#         df['attr_location_start_longitude'] = pd.to_numeric(df['attr_location_start_longitude'], errors='coerce')
        
#         # Calculate averaged coordinates
#         df['avg_lat'] = df[['attr_location_latitude', 'attr_location_start_latitude']].mean(axis=1, skipna=True)
#         df['avg_lon'] = df[['attr_location_longitude', 'attr_location_start_longitude']].mean(axis=1, skipna=True)
        
#         # Remove rows with missing averaged coordinates
#         df = df.dropna(subset=['avg_lat', 'avg_lon'])
        
#         # Calculate distances and filter within radius
#         coverage_data = []
#         for _, row in df.iterrows():
#             lat = float(row['avg_lat'])
#             lon = float(row['avg_lon'])
#             distance = calculate_haversine_distance(ref_lat, ref_lon, lat, lon)
            
#             if distance <= search_radius_km:
#                 coverage_data.append({
#                     'lat': round(lat, 6),
#                     'lon': round(lon, 6),
#                     'distance_km': round(distance, 3),
#                     'operator': str(row.get('attr_sim_operator_common_name', 'Unknown')),
#                     'network_type': str(row.get('attr_network_type', 'Unknown')),
#                     'signal_strength': row.get('attr_signal_strength_dbm', None),
#                     'download_speed': row.get('attr_download_speed_kbps', None),
#                     'upload_speed': row.get('attr_upload_speed_kbps', None),
#                     'latency': row.get('attr_ping_latency_ms', None)
#                 })
        
#         # Sort by distance
#         coverage_data.sort(key=lambda x: x['distance_km'])
        
#         # Clean NaN values
#         coverage_data = clean_nan_values(coverage_data)
        
#         response_data = {
#             'success': True,
#             'coverage_data': coverage_data,
#             'total_measurements': len(coverage_data),
#             'search_center': {
#                 'lat': round(ref_lat, 6),
#                 'lon': round(ref_lon, 6)
#             },
#             'search_radius_km': search_radius_km,
#             'data_source': 'MobileNetworkPerformance_55432_2025-06-28.csv',
#             'coordinate_method': 'Average of attr_location_latitude + attr_location_start_latitude and attr_location_longitude + attr_location_start_longitude'
#         }
        
#         return jsonify(clean_nan_values(response_data))
        
#     except Exception as e:
#         return jsonify({
#             'success': False, 
#             'message': f'Error fetching network coverage: {str(e)}'
#         }), 500



dash_app = create_dash_app(app, latest_result)

# Add Dash app for call drop rate graph at /call-drop-rate-graph
application = DispatcherMiddleware(app.wsgi_app, {
    '/usage-graph': dash_app.server,
    '/call-drop-rate-graph': call_drop_rate_dash_app.server,
    '/hlr-vlr-subbase-graph': hlr_vlr_subbase_dash_app.server,
})

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, application, use_debugger=True, use_reloader=True)
