import pandas as pd
import os
from flask import request, jsonify

# Global variables for RSRP data
zte_rsrp_df = None
huawei_rsrp_df = None

def initialize_rsrp_data():
    global zte_rsrp_df, huawei_rsrp_df
    
    try:
        # Get the data files directory path relative to current file location
        data_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
        
        # Load ZTE and Huawei RSRP data
        zte_rsrp_df = pd.read_excel(os.path.join(data_files_dir, 'ZTE RSRP.xlsx'))
        huawei_rsrp_df = pd.read_excel(os.path.join(data_files_dir, 'Huawei RSRP.xlsx'))
        
        print("ZTE RSRP Columns:", zte_rsrp_df.columns)
        print("Huawei RSRP Columns:", huawei_rsrp_df.columns)
        
        return True
    except Exception as e:
        print(f"Error loading RSRP data: {e}")
        return False

def fetch_rsrp_data_directly(cell_code):

    global zte_rsrp_df, huawei_rsrp_df
    
    if zte_rsrp_df is None or huawei_rsrp_df is None:
        return []
    
    # Extract the site ID (first 6 characters of cell code)
    site_id = str(cell_code)[:6]
    
    # Filter both datasets
    zte_filtered = zte_rsrp_df[zte_rsrp_df['Site_ID'].astype(str) == site_id]
    huawei_filtered = huawei_rsrp_df[huawei_rsrp_df['Site_ID'].astype(str) == site_id]
    
    if zte_filtered.empty and huawei_filtered.empty:
        return []
    
    site_info = []
    
    # Process ZTE data
    for _, rsrp_row in zte_filtered.iterrows():
        site_info.append({
            'Site_Name': rsrp_row['Site Name'],
            'Cell_Name': rsrp_row['Cell Name'],
            'Site_ID': rsrp_row['Site_ID'],
            'RSRP Range 1 (>-105dBm) %': round(float(rsrp_row['RSRP Range 1 (>-105dBm) %']), 2),
            'RSRP Range 2 (-105~-110dBm) %': round(float(rsrp_row['RSRP Range 2 (-105~-110dBm) %']), 2),
            'RSRP Range 3 (-110~-115dBm) %': round(float(rsrp_row['RSRP Range 3 (-110~-115dBm) %']), 2),
            'RSRP < -115dBm %': round(float(rsrp_row['RSRP < -115dBm']), 2)
        })
    
    # Process Huawei data
    for _, rsrp_row in huawei_filtered.iterrows():
        site_info.append({
            'Site_Name': rsrp_row['Site Name'],
            'Cell_Name': rsrp_row['Cell Name'],
            'Site_ID': rsrp_row['Site_ID'],
            'RSRP Range 1 (>-105dBm) %': round(float(rsrp_row['RSRP Range 1 (>-105dBm) %']), 2),
            'RSRP Range 2 (-105~-110dBm) %': round(float(rsrp_row['RSRP Range 2 (-105~-110dBm) %']), 2),
            'RSRP Range 3 (-110~-115dBm) %': round(float(rsrp_row['RSRP Range 3 (-110~-115dBm) %']), 2),
            'RSRP < -115dBm %': round(float(rsrp_row['RSRP < -115dBm']), 2)
        })

    return site_info

