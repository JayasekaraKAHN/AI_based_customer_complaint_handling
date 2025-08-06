from transformers import pipeline
import numpy as np

def format_rsrp_summary_for_overview(rsrp_data_list, title="RSRP Signal Quality"):
    """Format RSRP data to display summary row for <=2 sites, individual rows for >2 sites"""
    if not rsrp_data_list:
        return {
            'title': title,
            'display_type': 'summary',
            'summary_row': {
                'Site_Name': 'No Data Available',
                'Site_ID': 'N/A',
                'Signal Quality': 'No Signal Data',
                'Signal_Quality_Percentage': '0%',
                'Good_Signal_Avg': '0.0%'
            },
            'individual_rows': [],
            'total_sites': 0,
            'good_count': 0,
            'poor_count': 0
        }
    
    # Count good and poor signals
    good_count = 0
    poor_count = 0
    all_site_names = []
    all_site_ids = []
    individual_rows = []
    total_good_signal_avg = 0.0
    
    for rsrp_entry in rsrp_data_list:
        signal_quality = rsrp_entry.get('Signal Quality', 'Unknown')
        site_name = rsrp_entry.get('Site_Name', 'Unknown Site')
        site_id = rsrp_entry.get('Site_ID', 'Unknown')
        good_signal_avg = rsrp_entry.get('Good Signal Avg (Range 1+2) %', 0.0)
        
        if signal_quality == "Good":
            good_count += 1
        else:
            poor_count += 1
            
        if site_name not in all_site_names:
            all_site_names.append(site_name)
        if site_id not in all_site_ids:
            all_site_ids.append(site_id)
        
        # Accumulate good signal average
        total_good_signal_avg += float(good_signal_avg) if good_signal_avg else 0.0
        
        # Create individual row for each entry
        individual_rows.append({
            'Site_Name': site_name,
            'Site_ID': site_id,
            'Signal Quality': signal_quality,
            'Signal_Quality_Percentage': f"{(1/len(rsrp_data_list) * 100):.1f}%",
            'Good_Signal_Avg': f"{float(good_signal_avg) if good_signal_avg else 0.0:.1f}%"
        })
    
    total_sites = len(rsrp_data_list)
    unique_sites = len(all_site_names)
    
    # Calculate overall good signal average
    overall_good_signal_avg = total_good_signal_avg / total_sites if total_sites > 0 else 0.0
    
    # Determine display type: if more than 2 unique sites, show individual rows
    if unique_sites > 2:
        return {
            'title': title,
            'display_type': 'individual',
            'summary_row': None,
            'individual_rows': individual_rows,
            'total_sites': total_sites,
            'unique_sites': unique_sites,
            'good_count': good_count,
            'poor_count': poor_count,
            'overall_good_signal_avg': f"{overall_good_signal_avg:.1f}%"
        }
    
    # For 2 or fewer sites, show summary
    if len(all_site_names) == 1:
        site_name_summary = all_site_names[0]
    else:
        site_name_summary = f"{len(all_site_names)} Sites"
    
    if len(all_site_ids) == 1:
        site_id_summary = all_site_ids[0]
    else:
        site_id_summary = f"{len(all_site_ids)} Site IDs"
    
    # Determine overall signal quality and percentage
    if good_count > poor_count:
        overall_quality = "Mostly Good"
        quality_percentage = f"{(good_count/total_sites * 100):.1f}%"
    elif poor_count > good_count:
        overall_quality = "Mostly Poor"
        quality_percentage = f"{(poor_count/total_sites * 100):.1f}%"
    elif good_count == poor_count and good_count > 0:
        overall_quality = "Mixed Quality"
        quality_percentage = "50%"
    else:
        overall_quality = "Unknown"
        quality_percentage = "0%"
    
    # Create single summary row
    summary_row = {
        'Site_Name': site_name_summary,
        'Site_ID': site_id_summary,
        'Signal Quality': overall_quality,
        'Signal_Quality_Percentage': quality_percentage,
        'Good_Signal_Avg': f"{overall_good_signal_avg:.1f}%"
    }
    
    return {
        'title': title,
        'display_type': 'summary',
        'summary_row': summary_row,
        'individual_rows': individual_rows,
        'total_sites': total_sites,
        'unique_sites': unique_sites,
        'good_count': good_count,
        'poor_count': poor_count,
        'overall_good_signal_avg': f"{overall_good_signal_avg:.1f}%"
    }

