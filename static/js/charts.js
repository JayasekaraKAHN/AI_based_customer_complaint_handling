class UsageCharts {
  constructor(usageData) {
    this.usage = usageData;
    this.initializeCharts();
  }

  initializeCharts() {
    this.createNetworkChart();
    this.createTotalVolumeChart();
    this.createVoiceChart();
    this.createSMSChart();
  }

  createNetworkChart() {
    // Line Chart (by network type)
    const networkTraces = ["2G", "3G", "4G", "5G"].map((net) => ({
      x: this.usage.months,
      y: this.usage[net].map(mb => +(mb / 1024).toFixed(2)),
      name: net,
      mode: "lines+markers",
      type: "scatter",
    }));

    const networkLayout = {
      title: "Monthly Data Volume by Network",
      xaxis: { title: "Month" },
      yaxis: { title: "Volume (GB)", tickformat: '.2f' },
    };

    Plotly.newPlot("monthlyVolumeChart", networkTraces, networkLayout, {
      responsive: true,
    });
  }

  createTotalVolumeChart() {
    // Bar Chart (total usage)
    const totalBarTrace = {
      x: this.usage.months,
      y: this.usage.Total.map(mb => +(mb / 1024).toFixed(2)),
      name: "Total Usage",
      type: "bar",
      marker: { color: "#007bff" },
      width: 0.5,
    };

    const totalLayout = {
      title: "Total Monthly Data Usage",
      xaxis: { title: "Month" },
      yaxis: { title: "Total Volume (GB)", tickformat: '.2f' },
    };

    Plotly.newPlot("totalVolumeChart", [totalBarTrace], totalLayout, {
      responsive: true,
    });
  }

  createVoiceChart() {
    // Voice Usage Chart
    const voiceTraces = ["incoming_voice", "outgoing_voice"].map((type) => ({
      x: this.usage.months,
      y: this.usage[type],
      name: type === "incoming_voice" ? "Incoming Voice" : "Outgoing Voice",
      mode: "lines+markers",
      type: "scatter",
    }));

    const voiceLayout = {
      title: "Monthly Voice Usage",
      xaxis: { title: "Month" },
      yaxis: { title: "Voice Usage (Minutes)" },
    };

    Plotly.newPlot("voiceUsageChart", voiceTraces, voiceLayout, {
      responsive: true,
    });
  }

  createSMSChart() {
    // SMS Usage Chart
    const smsTraces = ["incoming_sms", "outgoing_sms"].map((type) => ({
      x: this.usage.months,
      y: this.usage[type],
      name: type === "incoming_sms" ? "Incoming SMS" : "Outgoing SMS",
      mode: "lines+markers",
      type: "scatter",
    }));

    const smsLayout = {
      title: "Monthly SMS Usage",
      xaxis: { title: "Month" },
      yaxis: { title: "SMS Count" },
    };

    Plotly.newPlot("smsUsageChart", smsTraces, smsLayout, {
      responsive: true,
    });
  }
}

// Initialize charts when DOM is loaded and data is available
function initializeUsageCharts(usageData) {
  if (typeof usageData !== 'undefined' && usageData) {
    new UsageCharts(usageData);
  }
}
