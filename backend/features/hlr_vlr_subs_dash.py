from dash import Dash, html, dcc
import plotly.graph_objs as go
import pandas as pd

def create_hlr_vlr_subs_dash_app(server, data_file_path, url_base_pathname='/hlr-vlr-subbase-graph/'):
    dash_app = Dash(__name__, server=server, url_base_pathname=url_base_pathname)

    def get_hlr_vlr_subs_figure():
        try:
            df = pd.read_excel(data_file_path, sheet_name='Daily HLR Subs')
        except Exception as e:
            print(f"[HLR VLR Subs] Error reading sheet: {e}")
            return go.Figure()

        fig = go.Figure()
        x_col = df.columns[0]
        x = df[x_col].astype(str)
        for col in df.columns[1:]:
            fig.add_trace(go.Scatter(x=x, y=df[col], mode='lines+markers', name=col))
        fig.update_layout(title='Daily HLR/VLR Subscribers (HLR_VLR_Subbase.xls)',
                          xaxis_title=x_col,
                          yaxis_title='Subscriber Count',
                          template='plotly_white')
        return fig

    dash_app.layout = html.Div([
        html.H2('Line Graph - Daily HLR Subscribers'),
        dcc.Graph(id='hlr-vlr-subs-graph', figure=get_hlr_vlr_subs_figure()),
        html.Div('This chart visualizes the daily HLR subscribers from the HLR_VLR_Subbase.xls file.')
    ])
    return dash_app
