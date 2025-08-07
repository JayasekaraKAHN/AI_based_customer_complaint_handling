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
import folium
import calendar
import time

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

# Load rule-based summarization (lightweight alternative to BART)
summarizer = None

def get_summarizer():
    """Initialize rule-based summarizer (lightweight alternative to transformers)"""
    global summarizer
    if summarizer is None:
        print("[LOADING] Initializing rule-based summarization system...")
        try:
            # Initialize rule-based summarizer with telecom-specific keywords
            summarizer = {
                'type': 'rule_based',
                'telecom_keywords': {
                    'data': 3, 'usage': 3, 'signal': 2, 'network': 2, 'location': 2,
                    'rsrp': 2, 'lte': 2, 'cell': 2, 'site': 1, '3g': 1, '4g': 1,
                    'coverage': 2, 'quality': 2, 'performance': 2, 'utilization': 2,
                    'tower': 1, 'connection': 1, 'strength': 1, 'mobile': 1
                },
                'loaded': True
            }
            print("[LOADED] Rule-based summarization system initialized successfully")
        except Exception as e:
            summarizer = False  # Mark as failed to avoid repeated attempts
            print(f"[SUMMARIZER] Error initializing rule-based summarizer: {e}")
    return summarizer if summarizer is not False else None

def generate_ai_summary(text, max_length=150):
    """Generate summary using rule-based approach for telecom data"""
    if not text or len(text.strip()) < 50:
        return "Insufficient data for summary"
    
    # Split into sentences
    sentences = text.split('. ')
    if len(sentences) <= 3:
        return text
    
    # Get telecom keywords from summarizer
    summarizer_obj = get_summarizer()
    if not summarizer_obj:
        return text[:max_length] + "..."
    
    telecom_keywords = summarizer_obj.get('telecom_keywords', {})
    
    scored_sentences = []
    
    for i, sentence in enumerate(sentences):
        if len(sentence.strip()) < 10:  # Skip very short sentences
            continue
            
        score = 0
        sentence_lower = sentence.lower()
        
        # Keyword scoring
        for keyword, weight in telecom_keywords.items():
            score += sentence_lower.count(keyword) * weight
        
        # Length bonus (prefer substantial sentences)
        word_count = len(sentence.split())
        if 8 <= word_count <= 25:  # Optimal length range
            score += 2
        elif word_count > 25:
            score += 1
        
        # Position bonus (first and last sentences often important)
        if i == 0 or i == len(sentences) - 1:
            score += 1
        
        # Numbers/statistics bonus (important in telecom data)
        if re.search(r'\d+(?:\.\d+)?(?:%|MB|GB|dBm|Hz)', sentence):
            score += 2
        
        scored_sentences.append((score, i, sentence.strip()))
    
    if not scored_sentences:
        return text[:max_length] + "..."
    
    # Select top 3 sentences
    top_sentences = sorted(scored_sentences, key=lambda x: x[0], reverse=True)[:3]
    
    # Restore original order
    top_sentences.sort(key=lambda x: x[1])
    
    summary = '. '.join([sentence[2] for sentence in top_sentences])
    
    # Ensure proper ending
    if not summary.endswith('.'):
        summary += '.'
    
    # Truncate if too long
    if len(summary) > max_length:
        summary = summary[:max_length-3] + "..."
    
    return summary

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
result_cache_timeout = 300  # Cache results for 5 minutes
ai_summary_cache = {}  # Separate cache for AI summaries
map_cache = {}  # Separate cache for maps
analytics_cache = {}  # Cache for analytics data (RSRP, LTE, etc.)
filter_cache = {}  # Cache for filtered results

def is_cache_valid(msisdn):
    """Check if cached result is still valid"""
    if not latest_result or latest_result.get('MSISDN') != msisdn:
        return False
    
    cache_time = latest_result.get('_cache_time', 0)
    return (time.time() - cache_time) < result_cache_timeout

def cache_result(result, msisdn):
    """Cache result with timestamp"""
    global latest_result
    latest_result = result.copy()
    latest_result['MSISDN'] = msisdn
    latest_result['_cache_time'] = time.time()

def is_ai_cache_valid(msisdn):
    """Check if AI summary cache is valid"""
    if msisdn not in ai_summary_cache:
        return False
    cache_time = ai_summary_cache[msisdn].get('_cache_time', 0)
    return (time.time() - cache_time) < result_cache_timeout

