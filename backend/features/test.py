from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from datetime import timedelta
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from usage_graphs import create_dash_app 
import pandas as pd
import re
import io
import os
import folium
import calendar

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static'))

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = "admin12345"
app.permanent_session_lifetime = timedelta(minutes=10)

#auto-detect usage files
def auto_detect_usage_files(data_directory=None):
    if data_directory is None:
        data_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
    usage_files = {}    
    try:
        all_files = os.listdir(data_directory)
    except OSError:
        return usage_files
    
    for filename in all_files:
        match = re.match(r"USERTD_(\d{4})_(\d{2})\.txt", filename)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
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

#display user location on map
def create_location_map(result_data):
    try:
        lat = result_data.get('Lat', 'Not Found')
        lon = result_data.get('Lon', 'Not Found')
        sitename = result_data.get('Sitename', 'Unknown Site')
        district = result_data.get('District', 'Unknown District')
        msisdn = result_data.get('MSISDN', 'Unknown')
        
        default_lat, default_lon = 7.8731, 80.7718 # Default to Colombo
        
        if lat != 'Not Found' and lon != 'Not Found':
            try:
                lat = float(lat)
                lon = float(lon)
                center_lat, center_lon = lat, lon
                zoom_level = 12
                found_location = True
            except (ValueError, TypeError):
                center_lat, center_lon = default_lat, default_lon
                zoom_level = 7
                found_location = False
        else:
            center_lat, center_lon = default_lat, default_lon
            zoom_level = 7
            found_location = False
        
        map_obj = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_level,
            tiles='OpenStreetMap'
        )
        
        popup_content = f"""
        <div style="width: 280px; font-family: Arial, sans-serif;">
            <h5 style="color: #2196F3; background: #E3F2FD; padding: 8px; margin: -5px -5px 10px -5px; border-radius: 4px;">
                📱 User Location
            </h5>
            <table style="width: 100%; font-size: 12px;">
                <tr><td><strong>MSISDN:</strong></td><td>{msisdn}</td></tr>
                <tr><td><strong>Site:</strong></td><td>{sitename}</td></tr>
                <tr><td><strong>District:</strong></td><td>{district}</td></tr>
                <tr><td><strong>Region:</strong></td><td>{result_data.get('Region', 'Unknown')}</td></tr>
                <tr><td><strong>Cell Code:</strong></td><td>{result_data.get('Cellcode', 'Unknown')}</td></tr>
                <tr><td><strong>LAC:</strong></td><td>{result_data.get('LAC', 'Unknown')}</td></tr>
                <tr><td><strong>SAC:</strong></td><td>{result_data.get('SAC', 'Unknown')}</td></tr>
                <tr><td><strong>Coordinates:</strong></td><td>{lat}, {lon}</td></tr>
            </table>
        </div>
        """
        
        if found_location:
            folium.Marker(
                location=[center_lat, center_lon],
                popup=folium.Popup(popup_content, max_width=320),
                tooltip=f"👤 User: {msisdn} | {district}",
                icon=folium.Icon(
                    color='red', 
                    icon='user', 
                    prefix='fa'
                )
            ).add_to(map_obj)
            
        else:
            folium.Marker(
                location=[center_lat, center_lon],
                popup=folium.Popup(
                    """
                    <div style="width: 200px;">
                        <h6 style="color: #FF5722;">Location Not Found</h6>
                        <p>Showing default Sri Lanka location</p>
                        <p><strong>MSISDN:</strong> {}</p>
                        <p><strong>Coordinates:</strong> Not available</p>
                    </div>
                    """.format(msisdn), 
                    max_width=220
                ),
                tooltip="Location not available",
                icon=folium.Icon(color='gray', icon='question-circle', prefix='fa')
            ).add_to(map_obj)
        
        # Add a simple legend
        legend_html = f"""
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; height: auto; 
                    background-color: white; border: 2px solid #ccc; z-index: 9999; 
                    font-size: 12px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        <p style="margin: 5px 0; font-size: 10px; color: #666;">
            <strong>District:</strong> {district}<br>
            <strong>Region:</strong> {result_data.get('Region', 'Unknown')}
        </p>
        </div>
        """
        map_obj.get_root().html.add_child(folium.Element(legend_html))
        
        return map_obj
        
    except Exception as e:
        print(f"Error creating map: {e}")
        map_obj = folium.Map(
            location=[7.8731, 80.7718],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        folium.Marker(
            location=[7.8731, 80.7718],
            popup=folium.Popup(
                f"""
                <div style="width: 200px;">
                    <h6 style="color: #F44336;">Map Error</h6>
                    <p>Unable to create location map</p>
                    <p><strong>MSISDN:</strong> {result_data.get('MSISDN', 'Unknown')}</p>
                    <p><strong>Error:</strong> {str(e)[:50]}...</p>
                </div>
                """, 
                max_width=220
            ),
            icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
        ).add_to(map_obj)
        
        return map_obj

#user count by site
def get_user_count(month=None, district=None):
    df_list = []
    for m, file_info in USAGE_FILES.items():
        if month and m != month:
            continue
        df = pd.read_csv(file_info['filename'], sep="\t", dtype={"MSISDN": str})
        df.columns = [col.strip().upper() for col in df.columns]
        df["Month"] = m
        df_list.append(df)

    if not df_list:
        return pd.DataFrame()

    usage_all = pd.concat(df_list, ignore_index=True)

    if "MSISDN" not in VLRD.columns:
        return pd.DataFrame()

    usage_all["MSISDN"] = usage_all["MSISDN"].astype(str)
    VLRD["MSISDN"] = VLRD["MSISDN"].astype(str)
    merged_df = pd.merge(usage_all, VLRD, on="MSISDN", how="inner")
    merged_df["SITE_ID"] = merged_df["CELL_CODE"].astype(str).str[:6]

    district_upper = district.upper() if district else ""       # get district by site name
    matching_district = None
    if district:
        sitename_match = ref_df[ref_df["sitename"].str.upper() == district_upper]
        if not sitename_match.empty:
            matching_district = sitename_match.iloc[0]["district"]
            district_upper = matching_district.upper()

    if district:
        merged_df = merged_df[merged_df["DISTRICT"].str.upper() == district_upper]

    result_df = merged_df.groupby(['DISTRICT', 'SITE_ID'])['MSISDN'].nunique().reset_index()
    result_df.rename(columns={'MSISDN': 'User_Count'}, inplace=True)
    result_df = result_df.sort_values(by='User_Count', ascending=False)
    return result_df

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

#MSISDN data retrieval
def get_msisdn_data(msisdn):
    global latest_result

    with open(INPUT_FILE, "r") as file:
        lines = file.readlines()

    for line in lines:
        columns = line.strip().split(";")
        if len(columns) < 5:
            continue

        imsi = columns[0]
        msisdn_entry = columns[1]
        tac = columns[2][:8]
        location = columns[4]
        imei = columns[2]  

        if msisdn_entry == msisdn:
            sitename = cellcode = lon = lat = region = district = "Not Found"
            sim_type = connection_type = "Unknown"

            if len(imsi) >= 8:
                imsi_digit = imsi[7]
                if imsi_digit in SIM_TYPE_MAPPING:
                    sim_type, connection_type = SIM_TYPE_MAPPING[imsi_digit]

            lac_dec = sac_dec = "Not Found"
            if location.strip():
                match = re.match(r"(\d+)-(\w+)-([a-fA-F0-9]+)", location)
                if match:
                    try:
                        lac_dec = int(match.group(2), 16)
                        sac_dec = int(match.group(3), 16)
                        
                        matched_row = ref_df[(ref_df['lac'] == lac_dec) & (ref_df['cellid'] == sac_dec)]
                        
                        if not matched_row.empty:
                            row = matched_row.iloc[0]
                            sitename = row['sitename']
                            cellcode = row['cellcode']
                            lon = float(row['lon'])
                            lat = float(row['lat'])
                            region = row['region']
                            district = row['district']
                            
                            technology_type = row.get('type', 'Unknown')
                            
                            print(f"Found location: {sitename} ({district}, {region}) - {technology_type}")
                            print(f"Coordinates: {lat}, {lon}")
                        else:
                            alt_match = ref_df[ref_df['lac'] == lac_dec]
                            if not alt_match.empty:
                                closest_match = alt_match.iloc[0]
                                sitename = f"{closest_match['sitename']} (Approximate)"
                                cellcode = closest_match['cellcode']
                                lon = float(closest_match['lon'])
                                lat = float(closest_match['lat'])
                                region = closest_match['region']
                                district = closest_match['district']
                                print(f"Using approximate location: {sitename}")
                            else:
                                print(f"No reference data found for LAC: {lac_dec}, Cell: {sac_dec}")
                                
                    except ValueError:
                        return {"error": "Invalid hex values for LAC or SAC"}
                    except Exception as e:
                        print(f"Error processing location data: {e}")
                        return {"error": f"Location processing error: {str(e)}"}

            brand = model = software_os_name = marketing_name = year_released = device_type = volte = technology = primary_hardware_type = "Not Found"
            if tac.isdigit():
                tac_row = tac_df[tac_df['tac'] == int(tac)]
                if not tac_row.empty:
                    row = tac_row.iloc[0]
                    brand = row['brand']
                    model = row['model']
                    software_os_name = row['software_os_name']
                    marketing_name = row['marketing_name']
                    year_released = row['year_released']
                    device_type = row['device_type']
                    volte = row['volte']
                    technology = row['technology']
                    primary_hardware_type = row['primary_hardware_type']

            usage_records = usage_df[usage_df["MSISDN"] == int(msisdn)]
            monthly_usage = {
                "months": [],
                "2G": [],
                "3G": [],
                "4G": [],
                "5G": [],
                "outgoing_voice": [],
                "incoming_voice": [],
                "outgoing_sms":[],
                "incoming_sms": [],
                "Total": []
            }

            if not usage_records.empty:
                grouped = usage_records.groupby("MONTH").sum(numeric_only=True)
                sorted_months = sorted(USAGE_FILES.keys(), 
                    key=lambda x: (USAGE_FILES[x]['year'], USAGE_FILES[x]['month']))
                
                for month in sorted_months:
                    monthly_usage["months"].append(month)
                    monthly_usage["2G"].append(int(grouped.at[month, 'VOLUME_2G_MB']) if month in grouped.index else 0)
                    monthly_usage["3G"].append(int(grouped.at[month, 'VOLUME_3G_MB']) if month in grouped.index else 0)
                    monthly_usage["4G"].append(int(grouped.at[month, 'VOLUME_4G_MB']) if month in grouped.index else 0)
                    monthly_usage["5G"].append(int(grouped.at[month, 'VOLUME_5G_MB']) if month in grouped.index else 0)
                    monthly_usage["incoming_voice"].append(round(grouped.at[month, 'INCOMING_VOICE'], 2) if month in grouped.index else 0.00)
                    monthly_usage["outgoing_voice"].append(round(grouped.at[month, 'OUTGOING_VOICE'], 2) if month in grouped.index else 0.00)
                    monthly_usage["incoming_sms"].append(int(grouped.at[month, 'INCOMING_SMS']) if month in grouped.index else 0)
                    monthly_usage["outgoing_sms"].append(int(grouped.at[month, 'OUTGOING_SMS']) if month in grouped.index else 0)

                    total = 0
                    if month in grouped.index:
                        total = (int(grouped.at[month, 'VOLUME_2G_MB']) +
                                 int(grouped.at[month, 'VOLUME_3G_MB']) +
                                 int(grouped.at[month, 'VOLUME_4G_MB']) +
                                 int(grouped.at[month, 'VOLUME_5G_MB']))
                    monthly_usage["Total"].append(total)

            common_cells = []
            try:
                if not VLRD.empty:
                    vlrd_matches = VLRD[VLRD["MSISDN"] == int(msisdn)]
                    
                    if not vlrd_matches.empty:
                        for _, row in vlrd_matches.iterrows():
                            cell_data = {
                                'CELL_CODE': row.get('CELL_CODE', 'Unknown'),
                                'SITE_NAME': row.get('SITE_NAME', 'Unknown'),
                                'DISTRICT': row.get('DISTRICT', 'Unknown'),
                                'LAC': row.get('LAC', 'Unknown'),
                                'CELL': row.get('CELL', 'Unknown'),
                                'LON': 'Not Found',
                                'LAT': 'Not Found',
                                'RSRP_DATA': []
                            }
                            
                            if cell_data['CELL_CODE'] != 'Unknown':
                                ref_match = ref_df[ref_df['cellcode'] == cell_data['CELL_CODE']]
                                if not ref_match.empty:
                                    cell_data['LON'] = ref_match.iloc[0]['lon']
                                    cell_data['LAT'] = ref_match.iloc[0]['lat']
                                
                                site_id = str(cell_data['CELL_CODE'])[:6]
                                try:
                                    rsrp_data_for_site = fetch_rsrp_data_by_site_id(site_id)
                                    cell_data['RSRP_DATA'] = rsrp_data_for_site if rsrp_data_for_site else []
                                except Exception as e:
                                    print(f"Error fetching RSRP data for Site ID {site_id}: {e}")
                                    cell_data['RSRP_DATA'] = []
                            
                            common_cells.append(cell_data)
                        
            except Exception as e:
                print(f"Error processing VLRD data: {e}")
                common_cells = []

            rsrp_data = []
            if cellcode and cellcode != "Not Found":
                try:
                    rsrp_data = fetch_rsrp_data_directly(cellcode)
                    if not rsrp_data:
                        rsrp_data = []
                except Exception as e:
                    print(f"Error fetching RSRP data: {e}")
                    rsrp_data = []

            result = {
                "MSISDN": msisdn,
                "IMSI": imsi,
                "IMEI": imei,
                "SIM Type": sim_type,
                "Connection Type": connection_type,
                "LAC": lac_dec,
                "SAC": sac_dec,
                "Sitename": sitename,
                "Cellcode": cellcode,
                "Lon": lon,
                "Lat": lat,
                "Region": region,
                "District": district,
                "TAC": tac,
                "Brand": brand,
                "Model": model,
                "OS": software_os_name,
                "Marketing Name": marketing_name,
                "Year Released": year_released,
                "Device Type": device_type,
                "VoLTE": volte,
                "Technology": technology,
                "Primary Hardware Type": primary_hardware_type,
                "Monthly Usage": monthly_usage,
                "Common Cell Locations": common_cells,
                "RSRP Data": rsrp_data
            }

            latest_result = result
            return result

    return {"error": "MSISDN not found"}

def fetch_rsrp_data_directly(cell_code):
    global zte_rsrp_df, huawei_rsrp_df, ref_df

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
    value = value.strip()
    
    if ',' in value:
        conditions = [cond.strip() for cond in value.split(',')]
        filtered_data = data
        for condition in conditions:
            if condition:
                filtered_data = apply_single_auto_filter(filtered_data, column, condition)
        return filtered_data
    
    return apply_single_auto_filter(data, column, value)

def apply_single_auto_filter(data, column, value):

    if value.startswith('>='):
        return apply_operator_filter(data, column, value[2:], '>=')
    elif value.startswith('<='):
        return apply_operator_filter(data, column, value[2:], '<=')
    elif value.startswith('>'):
        return apply_operator_filter(data, column, value[1:], '>')
    elif value.startswith('<'):
        return apply_operator_filter(data, column, value[1:], '<')
    
    elif value.startswith('='):
        return apply_operator_filter(data, column, value[1:], '=')

    elif value.startswith('!='):
        return apply_operator_filter(data, column, value[2:], '!=')
    
    elif '-' in value and not value.startswith('-') and len(value.split('-')) == 2:
        parts = value.split('-')
        try:
            min_val, max_val = float(parts[0].strip()), float(parts[1].strip())
            if min_val <= max_val:
                return apply_range_filter(data, column, min_val, max_val)
        except (ValueError, TypeError):
            pass
        return apply_text_filter(data, column, value)
    
    elif '*' in value or '%' in value:
        return apply_wildcard_filter(data, column, value)
    
    elif value.startswith('/') and value.endswith('/') and len(value) > 2:
        return apply_regex_filter(data, column, value[1:-1])
    
    else:
        return apply_smart_match_filter(data, column, value)

def apply_operator_filter(data, column, value_str, operator):
    try:
        threshold = float(value_str.strip())
        return [
            row for row in data
            if compare_values(row.get(column), operator, threshold)
        ]
    except (ValueError, TypeError):
        if operator in ['=', '!=']:
            target = value_str.strip().lower()
            if operator == '=':
                return [
                    row for row in data
                    if str(row.get(column, '')).lower() == target
                ]
            else:  # !=
                return [
                    row for row in data
                    if str(row.get(column, '')).lower() != target
                ]
        return apply_text_filter(data, column, f"{operator}{value_str}")

def apply_range_filter(data, column, min_val, max_val):
    return [
        row for row in data
        if min_val <= float(row.get(column, 0)) <= max_val
    ]

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

def apply_smart_match_filter(data, column, value):

    sample_values = [row.get(column) for row in data[:10] if row.get(column)]
    is_numeric_column = all(
        isinstance(val, (int, float)) or 
        (isinstance(val, str) and val.replace('.', '').replace('-', '').isdigit())
        for val in sample_values if val
    )
    
    if is_numeric_column:
        try:
            target_value = float(value)
            tolerance = 0.01
            return [
                row for row in data 
                if abs(float(row.get(column, 0)) - target_value) <= tolerance
            ]
        except (ValueError, TypeError):
            pass
    
    return apply_text_filter(data, column, value)

def compare_values(data_value, operator, threshold):
    """Enhanced comparison function with better type handling"""
    try:
        data_val = float(data_value)
        if operator == '>':
            return data_val > threshold
        elif operator == '>=':
            return data_val >= threshold
        elif operator == '<':
            return data_val < threshold
        elif operator == '<=':
            return data_val <= threshold
        elif operator == '=':
            return abs(data_val - threshold) <= 0.01 
        elif operator == '!=':
            return abs(data_val - threshold) > 0.01
        return False
    except (ValueError, TypeError):
        if operator in ['=', '!=']:
            data_str = str(data_value).lower()
            threshold_str = str(threshold).lower()
            if operator == '=':
                return data_str == threshold_str
            else:
                return data_str != threshold_str
        return False
    

#route 
@app.route('/')
def home():
    return render_template('home.html')

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
    result = get_msisdn_data(msisdn)

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
    result = get_msisdn_data(msisdn)
    
    if "error" in result:
        return render_template('index.html', error=result["error"])
    
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
    
    return render_template('index.html', result=result, has_map=has_map)

#user count by site
@app.route('/user_count')
def user_count():
    month = request.args.get('month')
    district = request.args.get('district')
    table_data = get_user_count(month, district)

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
    table_data = get_user_count(month, district)
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
    rsrp_data = fetch_rsrp_data_directly(cell_code)

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
    """Get RSRP data for a specific Site ID - for testing and direct access"""
    try:
        rsrp_data = fetch_rsrp_data_by_site_id(site_id)
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
    
    rsrp_data = fetch_rsrp_data_directly(cellcode)
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
        'RSRP < -115dBm %_max': request.form.get('rsrp_range4_max', '')
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
    
    site_rsrp_data = fetch_rsrp_data_by_site_id(site_id)
    
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
        'RSRP < -115dBm %_max': request.form.get('rsrp_range4_max', '')
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

def fetch_rsrp_data_by_site_id(site_id):
    global zte_rsrp_df, huawei_rsrp_df
    
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
    
    return site_info

dash_app = create_dash_app(app, latest_result)

application = DispatcherMiddleware(app.wsgi_app, {
    '/usage-graph': dash_app.server
})

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, application, use_debugger=True, use_reloader=True)