def fetch_rsrp_data_by_site_id(site_id):

    global zte_rsrp_df, huawei_rsrp_df
    
    if zte_rsrp_df is None or huawei_rsrp_df is None:
        return []
    
    # Ensure site_id is a string and get first 6 characters
    site_id_str = str(site_id)[:6]
    
    # Filter both datasets by Site_ID
    zte_filtered = zte_rsrp_df[zte_rsrp_df['Site_ID'].astype(str) == site_id_str]
    huawei_filtered = huawei_rsrp_df[huawei_rsrp_df['Site_ID'].astype(str) == site_id_str]
    
    if zte_filtered.empty and huawei_filtered.empty:
        return []
    
    site_info = []
    
    # Process ZTE data
    for _, rsrp_row in zte_filtered.iterrows():
        site_info.append({
            'Site_Name': rsrp_row['Site Name'],
            'Cell_Name': rsrp_row['Cell Name'],
            'Site_ID': rsrp_row['Site_ID'],
            'RSRP Range 1 (>-105dBm) %': round(float(rsrp_row['RSRP Range 1 (>-105dBm) %']) * 100, 2),
            'RSRP Range 2 (-105~-110dBm) %': round(float(rsrp_row['RSRP Range 2 (-105~-110dBm) %']) * 100, 2),
            'RSRP Range 3 (-110~-115dBm) %': round(float(rsrp_row['RSRP Range 3 (-110~-115dBm) %']) * 100, 2),
            'RSRP < -115dBm %': round(float(rsrp_row['RSRP < -115dBm']) * 100, 2),
            'Source': 'ZTE'
        })
    
    # Process Huawei data
    for _, rsrp_row in huawei_filtered.iterrows():
        site_info.append({
            'Site_Name': rsrp_row['Site Name'],
            'Cell_Name': rsrp_row['Cell Name'],
            'Site_ID': rsrp_row['Site_ID'],
            'RSRP Range 1 (>-105dBm) %': round(float(rsrp_row['RSRP Range 1 (>-105dBm) %']), 2),
            'RSRP Range 2 (-105~-110dBm) %': round(float(rsrp_row['RSRP Range 2 (-105~-110dBm) %']), 2),
            'RSRP Range 3 (-110~-115dBm) %': round(float(rsrp_row['RSRP Range 3 (-110~-115dBm) %']), 2),
            'RSRP < -115dBm %': round(float(rsrp_row['RSRP < -115dBm']), 2),
            'Source': 'Huawei'
        })

    return site_info

def filter_and_sort_rsrp_data(rsrp_data, filters=None, sort_by=None, sort_order='asc'):
    if not rsrp_data:
        return []
    
    filtered_data = rsrp_data.copy()
    
    if filters:
        for key, value in filters.items():
            if value and str(value).strip():
                filtered_data = apply_type_sensitive_filter(filtered_data, key, value)
    
    # Apply sorting
    if sort_by and sort_by in ['Cell_Name', 'Site_ID', 'Site_Name', 'RSRP Range 1 (>-105dBm) %', 'RSRP Range 2 (-105~-110dBm) %',
                               'RSRP Range 3 (-110~-115dBm) %', 'RSRP < -115dBm %']:
        try:
            is_numeric = sort_by in ['RSRP Range 1 (>-105dBm) %', 'RSRP Range 2 (-105~-110dBm) %',
                                   'RSRP Range 3 (-110~-115dBm) %', 'RSRP < -115dBm %']
            
            if is_numeric:
                filtered_data.sort(
                    key=lambda x: float(x.get(sort_by, 0)),
                    reverse=(sort_order == 'desc')
                )
            else:
                filtered_data.sort(
                    key=lambda x: str(x.get(sort_by, '')).lower(),
                    reverse=(sort_order == 'desc')
                )
        except (ValueError, TypeError):
            pass 
    
    return filtered_data

def apply_type_sensitive_filter(data, filter_key, filter_value):
    value_str = str(filter_value).strip()
    
    # Text-based filters for string columns
    if filter_key in ['Cell_Name', 'Site_ID', 'Site_Name']:
        return apply_text_filter(data, filter_key, value_str)
    
    # Range filters for numeric columns
    elif filter_key.endswith('_min'):
        return apply_numeric_min_filter(data, filter_key, value_str)
    elif filter_key.endswith('_max'):
        return apply_numeric_max_filter(data, filter_key, value_str)
    
    # Auto-detect filter type for direct column filters
    else:
        return apply_auto_detect_filter(data, filter_key, value_str)

def apply_text_filter(data, column, value):

    # Exact match filter (=value)
    if value.startswith('='):
        exact_value = value[1:]
        return [row for row in data if str(row.get(column, '')).lower() == exact_value.lower()]
    
    # Not equal filter (!=value)
    elif value.startswith('!='):
        not_value = value[2:]
        return [row for row in data if str(row.get(column, '')).lower() != not_value.lower()]
    
    # Regex filter (/pattern/)
    elif value.startswith('/') and value.endswith('/'):
        import re
        pattern = value[1:-1]
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            return [row for row in data if regex.search(str(row.get(column, '')))]
        except re.error:
            return data
    
    # Wildcard filter (* or %)
    elif '*' in value or '%' in value:
        import re
        # Convert wildcards to regex
        pattern = value.replace('*', '.*').replace('%', '.*')
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            return [row for row in data if regex.search(str(row.get(column, '')))]
        except re.error:
            return data
    
    # Default: contains filter
    else:
        return [row for row in data if value.lower() in str(row.get(column, '')).lower()]

