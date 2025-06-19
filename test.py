from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import re
from datetime import timedelta
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

#import from external file usage graphs
from usage_graphs import create_dash_app  

app = Flask(__name__)
app.secret_key = "admin12345"
app.permanent_session_lifetime = timedelta(minutes=10)

# File paths
REFERENCE_FILE = "Reference_Data_Cell_Locations_20250403.csv"
TAC_FILE = "TACD_UPDATED.csv"
INPUT_FILE = "All_2025-4-2_3.txt"
USAGE_FILES = {
    "March": "USERTD_03.txt",
    "April": "USERTD_04.txt",
    "May": "USERTD_05.txt"
}

# Load reference data
ref_df = pd.read_csv(REFERENCE_FILE)
tac_df = pd.read_csv(TAC_FILE, low_memory=False)

@app.before_request
def check_login():
    session.permanent = True
    if not session.get("logged_in"):
        if request.endpoint not in ['login', 'static']:
            return redirect(url_for('login'))

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

@app.route('/logout')
def logout():
    session.pop("logged_in", None)
    return redirect(url_for('login'))

def load_usage_data():
    df_list = []
    for month, file in USAGE_FILES.items():
        df = pd.read_csv(file, sep="\t")
        df["Month"] = month
        df_list.append(df)
    return pd.concat(df_list, ignore_index=True)

usage_df = load_usage_data()

SIM_TYPE_MAPPING = {
    '1': ("ESIM", "PRE"),
    '2': ("USIM", "PRE"),
    '3': ("SIM", "PRE"),
    '7': ("ESIM", "POS"),
    '8': ("USIM", "POS"),
    '9': ("SIM", "POS")
}

latest_result = {}

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
                            lon = row['lon']
                            lat = row['lat']
                            region = row['region']
                            district = row['district']
                    except ValueError:
                        return {"error": "Invalid hex values for LAC or SAC"}

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
                "Total": []
            }

            if not usage_records.empty:
                grouped = usage_records.groupby("Month").sum(numeric_only=True)
                for month in USAGE_FILES.keys():
                    monthly_usage["months"].append(month)
                    monthly_usage["2G"].append(int(grouped.at[month, 'volume_2g_mb']) if month in grouped.index else 0)
                    monthly_usage["3G"].append(int(grouped.at[month, 'volume_3g_mb']) if month in grouped.index else 0)
                    monthly_usage["4G"].append(int(grouped.at[month, 'volume_4g_mb']) if month in grouped.index else 0)
                    monthly_usage["5G"].append(int(grouped.at[month, 'volume_5g_mb']) if month in grouped.index else 0)

                    total = 0
                    if month in grouped.index:
                        total = (int(grouped.at[month, 'volume_2g_mb']) +
                                 int(grouped.at[month, 'volume_3g_mb']) +
                                 int(grouped.at[month, 'volume_4g_mb']) +
                                 int(grouped.at[month, 'volume_5g_mb']))
                    monthly_usage["Total"].append(total)

            result = {
                "MSISDN": msisdn,
                "IMSI": imsi,
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
                "Monthly Usage": monthly_usage
            }

            latest_result = result
            return result

    return {"error": "MSISDN not found"}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    msisdn = request.form.get("msisdn")
    result = get_msisdn_data(msisdn)
    if "error" in result:
        return render_template('index.html', error=result["error"])
    return render_template('index.html', result=result)

# ✅ Create and mount Dash app from separate module
dash_app = create_dash_app(app, latest_result)

application = DispatcherMiddleware(app.wsgi_app, {
    '/usage-graph': dash_app.server
})

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, application, use_debugger=True, use_reloader=True)
