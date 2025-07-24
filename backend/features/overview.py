from transformers import pipeline
import numpy as np

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