def apply_numeric_min_filter(data, filter_key, value):
    try:
        min_value = float(value)
        # Remove '_min' suffix to get the actual column name
        column = filter_key.replace('_min', '')
        return [row for row in data if float(row.get(column, 0)) >= min_value]
    except (ValueError, TypeError):
        return data

def apply_numeric_max_filter(data, filter_key, value):
    try:
        max_value = float(value)
        # Remove '_max' suffix to get the actual column name
        column = filter_key.replace('_max', '')
        return [row for row in data if float(row.get(column, 0)) <= max_value]
    except (ValueError, TypeError):
        return data

def apply_auto_detect_filter(data, column, value):
    # Split by commas for multiple filters
    if ',' in value:
        filters = [f.strip() for f in value.split(',')]
        for filter_val in filters:
            data = apply_single_auto_filter(data, column, filter_val)
        return data
    else:
        return apply_single_auto_filter(data, column, value)

def apply_single_auto_filter(data, column, value):
    value = value.strip()
    
    # Operator-based filters
    if value.startswith('>='):
        return apply_operator_filter(data, column, value[2:].strip(), '>=')
    elif value.startswith('<='):
        return apply_operator_filter(data, column, value[2:].strip(), '<=')
    elif value.startswith('>'):
        return apply_operator_filter(data, column, value[1:].strip(), '>')
    elif value.startswith('<'):
        return apply_operator_filter(data, column, value[1:].strip(), '<')
    elif value.startswith('='):
        return apply_operator_filter(data, column, value[1:].strip(), '=')
    elif value.startswith('!='):
        return apply_operator_filter(data, column, value[2:].strip(), '!=')
    
    # Range filter (min-max)
    elif '-' in value and not value.startswith('-'):
        parts = value.split('-', 1)
        if len(parts) == 2:
            try:
                min_val = float(parts[0].strip())
                max_val = float(parts[1].strip())
                return apply_range_filter(data, column, min_val, max_val)
            except ValueError:
                pass
    
    # Wildcard patterns
    elif '*' in value or '%' in value:
        return apply_wildcard_filter(data, column, value)
    
    # Regex patterns
    elif value.startswith('/') and value.endswith('/'):
        return apply_regex_filter(data, column, value[1:-1])
    
    # Default: smart match (numeric or text)
    else:
        return apply_smart_match_filter(data, column, value)

def apply_operator_filter(data, column, value_str, operator):
    try:
        value = float(value_str)
        filtered_data = []
        for row in data:
            row_value = float(row.get(column, 0))
            if operator == '>=' and row_value >= value:
                filtered_data.append(row)
            elif operator == '<=' and row_value <= value:
                filtered_data.append(row)
            elif operator == '>' and row_value > value:
                filtered_data.append(row)
            elif operator == '<' and row_value < value:
                filtered_data.append(row)
            elif operator == '=' and row_value == value:
                filtered_data.append(row)
            elif operator == '!=' and row_value != value:
                filtered_data.append(row)
        return filtered_data
    except (ValueError, TypeError):
        # Fall back to text comparison
        return apply_text_filter(data, column, operator + value_str)

def apply_range_filter(data, column, min_val, max_val):
    return [row for row in data if min_val <= float(row.get(column, 0)) <= max_val]

def apply_wildcard_filter(data, column, pattern):
    import re
    # Convert wildcards to regex
    regex_pattern = pattern.replace('*', '.*').replace('%', '.*')
    try:
        regex = re.compile(regex_pattern, re.IGNORECASE)
        return [row for row in data if regex.search(str(row.get(column, '')))]
    except re.error:
        return data

def apply_regex_filter(data, column, pattern):
    import re
    try:
        regex = re.compile(pattern, re.IGNORECASE)
        return [row for row in data if regex.search(str(row.get(column, '')))]
    except re.error:
        return data

def apply_smart_match_filter(data, column, value):
    try:
        # Try numeric exact match
        numeric_value = float(value)
        return [row for row in data if float(row.get(column, 0)) == numeric_value]
    except (ValueError, TypeError):
        # Fall back to text contains
        return [row for row in data if value.lower() in str(row.get(column, '')).lower()]

