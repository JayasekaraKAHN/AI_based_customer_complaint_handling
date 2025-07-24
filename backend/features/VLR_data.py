# Add missing pandas import
import pandas as pd
#user count by site
def get_user_count(month=None, district=None, USAGE_FILES=None, VLRD=None, ref_df=None):
    df_list = []
    for m, file_info in USAGE_FILES.items():
        if month and m != month:
            continue
        df = pd.read_csv(file_info['filename'], sep="\t", dtype={"MSISDN": str})
        df.columns = [col.strip().upper() for col in df.columns]
        df["Month"] = m
        df_list.append(df)
    if not df_list or "MSISDN" not in VLRD.columns:
        return pd.DataFrame()
    usage_all = pd.concat(df_list, ignore_index=True)
    usage_all["MSISDN"] = usage_all["MSISDN"].astype(str)
    VLRD["MSISDN"] = VLRD["MSISDN"].astype(str)
    merged_df = pd.merge(usage_all, VLRD, on="MSISDN", how="inner")
    merged_df["SITE_ID"] = merged_df["CELL_CODE"].astype(str).str[:6]
    if district:
        district_upper = district.upper()
        sitename_match = ref_df[ref_df["sitename"].str.upper() == district_upper]
        if not sitename_match.empty:
            district_upper = sitename_match.iloc[0]["district"].upper()
        merged_df = merged_df[merged_df["DISTRICT"].str.upper() == district_upper]
    result_df = merged_df.groupby(['DISTRICT', 'SITE_ID'])['MSISDN'].nunique().reset_index()
    result_df.rename(columns={'MSISDN': 'User_Count'}, inplace=True)
    return result_df.sort_values(by='User_Count', ascending=False)