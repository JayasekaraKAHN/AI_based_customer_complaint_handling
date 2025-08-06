

# Required imports for mapping and HTML rendering
import folium
from folium import Map, Marker, Popup, Icon, Element

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
        <div style='width: 280px; font-family: Arial, sans-serif;'>
            <h5 style='color: #2196F3; background: #E3F2FD; padding: 8px; margin: -5px -5px 10px -5px; border-radius: 4px;'>
                📱 User Location
            </h5>
            <table style='width: 100%; font-size: 12px;'>
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
                    f"""
                    <div style='width: 200px;'>
                        <h6 style='color: #FF5722;'>Location Not Found</h6>
                        <p>Showing default Sri Lanka location</p>
                        <p><strong>MSISDN:</strong> {msisdn}</p>
                        <p><strong>Coordinates:</strong> Not available</p>
                    </div>
                    """, 
                    max_width=220
                ),
                tooltip="Location not available",
                icon=folium.Icon(color='gray', icon='question-circle', prefix='fa')
            ).add_to(map_obj)
        legend_html = f"""
        <div style='position: fixed; top: 10px; right: 10px; width: 200px; height: auto; background-color: white; border: 2px solid #ccc; z-index: 9999; font-size: 12px; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);'>
        <p style='margin: 5px 0; font-size: 10px; color: #666;'>
            <strong>District:</strong> {district}<br>
            <strong>Region:</strong> {result_data.get('Region', 'Unknown')}
        </p>
        </div>
        """
        map_obj.get_root().add_child(folium.Element(legend_html))
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
                <div style='width: 200px;'>
                    <h6 style='color: #F44336;'>Map Error</h6>
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
