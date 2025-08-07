/**
 * Usage Charts using Chart.js (replaces Plotly.js for smaller bundle size)
 * Provides the same functionality as before but with Chart.js
 */
class UsageCharts {
  constructor(usageData) {
    this.usage = usageData;
    this.charts = {}; // Store chart instances for cleanup
    this.initializeCharts();
  }

  initializeCharts() {
    this.createMonthlyUsageChart();
    this.createTotalUsageChart();
    this.createVoiceUsageChart();
    this.createSMSUsageChart();
  }

  // Destroy existing charts before creating new ones
  destroyCharts() {
    Object.values(this.charts).forEach(chart => {
      if (chart) chart.destroy();
    });
    this.charts = {};
  }

  createMonthlyUsageChart() {
    const ctx = document.getElementById('monthlyVolumeChart').getContext('2d');
    
    // Convert usage data from MB to GB for network usage chart
    const datasets = ["2G", "3G", "4G", "5G"].map((network, index) => {
      const colors = [
        'rgba(255, 99, 132, 0.8)',
        'rgba(54, 162, 235, 0.8)', 
        'rgba(255, 206, 86, 0.8)',
        'rgba(75, 192, 192, 0.8)'
      ];
      
      return {
        label: network,
        data: this.usage[network] ? this.usage[network].map(mb => +(mb / 1024).toFixed(2)) : [],
        borderColor: colors[index],
        backgroundColor: colors[index].replace('0.8', '0.2'),
        borderWidth: 2,
        fill: false,
        tension: 0.1
      };
    });

    this.charts.monthlyUsage = new Chart(ctx, {
      type: 'line',
      data: {
        labels: this.usage.months || [],
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 2,
        plugins: {
          title: {
            display: true,
            text: 'Monthly Data Usage by Network Type',
            font: {
              size: 16
            }
          },
          legend: {
            display: true,
            position: 'top'
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Usage (GB)'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Month'
            }
          }
        }
      }
    });
  }

  createTotalUsageChart() {
    const ctx = document.getElementById('totalVolumeChart').getContext('2d');
    
    // Create Total Usage Bar Chart (like the original implementation)
    const totalUsageData = this.usage.Total ? this.usage.Total.map(mb => +(mb / 1024).toFixed(2)) : [];
    
    this.charts.totalUsage = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: this.usage.months || [],
        datasets: [{
          label: 'Total Usage',
          data: totalUsageData,
          backgroundColor: 'rgba(54, 162, 235, 0.6)',
          borderColor: 'rgba(54, 162, 235, 1)',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1.5,
        plugins: {
          title: {
            display: true,
            text: 'Total Monthly Data Usage',
            font: {
              size: 16
            }
          },
          legend: {
            display: true,
            position: 'top'
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Total Usage (GB)'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Month'
            }
          }
        }
      }
    });
  }

  createVoiceUsageChart() {
    const ctx = document.getElementById('voiceUsageChart').getContext('2d');
    
    // Create Voice Usage Line Chart (like the original implementation)
    const voiceDatasets = [];
    
    if (this.usage.incoming_voice) {
      voiceDatasets.push({
        label: 'Incoming Voice',
        data: this.usage.incoming_voice,
        borderColor: 'rgba(255, 99, 132, 1)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      });
    }
    
    if (this.usage.outgoing_voice) {
      voiceDatasets.push({
        label: 'Outgoing Voice',
        data: this.usage.outgoing_voice,
        borderColor: 'rgba(54, 162, 235, 1)',
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      });
    }
    
    this.charts.voiceUsage = new Chart(ctx, {
      type: 'line',
      data: {
        labels: this.usage.months || [],
        datasets: voiceDatasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 2,
        plugins: {
          title: {
            display: true,
            text: 'Monthly Incoming & Outgoing Voice Usage',
            font: {
              size: 16
            }
          },
          legend: {
            display: true,
            position: 'top'
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Voice Minutes'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Month'
            }
          }
        }
      }
    });
  }

  createSMSUsageChart() {
    const ctx = document.getElementById('smsUsageChart').getContext('2d');
    
    // Create SMS Usage Line Chart (like the original implementation)
    const smsDatasets = [];
    
    if (this.usage.incoming_sms) {
      smsDatasets.push({
        label: 'Incoming SMS',
        data: this.usage.incoming_sms,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      });
    }
    
    if (this.usage.outgoing_sms) {
      smsDatasets.push({
        label: 'Outgoing SMS',
        data: this.usage.outgoing_sms,
        borderColor: 'rgba(255, 206, 86, 1)',
        backgroundColor: 'rgba(255, 206, 86, 0.2)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      });
    }
    
    this.charts.smsUsage = new Chart(ctx, {
      type: 'line',
      data: {
        labels: this.usage.months || [],
        datasets: smsDatasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 2,
        plugins: {
          title: {
            display: true,
            text: 'Monthly Incoming & Outgoing SMS Usage',
            font: {
              size: 16
            }
          },
          legend: {
            display: true,
            position: 'top'
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'SMS Count'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Month'
            }
          }
        }
      }
    });
  }
}

// Global function to initialize charts (called from index.html)
function initializeUsageCharts(usageData) {
  try {
    // Destroy existing charts if they exist
    if (window.usageChartsInstance) {
      window.usageChartsInstance.destroyCharts();
    }
    
    // Create new charts instance
    window.usageChartsInstance = new UsageCharts(usageData);
    console.log('Charts initialized successfully with Chart.js');
  } catch (error) {
    console.error('Error initializing charts:', error);
  }
}

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { UsageCharts, initializeUsageCharts };
}