# --- Rule-Based Pattern Analysis ---
def rule_based_pattern_analysis(user_metrics):
    monthly_usage = user_metrics.get('Monthly Usage', {})
    months = monthly_usage.get('months', [])
    total_usage = monthly_usage.get('Total', [])
    outgoing_voice = monthly_usage.get('outgoing_voice', [])
    incoming_voice = monthly_usage.get('incoming_voice', [])
    outgoing_sms = monthly_usage.get('outgoing_sms', [])
    incoming_sms = monthly_usage.get('incoming_sms', [])
    device = f"{user_metrics.get('Brand', 'Unknown')} {user_metrics.get('Model', 'Unknown')}"
    location = f"{user_metrics.get('District', 'Unknown')} district, {user_metrics.get('Region', 'Unknown')} region"

    suggestions = []
    patterns = []

    # Detect high/low usage
    if total_usage:
        avg_usage = np.mean(total_usage)
        max_usage = max(total_usage)
        min_usage = min(total_usage)
        if max_usage > avg_usage:
            patterns.append("Significant spike in data usage detected in some months.")
        if min_usage < avg_usage:
            patterns.append("Some months show very low data usage.")
        if avg_usage > 1000:
            suggestions.append("Consider a higher data plan to save costs.")
        elif avg_usage < 500:
            suggestions.append("Current plan may be more than needed; consider downgrading.")

    # Detect voice/SMS patterns
    total_voice = sum(outgoing_voice) + sum(incoming_voice)
    total_sms = sum(outgoing_sms) + sum(incoming_sms)
    if total_voice > 5000:
        patterns.append("Heavy voice call activity detected.")
    if total_sms > 500:
        patterns.append("Frequent SMS usage detected.")
    if total_voice < 100 and total_sms < 50:
        patterns.append("Low voice and SMS activity.")

    # Voice usage trend analysis
    voice_monthly = [
        (outgoing_voice[i] if i < len(outgoing_voice) else 0) + (incoming_voice[i] if i < len(incoming_voice) else 0)
        for i in range(len(months))
    ]
    if len(voice_monthly) >= 2:
        diffs = [voice_monthly[i+1] - voice_monthly[i] for i in range(len(voice_monthly)-1)]
        voice_pattern = None
        if all(d > 0 for d in diffs):
            voice_pattern = "Voice usage is consistently increasing month over month."
        elif all(d < 0 for d in diffs):
            voice_pattern = "Voice usage is consistently decreasing month over month."
        elif all(abs(d) < 10 for d in diffs):
            voice_pattern = "Voice usage is stable across months."
        else:
            max_increase = max(diffs)
            max_decrease = min(diffs)
            if max_increase > 100:
                voice_pattern = "Significant increase in voice usage detected in some months."
            elif max_decrease < -100:
                voice_pattern = "Significant decrease in voice usage detected in some months."
        if voice_pattern:
            patterns.append(voice_pattern)

    # Device age
    year_released = user_metrics.get('Year Released', None)
    if year_released and str(year_released).isdigit():
        try:
            year_released = int(year_released)
            if year_released < 2022:
                suggestions.append("Consider upgrading to a newer device for better performance and features.")
        except Exception:
            pass

    return {
        'patterns': patterns,
        'suggestions': suggestions
    }

# --- Personalized Recommendation Engine (Placeholder) ---
def personalized_recommendations(user_metrics):
    return ["Try Mobitel's new Unlimited Data Plan for heavy users!", "Upgrade to a 5G device for better speeds."]

