import pandas as pd
import re
def fetch_rsrp_data_directly(cell_code, zte_rsrp_df, huawei_rsrp_df, ref_df):
    site_id = str(cell_code)[:6]
    zte_filtered = zte_rsrp_df[zte_rsrp_df['Site_ID'].astype(str) == site_id]
    huawei_filtered = huawei_rsrp_df[huawei_rsrp_df['Site_ID'].astype(str) == site_id]
    if zte_filtered.empty and huawei_filtered.empty:
        return None
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
            'RSRP < -115dBm %': round(float(rsrp_row['RSRP < -115dBm']) * 100, 2)
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
    site_info = add_calculated_rsrp_columns(site_info)
    return site_info

def add_calculated_rsrp_columns(rsrp_data):
    if not rsrp_data:
        return rsrp_data
    
    site_averages = {}
    
    for row in rsrp_data:
        site_name = row.get('Site_Name', 'Unknown')
        if site_name not in site_averages:
            site_averages[site_name] = {
                'range1_values': [],
                'range2_values': [],
                'range3_values': [],
                'range4_values': []
            }
        
        try:
            range1 = float(row.get('RSRP Range 1 (>-105dBm) %', 0))
            range2 = float(row.get('RSRP Range 2 (-105~-110dBm) %', 0))
            range3 = float(row.get('RSRP Range 3 (-110~-115dBm) %', 0))
            range4 = float(row.get('RSRP < -115dBm %', 0))
            
            site_averages[site_name]['range1_values'].append(range1)
            site_averages[site_name]['range2_values'].append(range2)
            site_averages[site_name]['range3_values'].append(range3)
            site_averages[site_name]['range4_values'].append(range4)
            
        except (ValueError, TypeError):
            continue
    
    for site_name in site_averages:
        site_data = site_averages[site_name]
        
        avg_range1 = sum(site_data['range1_values']) / len(site_data['range1_values']) if site_data['range1_values'] else 0
        avg_range2 = sum(site_data['range2_values']) / len(site_data['range2_values']) if site_data['range2_values'] else 0
        avg_range3 = sum(site_data['range3_values']) / len(site_data['range3_values']) if site_data['range3_values'] else 0
        avg_range4 = sum(site_data['range4_values']) / len(site_data['range4_values']) if site_data['range4_values'] else 0
        
        site_averages[site_name]['avg_range1'] = round(avg_range1, 2)
        site_averages[site_name]['avg_range2'] = round(avg_range2, 2)
        site_averages[site_name]['avg_range3'] = round(avg_range3, 2)
        site_averages[site_name]['avg_range4'] = round(avg_range4, 2)
        
        site_averages[site_name]['good_signal_avg'] = round(avg_range1 + avg_range2, 2)
        site_averages[site_name]['poor_signal_avg'] = round(avg_range3 + avg_range4, 2)
    
    for row in rsrp_data:
        site_name = row.get('Site_Name', 'Unknown')
        
        if site_name in site_averages:
            good_signal_avg = site_averages[site_name]['good_signal_avg']
            poor_signal_avg = site_averages[site_name]['poor_signal_avg']
            
            row['Good Signal Avg (Range 1+2) %'] = good_signal_avg
            row['Poor Signal Avg (Range 3+4) %'] = poor_signal_avg
            
            if good_signal_avg > poor_signal_avg:
                row['Signal Quality'] = 'Good'
            else:
                row['Signal Quality'] = 'Poor'
        else:
            row['Good Signal Avg (Range 1+2) %'] = 0.0
            row['Poor Signal Avg (Range 3+4) %'] = 0.0
            row['Signal Quality'] = 'Poor' 
    
    return rsrp_data