def compare_values(row_value, filter_value, operator):
    try:
        # Try numeric comparison first
        rv = float(row_value)
        fv = float(filter_value)
        
        if operator == '>':
            return rv > fv
        elif operator == '>=':
            return rv >= fv
        elif operator == '<':
            return rv < fv
        elif operator == '<=':
            return rv <= fv
        elif operator == '=':
            return rv == fv
        elif operator == '!=':
            return rv != fv
        else:
            return False
            
    except (ValueError, TypeError):
        # Fall back to string comparison
        rv_str = str(row_value).lower()
        fv_str = str(filter_value).lower()
        
        if operator in ['=', '==']:
            return rv_str == fv_str
        elif operator == '!=':
            return rv_str != fv_str
        elif operator == '>':
            return rv_str > fv_str
        elif operator == '>=':
            return rv_str >= fv_str
        elif operator == '<':
            return rv_str < fv_str
        elif operator == '<=':
            return rv_str <= fv_str
        else:
            return fv_str in rv_str

# Global variables for RSRP data
zte_rsrp_df = None
huawei_rsrp_df = None

def extract_rsrp_filters_from_request(request):
    """Extract RSRP filter parameters from Flask request object"""
    return {
        # Text filters
        'Cell_Name': request.form.get('cell_name_filter', ''),
        'Site_ID': request.form.get('site_id_filter', ''),
        'Site_Name': request.form.get('site_name_filter', ''),
        
        # Smart direct filters (auto-detect type)
        'RSRP Range 1 (>-105dBm) %': request.form.get('rsrp_range1_direct', ''),
        'RSRP Range 2 (-105~-110dBm) %': request.form.get('rsrp_range2_direct', ''),
        'RSRP Range 3 (-110~-115dBm) %': request.form.get('rsrp_range3_direct', ''),
        'RSRP < -115dBm %': request.form.get('rsrp_range4_direct', ''),
        
        # Traditional min/max filters
        'RSRP Range 1 (>-105dBm) %_min': request.form.get('rsrp_range1_min', ''),
        'RSRP Range 1 (>-105dBm) %_max': request.form.get('rsrp_range1_max', ''),
        'RSRP Range 2 (-105~-110dBm) %_min': request.form.get('rsrp_range2_min', ''),
        'RSRP Range 2 (-105~-110dBm) %_max': request.form.get('rsrp_range2_max', ''),
        'RSRP Range 3 (-110~-115dBm) %_min': request.form.get('rsrp_range3_min', ''),
        'RSRP Range 3 (-110~-115dBm) %_max': request.form.get('rsrp_range3_max', ''),
        'RSRP < -115dBm %_min': request.form.get('rsrp_range4_min', ''),
        'RSRP < -115dBm %_max': request.form.get('rsrp_range4_max', '')
    }

def process_rsrp_filter_request(rsrp_data, request):
    """Process an RSRP filtering request and return filtered results with metadata"""
    filters = extract_rsrp_filters_from_request(request)
    sort_by = request.form.get('sort_by', '')
    sort_order = request.form.get('sort_order', 'asc')
    
    filtered_data = filter_and_sort_rsrp_data(rsrp_data, filters, sort_by, sort_order)
    
    return {
        'data': filtered_data,
        'total_count': len(rsrp_data),
        'filtered_count': len(filtered_data),
        'filters': filters,
        'sort_by': sort_by,
        'sort_order': sort_order
    }

def validate_msisdn_and_get_rsrp_data(msisdn, get_msisdn_data_func):
    """Validate MSISDN and fetch RSRP data, returning error or data"""
    if not msisdn:
        return {'error': 'MSISDN required'}, 400
    
    result = get_msisdn_data_func(msisdn)
    if "error" in result:
        return {'error': result["error"]}, 404
    
    cellcode = result.get('Cellcode')
    if not cellcode or cellcode == "Not Found":
        return {'error': 'No cell code found for this MSISDN'}, 404
    
    rsrp_data = fetch_rsrp_data_directly(cellcode)
    if not rsrp_data:
        return {'error': 'No RSRP data found'}, 404
    
    return {'rsrp_data': rsrp_data, 'cellcode': cellcode}, 200

def validate_common_location_request(msisdn, cell_code):
    """Validate common location RSRP request parameters"""
    if not msisdn:
        return {'error': 'MSISDN required'}, 400
    
    if not cell_code:
        return {'error': 'Cell code required'}, 400
    
    # Extract site ID from cell code (first 6 characters)
    site_id = str(cell_code)[:6]
    
    # Get RSRP data directly for the specific Site ID
    site_rsrp_data = fetch_rsrp_data_by_site_id(site_id)
    
    if not site_rsrp_data:
        return {'error': f'No RSRP data found for Cell Code {cell_code}'}, 404
    
    return {'rsrp_data': site_rsrp_data, 'site_id': site_id, 'cell_code': cell_code}, 200
