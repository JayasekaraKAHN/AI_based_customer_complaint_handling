import pandas as pd
import json
from flask import Blueprint, render_template

hlr_vlr_bp = Blueprint('hlr_vlr', __name__)

@hlr_vlr_bp.route("/hlr-vlr")
def hlr_vlr_graph():
    df_all = pd.read_excel("C:/Users/kasun/OneDrive/Desktop/AI_based_customer_complaint_handling/backend/data_files/HLR_VLR_Subbase.xls", sheet_name="Daily HLR Subs", skiprows=2)

    df_all['Date'] = pd.to_datetime(df_all['Date'])
    df_all = df_all.sort_values(by='Date')

    labels = df_all['Date'].dt.strftime('%Y-%m-%d').tolist()
    prepaid = df_all['Prepaid Subs'].tolist()
    postpaid = df_all['Postpaid Subs'].tolist()
    vlr = df_all['Total VLR Subs'].tolist()
    hss = df_all['Total HSS Subs'].tolist()

    return render_template("hlr_vlr_graph.html",
                           labels=json.dumps(labels),
                           prepaid=json.dumps(prepaid),
                           postpaid=json.dumps(postpaid),
                           vlr=json.dumps(vlr),
                           hss=json.dumps(hss))