def filter_and_sort_rsrp_data(rsrp_data, filters=None, sort_by=None, sort_order='asc'):
    if not rsrp_data:
        return []
    filtered_data = rsrp_data.copy()
    if filters:
        for key, value in filters.items():
            if value and str(value).strip():
                filtered_data = apply_type_sensitive_filter(filtered_data, key, value)
    sortable_cols = [
        'Cell_Name', 'Site_ID', 'Site_Name',
        'RSRP Range 1 (>-105dBm) %', 'RSRP Range 2 (-105~-110dBm) %',
        'RSRP Range 3 (-110~-115dBm) %', 'RSRP < -115dBm %'
    ]
    if sort_by and sort_by in sortable_cols:
        try:
            is_numeric = sort_by in sortable_cols[3:]
            filtered_data.sort(
                key=lambda x: float(x.get(sort_by, 0)) if is_numeric else str(x.get(sort_by, '')).lower(),
                reverse=(sort_order == 'desc')
            )
        except (ValueError, TypeError):
            pass
    return filtered_data

def apply_type_sensitive_filter(data, filter_key, filter_value):
    value_str = str(filter_value).strip()
    
    if filter_key in ['Cell_Name', 'Site_ID', 'Site_Name']:
        return apply_text_filter(data, filter_key, value_str)
    
    elif filter_key.endswith('_min'):
        return apply_numeric_min_filter(data, filter_key, value_str)
    elif filter_key.endswith('_max'):
        return apply_numeric_max_filter(data, filter_key, value_str)
    
    else:
        return apply_auto_detect_filter(data, filter_key, value_str)

def apply_text_filter(data, column, value):
    if value.startswith('='):
        target = value[1:].lower()
        return [
            row for row in data 
            if str(row.get(column, '')).lower() == target
        ]
    
    elif value.startswith('!='):
        target = value[2:].lower()
        return [
            row for row in data 
            if str(row.get(column, '')).lower() != target
        ]
    
    elif '*' in value or '%' in value:
        return apply_wildcard_filter(data, column, value)
    
    elif value.startswith('/') and value.endswith('/') and len(value) > 2:
        return apply_regex_filter(data, column, value[1:-1])
    
    else:
        return [
            row for row in data 
            if value.lower() in str(row.get(column, '')).lower()
        ]

def apply_numeric_min_filter(data, filter_key, value):
    rsrp_column = filter_key.replace('_min', '')
    if rsrp_column in ['RSRP Range 1 (>-105dBm) %', 'RSRP Range 2 (-105~-110dBm) %', 
                      'RSRP Range 3 (-110~-115dBm) %', 'RSRP < -115dBm %']:
        try:
            min_value = float(value)
            return [
                row for row in data 
                if float(row.get(rsrp_column, 0)) >= min_value
            ]
        except (ValueError, TypeError):
            return data
    return data

def apply_numeric_max_filter(data, filter_key, value):
    rsrp_column = filter_key.replace('_max', '')
    if rsrp_column in ['RSRP Range 1 (>-105dBm) %', 'RSRP Range 2 (-105~-110dBm) %', 
                      'RSRP Range 3 (-110~-115dBm) %', 'RSRP < -115dBm %']:
        try:
            max_value = float(value)
            return [
                row for row in data 
                if float(row.get(rsrp_column, 0)) <= max_value
            ]
        except (ValueError, TypeError):
            return data
    return data

def apply_auto_detect_filter(data, column, value):
    return apply_text_filter(data, column, value)

def apply_wildcard_filter(data, column, pattern):
    import re
    regex_pattern = pattern.replace('*', '.*').replace('%', '.*')
    try:
        compiled_pattern = re.compile(regex_pattern, re.IGNORECASE)
        return [
            row for row in data
            if compiled_pattern.search(str(row.get(column, '')))
        ]
    except re.error:
        return apply_text_filter(data, column, pattern)

def apply_regex_filter(data, column, pattern):
    import re
    try:
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        return [
            row for row in data
            if compiled_pattern.search(str(row.get(column, '')))
        ]
    except re.error:
        return []
    

def fetch_rsrp_data_by_site_id(site_id, zte_rsrp_df, huawei_rsrp_df):
    site_id_str = str(site_id)[:6]
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
    # Add calculated columns to all entries
    site_info = add_calculated_rsrp_columns(site_info)
    return site_info