def cache_ai_summary(msisdn, summary):
    """Cache AI summary separately"""
    ai_summary_cache[msisdn] = {
        'summary': summary,
        '_cache_time': time.time()
    }

def is_map_cache_valid(msisdn):
    """Check if map cache is valid"""
    if msisdn not in map_cache:
        return False
    cache_time = map_cache[msisdn].get('_cache_time', 0)
    map_file = map_cache[msisdn].get('map_file')
    # Check if cached and file still exists
    return (time.time() - cache_time) < result_cache_timeout and os.path.exists(map_file)

def cache_map(msisdn, map_file):
    """Cache map file path"""
    map_cache[msisdn] = {
        'map_file': map_file,
        '_cache_time': time.time()
    }

def get_cache_key(msisdn, data_type, cell_code=None):
    """Generate cache key for analytics data"""
    if cell_code:
        return f"{msisdn}_{data_type}_{cell_code}"
    return f"{msisdn}_{data_type}"

def is_analytics_cache_valid(cache_key):
    """Check if analytics cache is valid"""
    if cache_key not in analytics_cache:
        return False
    cache_time = analytics_cache[cache_key].get('_cache_time', 0)
    return (time.time() - cache_time) < result_cache_timeout

def cache_analytics_data(cache_key, data):
    """Cache analytics data"""
    analytics_cache[cache_key] = {
        'data': data,
        '_cache_time': time.time()
    }

def get_cached_analytics_data(cache_key):
    """Retrieve cached analytics data"""
    if is_analytics_cache_valid(cache_key):
        return analytics_cache[cache_key]['data']
    return None

def cleanup_expired_caches():
    """Clean up expired cache entries to prevent memory bloat"""
    current_time = time.time()
    
    # Clean up main result cache
    if latest_result.get('_cache_time', 0) and (current_time - latest_result['_cache_time']) > result_cache_timeout:
        latest_result.clear()
    
    # Clean up AI summary cache
    expired_keys = []
    for msisdn, cache_data in ai_summary_cache.items():
        if (current_time - cache_data.get('_cache_time', 0)) > result_cache_timeout:
            expired_keys.append(msisdn)
    for key in expired_keys:
        del ai_summary_cache[key]
    
    # Clean up map cache
    expired_keys = []
    for msisdn, cache_data in map_cache.items():
        if (current_time - cache_data.get('_cache_time', 0)) > result_cache_timeout:
            expired_keys.append(msisdn)
    for key in expired_keys:
        # Also delete the actual map file
        if 'map_file' in map_cache[key] and os.path.exists(map_cache[key]['map_file']):
            try:
                os.remove(map_cache[key]['map_file'])
            except:
                pass
        del map_cache[key]
    
    # Clean up analytics cache
    expired_keys = []
    for cache_key, cache_data in analytics_cache.items():
        if (current_time - cache_data.get('_cache_time', 0)) > result_cache_timeout:
            expired_keys.append(cache_key)
    for key in expired_keys:
        del analytics_cache[key]
    
    print(f"[CACHE] Cleaned up {len(expired_keys)} expired cache entries")

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
    # Check if this is a detailed view request from overview page
    detailed = request.args.get('detailed')
    msisdn = request.args.get('msisdn')
    
    if detailed and msisdn:
        global latest_result
        # Check if we have data for this MSISDN
        if latest_result and latest_result.get('MSISDN') == msisdn:
            result = latest_result
            # Generate AI summary
            ai_summary = generate_overall_msisdn_summary(result, get_summarizer())
            
            # Create map
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
            
            return render_template('index.html', result=result, has_map=has_map, ai_summary=ai_summary, from_overview=True)
    
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
    # Check if we have a cached map first
    if is_map_cache_valid(msisdn):
        print(f"[MAP] Using cached map for {msisdn}")
        # Read the cached data if available
        if is_cache_valid(msisdn):
            result = latest_result
        else:
            # Need to load basic data for error handling
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
        return render_template('map_display.html', msisdn=msisdn, result=result)
    
    # Generate new map if not cached
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
    
    # Use unique filename for each MSISDN
    map_path = os.path.join(static_path, f'temp_map_{msisdn}.html')
    map_obj.save(map_path)
    
    # Cache the map
    cache_map(msisdn, map_path)
    
    return render_template('map_display.html', msisdn=msisdn, result=result)