# --- LLM-Based Summarization ---
def generate_overall_msisdn_summary(user_metrics, summarizer=None):
    if summarizer is None:
        return "AI summarizer not available. Please check model installation."

    msisdn = user_metrics.get('MSISDN', 'Unknown')
    brand = user_metrics.get('Brand', 'Unknown')
    model = user_metrics.get('Model', 'Unknown')
    district = user_metrics.get('District', 'Unknown')
    region = user_metrics.get('Region', 'Unknown')
    monthly_usage = user_metrics.get('Monthly Usage', {})
    months = monthly_usage.get('months', [])
    total_usage = monthly_usage.get('Total', [])
    sim_type = user_metrics.get('SIM Type', 'Unknown')
    connection_type = user_metrics.get('Connection Type', 'Unknown')
    year_released = user_metrics.get('Year Released', 'Unknown')
    device_type = user_metrics.get('Device Type', 'Unknown')
    volte = user_metrics.get('VoLTE', 'Unknown')
    technology = user_metrics.get('Technology', 'Unknown')
    tac = user_metrics.get('TAC', 'Unknown')
    imei = user_metrics.get('IMEI', 'Unknown')
    imsi = user_metrics.get('IMSI', 'Unknown')
    sitename = user_metrics.get('Sitename', 'Unknown')
    cellcode = user_metrics.get('Cellcode', 'Unknown')
    lon = user_metrics.get('Lon', 'Unknown')
    lat = user_metrics.get('Lat', 'Unknown')
    os_name = user_metrics.get('OS', 'Unknown')
    marketing_name = user_metrics.get('Marketing Name', 'Unknown')
    primary_hardware_type = user_metrics.get('Primary Hardware Type', 'Unknown')

    # Build a more detailed, readable, point-wise usage summary
    usage_lines = []
    for m, t in zip(months, total_usage):
        usage_lines.append(f"- {m}: {t} MB data usage")
    usage_str = "\n".join(usage_lines) if usage_lines else "No usage data."

    outgoing_voice = monthly_usage.get('outgoing_voice', [])
    incoming_voice = monthly_usage.get('incoming_voice', [])
    outgoing_sms = monthly_usage.get('outgoing_sms', [])
    incoming_sms = monthly_usage.get('incoming_sms', [])

    voice_sms_lines = []
    for i, m in enumerate(months):
        voice = (outgoing_voice[i] if i < len(outgoing_voice) else 0) + (incoming_voice[i] if i < len(incoming_voice) else 0)
        sms = (outgoing_sms[i] if i < len(outgoing_sms) else 0) + (incoming_sms[i] if i < len(incoming_sms) else 0)
        voice_sms_lines.append(f"- {m}: {voice} mins voice, {sms} SMS")
    voice_sms_str = "\n".join(voice_sms_lines) if voice_sms_lines else "No voice/SMS data."

    # Get RSRP data for signal quality analysis
    rsrp_data = user_metrics.get('RSRP Data', [])
    common_locations = user_metrics.get('Common Cell Locations', [])

    # Format RSRP data for overview display
    recent_rsrp_summary = format_rsrp_summary_for_overview(rsrp_data, "Recent Location RSRP")
    
    # Process common locations RSRP data
    all_common_rsrp = []
    if common_locations:
        for loc in common_locations:
            loc_rsrp_data = loc.get('RSRP_DATA', [])
            all_common_rsrp.extend(loc_rsrp_data)
    
    common_rsrp_summary = format_rsrp_summary_for_overview(all_common_rsrp, "Common Locations RSRP")
    
    # Store formatted RSRP summaries in user_metrics for template access
    user_metrics['formatted_recent_rsrp'] = recent_rsrp_summary
    user_metrics['formatted_common_rsrp'] = common_rsrp_summary

    # --- Detailed MSISDN Data Section ---
    details_section = (
        f"\n==============================\n"
        f" MSISDN Detailed Data\n"
        f"==============================\n"
        f"Mobile Number      : {msisdn}\n"
        f"IMSI              : {imsi}\n"
        f"IMEI              : {imei}\n"
        f"SIM Type          : {sim_type}\n"
        f"Connection Type   : {connection_type}\n"
        f"Device            : {brand} {model} ({marketing_name})\n"
        f"OS                : {os_name}\n"
        f"Year Released     : {year_released}\n"
        f"Device Type       : {device_type}\n"
        f"VoLTE             : {volte}\n"
        f"Technology        : {technology}\n"
        f"Primary HW Type   : {primary_hardware_type}\n"
        f"TAC               : {tac}\n"
        f"Location          : {district} district, {region} region\n"
        f"Site Name         : {sitename}\n"
        f"Cell Code         : {cellcode}\n"
        f"Coordinates       : {lat}, {lon}\n"
        f"\n------------------------------\n"
        f" Monthly Usage Summary\n"
        f"------------------------------\n"
        f"Data Usage (MB) per Month:\n"
        + ("\n".join([f"  • {m}: {t} MB" for m, t in zip(months, total_usage)]) if months and total_usage else "  • No usage data.")
        + "\n\nVoice & SMS Activity per Month:\n"
        + ("\n".join([f"  • {m}: {voice} mins voice, {sms} SMS" for m, voice, sms in zip(months, [(outgoing_voice[i] if i < len(outgoing_voice) else 0) + (incoming_voice[i] if i < len(incoming_voice) else 0) for i in range(len(months))], [(outgoing_sms[i] if i < len(outgoing_sms) else 0) + (incoming_sms[i] if i < len(incoming_sms) else 0) for i in range(len(months))])]) if months else "  • No voice/SMS data.")
        + "\n==============================\n"
    )

    # --- Rule-based analysis ---
    rule_results = rule_based_pattern_analysis(user_metrics)
    patterns = rule_results['patterns']
    suggestions = rule_results['suggestions']

    # --- Personalized recommendations ---
    recs = personalized_recommendations(user_metrics)

    # Compose a richer prompt for the LLM, explicitly requesting pattern analysis and suggestions
    prompt = (
        f"\n"
        f"Patterns detected:\n" + ("\n".join(f"- {p}" for p in patterns) if patterns else "- None detected.") + "\n"
        f"Suggestions:\n" + ("\n".join(f"- {s}" for s in suggestions) if suggestions else "- None.") + "\n"
        f"Personalized Recommendations:\n" + ("\n".join(f"- {r}" for r in recs) if recs else "- None.")
    )

    try:
        # Handle different types of summarizers
        if summarizer == "basic":
            # Basic text summarization without AI model
            basic_summary = generate_basic_summary(user_metrics, patterns, suggestions, recs)
            return details_section + "\n" + basic_summary
        elif hasattr(summarizer, '__call__'):
            # AI model summarization
            result = summarizer(prompt, max_length=180, min_length=40, do_sample=False)
            combined_summary = (
                details_section + "\n"
                + result[0]['summary_text']
                + ("\n".join(
                    f"- {p}" for p in patterns
                    if p not in [
                        "Significant spike in data usage detected in some months.",
                        "Some months show very low data usage.",
                        "Heavy voice call activity detected.",
                        "Frequent SMS usage detected.",
                        "Significant increase in voice usage detected in some months."
                    ]
                ) if patterns else "- None detected.")
            )
            return combined_summary
        else:
            # Fallback to basic summary
            basic_summary = generate_basic_summary(user_metrics, patterns, suggestions, recs)
            return details_section + "\n" + basic_summary
            
    except Exception as e:
        print(f"[AI Summary] Error during summarization: {e}")
        # Fallback to basic summary
        basic_summary = generate_basic_summary(user_metrics, patterns, suggestions, recs)
        return details_section + "\n" + basic_summary

