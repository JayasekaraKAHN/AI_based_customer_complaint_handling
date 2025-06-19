from dash import Dash, html, dcc
import plotly.graph_objs as go

def create_dash_app(server, latest_result, url_base_pathname='/usage-graph/'):
    dash_app = Dash(__name__, server=server, url_base_pathname=url_base_pathname)

    def get_usage_figure():
        if not latest_result.get("Monthly Usage"):
            return go.Figure()
        usage = latest_result["Monthly Usage"]
        fig = go.Figure()
        for tech in ["2G", "3G", "4G", "5G"]:
            fig.add_trace(go.Scatter(x=usage["months"], y=usage[tech],
                                     mode='lines+markers', name=tech))
        
        fig.update_layout(title="Monthly Usage by Network Type",
                          xaxis_title="Month", yaxis_title="Usage (MB)",
                          template="plotly_white")
        return fig

    def get_total_usage_figure():
        if not latest_result.get("Monthly Usage"):
            return go.Figure()
        usage = latest_result["Monthly Usage"]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=usage["months"], y=usage["Total"], name="Total Usage"))
        
        fig.update_layout(title="Total Monthly Usage",
                          xaxis_title="Month", yaxis_title="Total Usage (MB)",
                          template="plotly_white")
        return fig

    dash_app.layout = html.Div([
        html.H2("Line Graph - Monthly Usage"),
        dcc.Graph(id='usage-graph', figure=get_usage_figure()),

        html.H2("Bar Graph - Total Monthly Usage"),
        dcc.Graph(id='total-usage-graph', figure=get_total_usage_figure()),
        
        html.Div("Search an MSISDN from Flask '/' and come back to see chart.")
    ])

    return dash_app
