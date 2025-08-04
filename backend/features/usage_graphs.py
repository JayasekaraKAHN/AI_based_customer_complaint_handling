from dash import Dash, html, dcc
import plotly.graph_objs as go

def create_dash_app(server, latest_result, url_base_pathname='/usage-graph/'):
    dash_app = Dash(__name__, server=server, url_base_pathname=url_base_pathname)

    #data usage by network
    def get_usage_figure():
        if not latest_result.get("Monthly Usage"):
            # Create an empty figure with a message when no data is available
            fig = go.Figure()
            fig.add_annotation(
                text="No data available. Please search for an MSISDN first.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            fig.update_layout(
                title="Monthly Usage by Network Type - No Data",
                xaxis_title="Month", 
                yaxis_title="Usage (GB)",
                template="plotly_white",
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False)
            )
            return fig
        
        usage = latest_result["Monthly Usage"]
        
        fig = go.Figure()
        for tech in ["2G", "3G", "4G", "5G"]:
            if tech in usage and usage[tech]:  # Check if tech exists and has data
                # Convert MB to GB by dividing by 1024 and round to 2 decimal places
                usage_gb = [round(mb / 1024, 2) for mb in usage[tech]]
                fig.add_trace(go.Scatter(x=usage["months"], y=usage_gb,
                                         mode='lines+markers', name=tech))
        
        fig.update_layout(title="Monthly Usage by Network Type",
                          xaxis_title="Month", yaxis_title="Usage (GB)",
                          template="plotly_white",
                          yaxis=dict(tickformat='.2f'))
        return fig

    #total data usage
    def get_total_usage_figure():
        if not latest_result.get("Monthly Usage"):
            # Create an empty figure with a message when no data is available
            fig = go.Figure()
            fig.add_annotation(
                text="No data available. Please search for an MSISDN first.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            fig.update_layout(
                title="Total Monthly Usage - No Data",
                xaxis_title="Month", 
                yaxis_title="Total Usage (GB)",
                template="plotly_white",
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False)
            )
            return fig
        
        usage = latest_result["Monthly Usage"]
        
        fig = go.Figure()
        if "Total" in usage and usage["Total"]:  # Check if Total exists and has data
            # Convert MB to GB by dividing by 1024 and round to 2 decimal places
            total_usage_gb = [round(mb / 1024, 2) for mb in usage["Total"]]
            fig.add_trace(go.Bar(x=usage["months"], y=total_usage_gb, name="Total Usage"))
        
        fig.update_layout(title="Total Monthly Usage",
                          xaxis_title="Month", yaxis_title="Total Usage (GB)",
                          template="plotly_white",
                          yaxis=dict(tickformat='.2f'))
        return fig
    
    #voice usage
    def get_voice_usage_figure():
        if not latest_result.get("Monthly Usage"):
            # Create an empty figure with a message when no data is available
            fig = go.Figure()
            fig.add_annotation(
                text="No data available. Please search for an MSISDN first.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            fig.update_layout(
                title="Monthly Incoming & Outgoing Calls - No Data",
                xaxis_title="Month", 
                yaxis_title="Call Duration (Minutes)",
                template="plotly_white",
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False)
            )
            return fig
        
        usage = latest_result["Monthly Usage"]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=usage["months"], y=usage["incoming_voice"],
                             mode='lines+markers', name="Incoming Voice"))
        fig.add_trace(go.Scatter(x=usage["months"], y=usage["outgoing_voice"],
                             mode='lines+markers', name="Outgoing Voice"))

        fig.update_layout(title="Monthly Incoming & Outgoing Voice Usage",
                      xaxis_title="Month", yaxis_title="Voice Minutes",
                      template="plotly_white")
        return fig
    
    #sms usage
    def get_sms_Usage_figure():
        if not latest_result.get("Monthly Usage"):
            # Create an empty figure with a message when no data is available
            fig = go.Figure()
            fig.add_annotation(
                text="No data available. Please search for an MSISDN first.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            fig.update_layout(
                title="Monthly Incoming & Outgoing SMS Usage - No Data",
                xaxis_title="Month", 
                yaxis_title="SMS Count",
                template="plotly_white",
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False)
            )
            return fig
        
        usage = latest_result["Monthly Usage"]
        
        fig = go.Figure()
        if "incoming_sms" in usage and usage["incoming_sms"]:  # Check if SMS data exists
            fig.add_trace(go.Scatter(x=usage["months"], y=usage["incoming_sms"],
                                     mode='lines+markers', name="Incoming SMS"))
        if "outgoing_sms" in usage and usage["outgoing_sms"]:  # Check if SMS data exists
            fig.add_trace(go.Scatter(x=usage["months"], y=usage["outgoing_sms"],
                                    mode='lines+markers', name="Outgoing SMS"))
        
        fig.update_layout(title="Monthly Incoming & Outgoing SMS Usage",
                          xaxis_title="Month", yaxis_title="SMS Count",
                          template="plotly_white")
        return fig

    dash_app.layout = html.Div([
        html.Div([
            html.H1("📊 Usage Analytics Dashboard", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),
            html.Div([
                html.P("📋 Instructions:", style={'fontWeight': 'bold', 'color': '#34495e'}),
                html.Ol([
                    html.Li("Go to the main application at http://127.0.0.1:5000/"),
                    html.Li("Log in with credentials (admin/admin)"),
                    html.Li("Search for an MSISDN number"),
                    html.Li("Return to this page to view the usage graphs"),
                    html.Li("Data usage is displayed in GB for better readability")
                ], style={'color': '#7f8c8d'})
            ], style={
                'backgroundColor': '#ecf0f1', 
                'padding': '20px', 
                'borderRadius': '10px', 
                'marginBottom': '30px',
                'border': '1px solid #bdc3c7'
            })
        ]),
        
        html.H2("📈 Line Graph - Monthly Usage by Network Type"),
        dcc.Graph(id='usage-graph', figure=get_usage_figure()),

        html.H2("📊 Bar Graph - Total Monthly Usage"),
        dcc.Graph(id='total-usage-graph', figure=get_total_usage_figure()),

        html.H2("📞 Line Graph - Monthly Voice Usage"),
        dcc.Graph(id='voice-usage-graph', figure=get_voice_usage_figure()),

        html.H2("📱 Line Graph - Monthly SMS Usage"),
        dcc.Graph(id='sms-usage-graph', figure=get_sms_Usage_figure()),
    ], style={'margin': '20px'})

    return dash_app
