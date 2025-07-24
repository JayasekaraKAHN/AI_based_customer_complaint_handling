def get_msisdn_data(msisdn, INPUT_FILE, SIM_TYPE_MAPPING, ref_df, tac_df, usage_df, USAGE_FILES, VLRD, fetch_rsrp_data_by_site_id, fetch_rsrp_data_directly):
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
                import re
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
                    except ValueError:
                        return {"error": "Invalid hex values for LAC or SAC"}
                    except Exception as e:
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
                sorted_months = sorted(USAGE_FILES.keys(), key=lambda x: (USAGE_FILES[x]['year'], USAGE_FILES[x]['month']))
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
                        total = (int(grouped.at[month, 'VOLUME_2G_MB']) + int(grouped.at[month, 'VOLUME_3G_MB']) + int(grouped.at[month, 'VOLUME_4G_MB']) + int(grouped.at[month, 'VOLUME_5G_MB']))
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
                                    cell_data['RSRP_DATA'] = []
                            common_cells.append(cell_data)
            except Exception as e:
                common_cells = []
            rsrp_data = []
            if cellcode and cellcode != "Not Found":
                try:
                    rsrp_data = fetch_rsrp_data_directly(cellcode)
                    if not rsrp_data:
                        rsrp_data = []
                except Exception as e:
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
            return result
    return {"error": "MSISDN not found"}