#search msisdn
@app.route('/search', methods=['POST'])
def search():
    search_start = time.time()
    global latest_result
    msisdn = request.form.get("msisdn")
    
    print(f"[SEARCH] Starting search for MSISDN: {msisdn}")
    
    # Fast data loading - only essential data
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
    
    # Store the result and MSISDN with caching
    cache_result(result, msisdn)
    
    search_time = time.time() - search_start
    print(f"[SEARCH] Search completed in {search_time:.2f} seconds")
    
    # Redirect to overview page for fast loading
    return redirect(url_for('overview', msisdn=msisdn))

# New overview route with optimized loading
@app.route('/overview/<msisdn>')
def overview(msisdn):
    start_time = time.time()
    global latest_result
    
    # Periodic cache cleanup (every 10th request approximately)
    if int(time.time()) % 10 == 0:
        cleanup_expired_caches()
    
    print(f"[OVERVIEW] Processing overview for MSISDN: {msisdn}")
    
    if not is_cache_valid(msisdn):
        data_start = time.time()
        print(f"[CACHE MISS] Loading data for MSISDN: {msisdn}")
        # If no recent data, fetch it
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
            flash(f"Error loading data for MSISDN {msisdn}: {result['error']}", "error")
            return redirect(url_for('index'))
        
        cache_result(result, msisdn)
        result = latest_result
        print(f"[DATA] Data loading took {time.time() - data_start:.2f} seconds")
    else:
        print(f"[CACHE HIT] Using cached data for MSISDN: {msisdn}")
        result = latest_result

    ai_summary = None
    if is_ai_cache_valid(msisdn):
        print("[AI] Using cached AI summary")
        ai_summary = ai_summary_cache[msisdn]['summary']
    
    has_map = False
    if is_map_cache_valid(msisdn):
        print("[MAP] Using cached map")
        has_map = True
    
    if ai_summary is not None and has_map:
        total_time = time.time() - start_time
        print(f"[OVERVIEW] Fast cached overview served in {total_time:.2f} seconds")
        return render_template('overview.html', result=result, has_map=has_map, ai_summary=ai_summary)
    
    if ai_summary is None:
        ai_start = time.time()
        print("[AI] Generating AI summary...")
        try:
            ai_summary = generate_overall_msisdn_summary(result, get_summarizer())
            cache_ai_summary(msisdn, ai_summary)
            print(f"[AI] AI summary generated in {time.time() - ai_start:.2f} seconds")
        except Exception as e:
            print(f"[AI] Error generating AI summary: {e}")
            ai_summary = "AI summary temporarily unavailable"
    
    if not has_map:
        map_start = time.time()
        print("[MAP] Creating location map...")
        try:
            map_obj = create_location_map(result)
            static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static'))
            if not os.path.exists(static_path):
                os.makedirs(static_path)
            map_path = os.path.join(static_path, f'temp_map_{msisdn}.html')
            map_obj.save(map_path)
            cache_map(msisdn, map_path)
            has_map = True
            print(f"[MAP] Map created in {time.time() - map_start:.2f} seconds")
        except Exception as e:
            print(f"[MAP] Error creating map: {e}")
            has_map = False

    total_time = time.time() - start_time
    print(f"[OVERVIEW] Total overview generation time: {total_time:.2f} seconds")

    return render_template('overview.html', result=result, has_map=has_map, ai_summary=ai_summary)

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
    start_time = time.time()
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    print(f"[RSRP FILTER] Starting RSRP filter for MSISDN: {msisdn}")
    
    # Check analytics cache first
    cache_key = get_cache_key(msisdn, 'rsrp')
    cached_data = get_cached_analytics_data(cache_key)
    
    if cached_data:
        print(f"[RSRP FILTER] Using cached RSRP data for {msisdn}")
        return jsonify({
            'data': cached_data,
            'total_count': len(cached_data),
            'filtered_count': len(cached_data),
            'cached': True
        })
    
    # Use cached MSISDN result if available to avoid reloading
    if not is_cache_valid(msisdn):
        print(f"[RSRP FILTER] Loading MSISDN data for {msisdn}")
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
        cache_result(result, msisdn)
    else:
        print(f"[RSRP FILTER] Using cached MSISDN data for {msisdn}")
        result = latest_result
    
    cellcode = result.get('Cellcode')
    if not cellcode or cellcode == "Not Found":
        return jsonify({'error': 'No cell code found for this MSISDN'}), 404
    
    rsrp_data = fetch_rsrp_data_directly(cellcode, zte_rsrp_df, huawei_rsrp_df, ref_df)
    if not rsrp_data:
        return jsonify({'error': 'No RSRP data found'}), 404
    
    # Cache the raw RSRP data
    cache_analytics_data(cache_key, rsrp_data)
    
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
    
    total_time = time.time() - start_time
    print(f"[RSRP FILTER] RSRP filter completed in {total_time:.2f} seconds")
    
    return jsonify({
        'data': filtered_data,
        'total_count': len(rsrp_data),
        'filtered_count': len(filtered_data)
    })