def generate_basic_summary(user_metrics, patterns, suggestions, recs):
    """Generate a basic text summary without AI model"""
    msisdn = user_metrics.get('MSISDN', 'Unknown')
    monthly_usage = user_metrics.get('Monthly Usage', {})
    total_usage = monthly_usage.get('Total', [])
    
    # Calculate average usage
    avg_usage = sum(total_usage) / len(total_usage) if total_usage else 0
    
    summary_parts = []
    summary_parts.append(f"📊 Usage Analysis for {msisdn}")
    
    if avg_usage > 0:
        if avg_usage > 5000:
            summary_parts.append("🔥 High data usage detected - Heavy user profile")
        elif avg_usage > 1000:
            summary_parts.append("📈 Moderate data usage - Regular user profile")
        else:
            summary_parts.append("📱 Light data usage - Basic user profile")
    
    if patterns:
        summary_parts.append(f"📋 Key Patterns: {', '.join(patterns[:3])}")
    
    if suggestions:
        summary_parts.append(f"💡 Recommendations: {', '.join(suggestions[:2])}")
    
    if recs:
        summary_parts.append(f"🎯 Personalized Tips: {', '.join(recs[:2])}")
    
    return "\n".join(summary_parts)
    
    # Store formatted RSRP summaries in user_metrics for template access
    user_metrics['formatted_recent_rsrp'] = recent_rsrp_summary
    user_metrics['formatted_common_rsrp'] = common_rsrp_summary

    # --- Detailed MSISDN Data Section ---
    details_section = (
        f"\n==============================\n"
        f" MSISDN Detailed Data\n"
        f"==============================\n"
        f"Mobile Number      : {msisdn}\n"
        f"IMSI              : {imsi}\n"
        f"IMEI              : {imei}\n"
        f"SIM Type          : {sim_type}\n"
        f"Connection Type   : {connection_type}\n"
        f"Device            : {brand} {model} ({marketing_name})\n"
        f"OS                : {os_name}\n"
        f"Year Released     : {year_released}\n"
        f"Device Type       : {device_type}\n"
        f"VoLTE             : {volte}\n"
        f"Technology        : {technology}\n"
        f"Primary HW Type   : {primary_hardware_type}\n"
        f"TAC               : {tac}\n"
        f"Location          : {district} district, {region} region\n"
        f"Site Name         : {sitename}\n"
        f"Cell Code         : {cellcode}\n"
        f"Coordinates       : {lat}, {lon}\n"
        f"\n------------------------------\n"
        f" Monthly Usage Summary\n"
        f"------------------------------\n"
        f"Data Usage (MB) per Month:\n"
        + ("\n".join([f"  • {m}: {t} MB" for m, t in zip(months, total_usage)]) if months and total_usage else "  • No usage data.")
        + "\n\nVoice & SMS Activity per Month:\n"
        + ("\n".join([f"  • {m}: {voice} mins voice, {sms} SMS" for m, voice, sms in zip(months, [(outgoing_voice[i] if i < len(outgoing_voice) else 0) + (incoming_voice[i] if i < len(incoming_voice) else 0) for i in range(len(months))], [(outgoing_sms[i] if i < len(outgoing_sms) else 0) + (incoming_sms[i] if i < len(incoming_sms) else 0) for i in range(len(months))])]) if months else "  • No voice/SMS data.")
        + "\n==============================\n"
    )

    # --- Rule-based analysis ---
    rule_results = rule_based_pattern_analysis(user_metrics)
    patterns = rule_results['patterns']
    suggestions = rule_results['suggestions']

    # --- Personalized recommendations ---
    recs = personalized_recommendations(user_metrics)

    # Compose a richer prompt for the LLM, explicitly requesting pattern analysis and suggestions
    prompt = (
        f"\n"
        f"Patterns detected:\n" + ("\n".join(f"- {p}" for p in patterns) if patterns else "- None detected.") + "\n"
        f"Suggestions:\n" + ("\n".join(f"- {s}" for s in suggestions) if suggestions else "- None.") + "\n"
        f"Personalized Recommendations:\n" + ("\n".join(f"- {r}" for r in recs) if recs else "- None.")
    )

    try:
        result = summarizer(prompt, max_length=180, min_length=40, do_sample=False)
        combined_summary = (
            details_section + "\n"
            + result[0]['summary_text']
            + ("\n".join(
                f"- {p}" for p in patterns
                if p not in [
                    "Significant spike in data usage detected in some months.",
                    "Some months show very low data usage.",
                    "Heavy voice call activity detected.",
                    "Frequent SMS usage detected.",
                    "Significant increase in voice usage detected in some months."
                ]
            ) if patterns else "- None detected.")
        )
        return combined_summary
    except Exception as e:
        return f"[AI Summary Error] {e}"
