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

import pandas as pd
import re
import io
import os
import folium
import calendar
from transformers import pipeline
import numpy as np


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
        lambda cell_code: fetch_rsrp_data_directly(cell_code, zte_rsrp_df, huawei_rsrp_df, ref_df)
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
        lambda cell_code: fetch_rsrp_data_directly(cell_code, zte_rsrp_df, huawei_rsrp_df, ref_df)
    )
    if "error" in result:
        return render_template('index.html', error=result["error"])

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

dash_app = create_dash_app(app, latest_result)

# Add Dash app for call drop rate graph at /call-drop-rate-graph
application = DispatcherMiddleware(app.wsgi_app, {
    '/usage-graph': dash_app.server,
    '/call-drop-rate-graph': call_drop_rate_dash_app.server,
    '/hlr-vlr-subbase-graph': hlr_vlr_subbase_dash_app.server,
})

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, application, use_debugger=True, use_reloader=True)