@app.route('/filter_common_location_rsrp_data', methods=['POST'])
def filter_common_location_rsrp_data():
    start_time = time.time()
    msisdn = request.form.get('msisdn')
    cell_code = request.form.get('cell_code') 
    
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    if not cell_code:
        return jsonify({'error': 'Cell code required'}), 400

    print(f"[COMMON RSRP] Starting common location RSRP filter for {msisdn}, cell: {cell_code}")
    
    # Check cache for this specific cell code
    cache_key = get_cache_key(msisdn, 'common_rsrp', cell_code)
    cached_data = get_cached_analytics_data(cache_key)
    
    if cached_data:
        print(f"[COMMON RSRP] Using cached data for {msisdn}, cell: {cell_code}")
        return jsonify({
            'data': cached_data,
            'total_count': len(cached_data),
            'filtered_count': len(cached_data),
            'cell_code': cell_code,
            'site_id': str(cell_code)[:6],
            'cached': True
        })

    site_id = str(cell_code)[:6]
    
    site_rsrp_data = fetch_rsrp_data_by_site_id(site_id, zte_rsrp_df, huawei_rsrp_df)
    
    if not site_rsrp_data:
        return jsonify({'error': f'No RSRP data found for Cell Code {cell_code}'}), 404

    # Cache the data before filtering
    cache_analytics_data(cache_key, site_rsrp_data)

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
    
    total_time = time.time() - start_time
    print(f"[COMMON RSRP] Common location RSRP filter completed in {total_time:.2f} seconds")
    
    return jsonify({
        'data': filtered_data,
        'total_count': len(site_rsrp_data),
        'filtered_count': len(filtered_data),
        'cell_code': cell_code,
        'site_id': site_id
    })

