from dash import Dash, html, dcc
import plotly.graph_objs as go
import pandas as pd
import os

def create_call_drop_rate_dash_app(server, data_file_path, url_base_pathname='/call-drop-rate-graph/'):
    dash_app = Dash(__name__, server=server, url_base_pathname=url_base_pathname)

    def get_call_drop_rate_figure():
        if not os.path.exists(data_file_path):
            return go.Figure()

        try:
            df = pd.read_excel(data_file_path, sheet_name='Average_3G_Call_Drop_Rate')
            site_col = 'Site Name' if 'Site Name' in df.columns else df.columns[0]
            drop_col = 'Call Drop Rate (%)' if 'Call Drop Rate (%)' in df.columns else df.columns[-1]
            df = df.dropna(subset=[site_col, drop_col], how='all')
            print(f"[Call Drop Rate] Rows visualized from 'Average_3G_Call_Drop_Rate': {len(df)}")
        except Exception as e:
            print(f"[Call Drop Rate] Error reading sheet: {e}")
            return go.Figure()
        site_col = 'Site Name' if 'Site Name' in df.columns else df.columns[0]
        drop_col = 'Call Drop Rate (%)' if 'Call Drop Rate (%)' in df.columns else df.columns[-1]
        x = df[site_col].astype(str).tolist()
        y = df[drop_col].tolist()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name='Call Drop Rate (%)'))
        fig.update_layout(title='3G Call Drop Rate by Site (Average_3G_Call_Drop_Rate Sheet)',
                          xaxis_title=site_col,
                          yaxis_title=drop_col,
                          template='plotly_white',
                          xaxis=dict(tickangle=45, tickfont=dict(size=10)),
                          yaxis=dict(tickformat='.2f'))
        return fig

    dash_app.layout = html.Div([
        html.H2('Line Graph - 3G Call Drop Rate by Site'),
        dcc.Graph(id='call-drop-rate-graph', figure=get_call_drop_rate_figure()),
        html.Div('This chart visualizes the call drop rate for each site from the Call_Drop_Rate_3G.xls file.')
    ])

    return dash_app
