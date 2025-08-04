import pandas as pd
import os

def load_lte_utilization_data():
    """Load LTE Utilization data from Excel file"""
    try:
        data_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_files'))
        file_path = os.path.join(data_files_dir, 'LTE Utilization Report - June v2.xlsx')
        
        if not os.path.exists(file_path):
            return None
            
        df = pd.read_excel(file_path, sheet_name='LTE Utilization Report')
        
        # Clean column names
        df.columns = [col.strip() if isinstance(col, str) else col for col in df.columns]
        
        return df
    except Exception as e:
        print(f"Error loading LTE utilization data: {e}")
        return None

def get_lte_utilization_by_site_id(site_id, lte_df=None):
    """Get LTE utilization data for a specific Site ID"""
    if lte_df is None:
        lte_df = load_lte_utilization_data()
    
    if lte_df is None:
        return []
    
    # Filter by Site ID
    site_data = lte_df[lte_df['Site ID'] == site_id]
    
    if site_data.empty:
        return []
    
    # Select relevant columns for display
    columns_to_include = [
        'Cell ID', 'Sector ID', 'Site Name', 'Site ID',
        'Sector Utilization (%)', 'Cell Utilization (%)',
        'Cell DL Average thoughput BH (Mbps)', 'Cell UL Average thoughput BH (Mbps)',
        'Radio resource usage BH (DL) %'
    ]
    
    # Only include columns that exist in the dataframe
    available_columns = [col for col in columns_to_include if col in site_data.columns]
    result_data = site_data[available_columns]
    
    # Convert to dictionary records and handle NaN values
    records = []
    for _, row in result_data.iterrows():
        record = {}
        for col in available_columns:
            value = row[col]
            # Handle NaN values
            if pd.isna(value):
                record[col] = None
            elif isinstance(value, (int, float)):
                record[col] = float(value) if not pd.isna(value) else None
            else:
                record[col] = str(value)
        records.append(record)
    
    return records

def get_lte_utilization_by_cell_code(cell_code, lte_df=None):
    """Get LTE utilization data for a specific Cell Code (Cell ID)"""
    if lte_df is None:
        lte_df = load_lte_utilization_data()
    
    if lte_df is None:
        return []
    
    # Filter by Cell ID (which contains the cell code)
    cell_data = lte_df[lte_df['Cell ID'].str.contains(str(cell_code), na=False)]
    
    if cell_data.empty:
        return []
    
    # Select relevant columns for display
    columns_to_include = [
        'Cell ID', 'Sector ID', 'Site Name', 'Site ID',
        'Sector Utilization (%)', 'Cell Utilization (%)',
        'Cell DL Average thoughput BH (Mbps)', 'Cell UL Average thoughput BH (Mbps)',
        'Radio resource usage BH (DL) %'
    ]
    
    # Only include columns that exist in the dataframe
    available_columns = [col for col in columns_to_include if col in cell_data.columns]
    result_data = cell_data[available_columns]
    
    # Convert to dictionary records and handle NaN values
    records = []
    for _, row in result_data.iterrows():
        record = {}
        for col in available_columns:
            value = row[col]
            # Handle NaN values
            if pd.isna(value):
                record[col] = None
            elif isinstance(value, (int, float)):
                record[col] = float(value) if not pd.isna(value) else None
            else:
                record[col] = str(value)
        records.append(record)
    
    return records

def get_all_lte_utilization_data(filters=None, sort_by=None, sort_order='asc'):
    """Get all LTE utilization data with optional filtering and sorting"""
    lte_df = load_lte_utilization_data()
    
    if lte_df is None:
        return []
    
    # Apply filters if provided
    if filters:
        for column, value in filters.items():
            if value and column in lte_df.columns:
                if lte_df[column].dtype == 'object':
                    # String filtering (case-insensitive contains)
                    lte_df = lte_df[lte_df[column].str.contains(str(value), na=False, case=False)]
                else:
                    # Numeric filtering (exact match or range if needed)
                    try:
                        numeric_value = float(value)
                        lte_df = lte_df[lte_df[column] == numeric_value]
                    except ValueError:
                        continue
    
    # Apply sorting if provided
    if sort_by and sort_by in lte_df.columns:
        ascending = sort_order.lower() == 'asc'
        lte_df = lte_df.sort_values(by=sort_by, ascending=ascending)
    
    # Select relevant columns for display
    columns_to_include = [
        'Cell ID', 'Sector ID', 'Site Name', 'Site ID', 'District', 'Region',
        'Sector Utilization (%)', 'Cell Utilization (%)',
        'Cell DL Average thoughput BH (Mbps)', 'Cell UL Average thoughput BH (Mbps)',
        'Radio resource usage BH (DL) %'
    ]
    
    # Only include columns that exist in the dataframe
    available_columns = [col for col in columns_to_include if col in lte_df.columns]
    result_data = lte_df[available_columns]
    
    # Convert to dictionary records and handle NaN values
    records = []
    for _, row in result_data.iterrows():
        record = {}
        for col in available_columns:
            value = row[col]
            # Handle NaN values
            if pd.isna(value):
                record[col] = None
            elif isinstance(value, (int, float)):
                record[col] = float(value) if not pd.isna(value) else None
            else:
                record[col] = str(value)
        records.append(record)
    
    return records

def get_lte_utilization_summary():
    """Get summary statistics for LTE utilization data"""
    lte_df = load_lte_utilization_data()
    
    if lte_df is None:
        return {}
    
    summary = {}
    
    try:
        # Basic counts
        summary['total_cells'] = len(lte_df)
        summary['total_sites'] = lte_df['Site ID'].nunique()
        summary['total_sectors'] = lte_df['Sector ID'].nunique()
        
        # Utilization statistics
        if 'Sector Utilization (%)' in lte_df.columns:
            sector_util = lte_df['Sector Utilization (%)'].dropna()
            summary['avg_sector_utilization'] = float(sector_util.mean()) if not sector_util.empty else None
            summary['max_sector_utilization'] = float(sector_util.max()) if not sector_util.empty else None
        
        if 'Cell Utilization (%)' in lte_df.columns:
            cell_util = lte_df['Cell Utilization (%)'].dropna()
            summary['avg_cell_utilization'] = float(cell_util.mean()) if not cell_util.empty else None
            summary['max_cell_utilization'] = float(cell_util.max()) if not cell_util.empty else None
        
        # Throughput statistics
        if 'Cell DL Average thoughput BH (Mbps)' in lte_df.columns:
            dl_throughput = lte_df['Cell DL Average thoughput BH (Mbps)'].dropna()
            summary['avg_dl_throughput'] = float(dl_throughput.mean()) if not dl_throughput.empty else None
        
        if 'Cell UL Average thoughput BH (Mbps)' in lte_df.columns:
            ul_throughput = lte_df['Cell UL Average thoughput BH (Mbps)'].dropna()
            summary['avg_ul_throughput'] = float(ul_throughput.mean()) if not ul_throughput.empty else None
            
    except Exception as e:
        print(f"Error calculating LTE utilization summary: {e}")
    
    return summary