@app.route('/filter_common_rsrp_data', methods=['POST'])
def filter_common_rsrp_data():
    """Filter RSRP data for all common locations in the unified table with enhanced caching"""
    start_time = time.time()
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    print(f"[COMMON RSRP ALL] Starting unified RSRP filter for {msisdn}")
    
    # Check cache for unified common RSRP data
    cache_key = get_cache_key(msisdn, 'all_common_rsrp')
    cached_data = get_cached_analytics_data(cache_key)
    
    if cached_data:
        print(f"[COMMON RSRP ALL] Using cached unified data for {msisdn}")
        # Apply filters to cached data
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
        
        filtered_data = filter_and_sort_rsrp_data(cached_data, filters, sort_by, sort_order)
        
        total_time = time.time() - start_time
        print(f"[COMMON RSRP ALL] Cached unified filter completed in {total_time:.2f} seconds")
        
        return jsonify({
            'data': filtered_data,
            'total_count': len(cached_data),
            'filtered_count': len(filtered_data),
            'cached': True
        })
    
    # Use cached MSISDN data if available
    if not is_cache_valid(msisdn):
        print(f"[COMMON RSRP ALL] Loading MSISDN data for {msisdn}")
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
        cache_result(result, msisdn)
    else:
        print(f"[COMMON RSRP ALL] Using cached MSISDN data for {msisdn}")
        result = latest_result
    
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
    
    # Cache the unified data
    cache_analytics_data(cache_key, all_common_rsrp_data)
    
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
    
    total_time = time.time() - start_time
    print(f"[COMMON RSRP ALL] Unified filter completed in {total_time:.2f} seconds")
    
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
    
    # Check for cached AI summary first
    if is_ai_cache_valid(msisdn):
        return jsonify({
            'msisdn': msisdn, 
            'summary': ai_summary_cache[msisdn]['summary'],
            'cached': True
        })
    
    # Get user data (should be cached from overview call)
    if not is_cache_valid(msisdn):
        # If not cached, need to load data
        user_data = get_msisdn_data(
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
        if 'error' in user_data:
            return jsonify({'error': user_data['error']}), 404
        cache_result(user_data, msisdn)
    else:
        user_data = latest_result
    
    # Generate AI summary
    try:
        summary = generate_overall_msisdn_summary(user_data, get_summarizer())
        cache_ai_summary(msisdn, summary)
        return jsonify({'msisdn': msisdn, 'summary': summary, 'cached': False})
    except Exception as e:
        print(f"[AI] Error generating summary: {e}")
        return jsonify({'error': 'AI summary generation failed', 'details': str(e)}), 500

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
        df[drop_col] = df[drop_col].replace({pd.NA: None, float('inf'): None, float('-inf'): None})
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
    from flask import jsonify
    file_path = os.path.join(data_files_dir, 'HLR_VLR_Subbase.xls')
    try:
        df = pd.read_excel(file_path, sheet_name='Daily HLR Subs')
        df = df.rename(columns=lambda x: str(x).strip())
        x_col = df.columns[0]
        x = df[x_col].astype(str).tolist()
        y_series = {col: df[col].replace({pd.NA: None, float('inf'): None, float('-inf'): None}).tolist() for col in df.columns[1:]}
        return jsonify({
            "x": x,
            "y_series": y_series,
            "x_col": x_col,
            "y_cols": list(df.columns[1:])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Route for HLR/VLR Subbase
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
    """Filter LTE utilization data based on MSISDN with enhanced caching"""
    start_time = time.time()
    msisdn = request.form.get('msisdn')
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    print(f"[LTE FILTER] Starting LTE filter for MSISDN: {msisdn}")
    
    # Check analytics cache first
    cache_key = get_cache_key(msisdn, 'lte')
    cached_data = get_cached_analytics_data(cache_key)
    
    if cached_data:
        print(f"[LTE FILTER] Using cached LTE data for {msisdn}")
        return jsonify({
            'msisdn': msisdn,
            'data': cached_data,
            'total_count': len(cached_data),
            'cached': True
        })
    
    # Use cached MSISDN result if available to avoid reloading
    if not is_cache_valid(msisdn):
        print(f"[LTE FILTER] Loading MSISDN data for {msisdn}")
        # Get MSISDN data to find associated site/cell information
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
        cache_result(result, msisdn)
    else:
        print(f"[LTE FILTER] Using cached MSISDN data for {msisdn}")
        result = latest_result
    
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
    
    # Cache the LTE data
    cache_analytics_data(cache_key, lte_data)
    
    total_time = time.time() - start_time
    print(f"[LTE FILTER] LTE filter completed in {total_time:.2f} seconds")
    
    return jsonify({
        'msisdn': msisdn,
        'cellcode': cellcode,
        'site_id': site_id,
        'data': lte_data,
        'total_count': len(lte_data)
    })

@app.route('/filter_common_location_lte_data', methods=['POST'])
def filter_common_location_lte_data():
    """Filter LTE utilization data for a specific common location cell code with caching"""
    start_time = time.time()
    msisdn = request.form.get('msisdn')
    cell_code = request.form.get('cell_code')
    
    if not msisdn:
        return jsonify({'error': 'MSISDN required'}), 400
    
    if not cell_code:
        return jsonify({'error': 'Cell code required'}), 400

    print(f"[COMMON LTE] Starting common location LTE filter for {msisdn}, cell: {cell_code}")
    
    # Check cache for this specific cell code
    cache_key = get_cache_key(msisdn, 'common_lte', cell_code)
    cached_data = get_cached_analytics_data(cache_key)
    
    if cached_data:
        print(f"[COMMON LTE] Using cached data for {msisdn}, cell: {cell_code}")
        return jsonify({
            'data': cached_data,
            'total_count': len(cached_data),
            'cell_code': cell_code,
            'site_id': str(cell_code)[:6],
            'cached': True
        })

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
        print(f"[COMMON LTE] Error fetching LTE data: {e}")
        pass
    
    if not lte_data:
        return jsonify({'error': f'No LTE utilization data found for Cell Code {cell_code}'}), 404

    # Cache the data
    cache_analytics_data(cache_key, lte_data)
    
    total_time = time.time() - start_time
    print(f"[COMMON LTE] Common location LTE filter completed in {total_time:.2f} seconds")

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

dash_app = create_dash_app(app, latest_result)

# Add Dash app for call drop rate graph at /call-drop-rate-graph
application = DispatcherMiddleware(app.wsgi_app, {
    '/usage-graph': dash_app.server,
    '/call-drop-rate-graph': call_drop_rate_dash_app.server,
    '/hlr-vlr-subbase-graph': hlr_vlr_subbase_dash_app.server,
})

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, application, use_debugger=True, use_reloader=True)
