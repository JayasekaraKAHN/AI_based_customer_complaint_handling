class RSRPTableManager {
  constructor() {
    this.rsrpFilterTimeout = null;
    this.commonRsrpFilterTimeout = null;
    this.initializeEventListeners();
  }

  initializeEventListeners() {}

  // Debounced filtering functions
  debounceRsrpFilter() {
    clearTimeout(this.rsrpFilterTimeout);
    this.rsrpFilterTimeout = setTimeout(() => {
      this.applyRsrpFilters();
    }, 200);
  }

  debounceCommonRsrpFilter() {
    clearTimeout(this.commonRsrpFilterTimeout);
    this.commonRsrpFilterTimeout = setTimeout(() => {
      this.applyCommonRsrpFilters();
    }, 200);
  }

  // RSRP filtering functions
  applyRsrpFilters() {
    const form = document.getElementById('rsrpFilterForm');
    const formData = new FormData(form);

    const headerInputs = document.querySelectorAll('input[form="rsrpFilterForm"]');
    headerInputs.forEach(input => {
      if (input.value.trim()) {
        formData.set(input.name, input.value);
      }
    });

    fetch('/filter_rsrp_data', {
      method: 'POST',
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert('Error: ' + data.error);
          return;
        }

        this.updateRsrpTable(data.data);
        this.updateRsrpStatus(data.filtered_count, data.total_count);
      })
      .catch(error => {
        console.error('Error:', error);
        alert('Error filtering RSRP data');
      });
  }

  applyCommonRsrpFilters() {
    const form = document.getElementById('commonRsrpFilterForm');
    const formData = new FormData(form);

    const headerInputs = document.querySelectorAll('input[form="commonRsrpFilterForm"]');
    headerInputs.forEach(input => {
      if (input.value.trim()) {
        formData.set(input.name, input.value);
      }
    });

    fetch('/filter_common_rsrp_data', {
      method: 'POST',
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert('Error: ' + data.error);
          return;
        }

        this.updateCommonRsrpTable(data.data);
        this.updateCommonRsrpStatus(data.filtered_count, data.total_count);
      })
      .catch(error => {
        console.error('Error:', error);
        alert('Error filtering common RSRP data');
      });
  }

  // Filter clearing functions
  clearRsrpFilters() {
    const form = document.getElementById('rsrpFilterForm');
    const inputs = form.querySelectorAll('input[type="text"], input[type="number"], select');
    inputs.forEach(input => {
      if (input.name !== 'msisdn') {
        input.value = '';
      }
    });

    const headerInputs = document.querySelectorAll('input[form="rsrpFilterForm"]');
    headerInputs.forEach(input => {
      input.value = '';
    });

    location.reload();
  }

  clearCommonRsrpFilters() {
    const form = document.getElementById('commonRsrpFilterForm');
    const inputs = form.querySelectorAll('input[type="text"], input[type="number"], select');
    inputs.forEach(input => {
      if (input.name !== 'msisdn') {
        input.value = '';
      }
    });

    const headerInputs = document.querySelectorAll('input[form="commonRsrpFilterForm"]');
    headerInputs.forEach(input => {
      input.value = '';
    });

    location.reload();
  }

  // Table update functions
  updateRsrpTable(data) {
    const tbody = document.getElementById('rsrpTableBody');
    tbody.innerHTML = '';

    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted"><i class="fas fa-info-circle"></i> No RSRP data matches the current filters</td></tr>';
      this.updateRsrpStats(0, 0);
      return;
    }

    const groupedData = this.groupDataBySite(data);
    this.renderGroupedData(tbody, groupedData);
    this.updateRsrpStats(data.length, data.length);
  }

  updateCommonRsrpTable(data) {
    const tbody = document.getElementById('commonRsrpTableBody');
    tbody.innerHTML = '';

    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted"><i class="fas fa-info-circle"></i> No RSRP data matches the current filters</td></tr>';
      this.updateCommonRsrpStats(0, 0);
      return;
    }

    const groupedData = this.groupDataBySite(data);
    this.renderGroupedData(tbody, groupedData);
    this.updateCommonRsrpStats(data.length, data.length);
  }

  // Helper functions
  groupDataBySite(data) {
    const groupedData = {};
    data.forEach(row => {
      const siteName = row['Site_Name'];
      const siteId = row['Site_ID'];

      if (!groupedData[siteName]) {
        groupedData[siteName] = {};
      }
      if (!groupedData[siteName][siteId]) {
        groupedData[siteName][siteId] = [];
      }
      groupedData[siteName][siteId].push(row);
    });
    return groupedData;
  }

  renderGroupedData(tbody, groupedData) {
    Object.keys(groupedData).forEach(siteName => {
      const siteNameGroups = groupedData[siteName];
      const totalSiteNameRows = Object.values(siteNameGroups).reduce((sum, arr) => sum + arr.length, 0);
      let siteNameRowIndex = 0;

      Object.keys(siteNameGroups).forEach(siteId => {
        const siteIdRows = siteNameGroups[siteId];

        siteIdRows.forEach((row, cellIndex) => {
          const tr = document.createElement('tr');
          tr.className = 'rsrp-row';

          let html = '';

          if (siteNameRowIndex === 0) {
            html += `<td rowspan="${totalSiteNameRows}" class="rsrp-site-cell">${siteName}</td>`;
          }

          if (cellIndex === 0) {
            html += `<td rowspan="${siteIdRows.length}" class="rsrp-site-id-cell">${siteId}</td>`;
          }

          const range1 = parseFloat(row['RSRP Range 1 (>-105dBm) %']) || 0;
          const range2 = parseFloat(row['RSRP Range 2 (-105~-110dBm) %']) || 0;
          const range3 = parseFloat(row['RSRP Range 3 (-110~-115dBm) %']) || 0;
          const range4 = parseFloat(row['RSRP < -115dBm %']) || 0;

          html += `
            <td class="rsrp-cell-name">${row['Cell_Name']}</td>
            <td class="rsrp-data-cell ${this.getRsrpRangeClass(range1, 'excellent')}">${range1.toFixed(1)}%</td>
            <td class="rsrp-data-cell ${this.getRsrpRangeClass(range2, 'good')}">${range2.toFixed(1)}%</td>
            <td class="rsrp-data-cell ${this.getRsrpRangeClass(range3, 'fair')}">${range3.toFixed(1)}%</td>
            <td class="rsrp-data-cell ${this.getRsrpRangeClass(range4, 'poor')}">${range4.toFixed(1)}%</td>
          `;

          tr.innerHTML = html;
          tbody.appendChild(tr);
          siteNameRowIndex++;
        });
      });
    });
  }

  getRsrpRangeClass(value, type) {
    // Apply color coding based on percentage thresholds
    if (type === 'excellent' && value > 70) return 'rsrp-range-excellent';
    if (type === 'good' && value > 60) return 'rsrp-range-good';
    if (type === 'fair' && value > 50) return 'rsrp-range-fair';
    if (type === 'poor' && value > 40) return 'rsrp-range-poor';
    
    // General color coding for any high values
    if (value > 80) return 'rsrp-range-excellent';
    if (value > 60) return 'rsrp-range-good';
    if (value > 40) return 'rsrp-range-fair';
    if (value > 20) return 'rsrp-range-poor';
    
    return '';
  }

  // Status update functions
  updateRsrpStats(filteredCount, totalCount) {
    const statsDiv = document.getElementById('rsrpStats');
    if (statsDiv) {
      if (filteredCount < totalCount) {
        statsDiv.innerHTML = `<i class="fas fa-filter"></i> Showing ${filteredCount} of ${totalCount} records`;
      } else {
        statsDiv.innerHTML = `<i class="fas fa-table"></i> ${totalCount} records total`;
      }
    }
  }

  updateCommonRsrpStats(filteredCount, totalCount) {
    const statsDiv = document.getElementById('commonRsrpStats');
    if (statsDiv) {
      if (filteredCount < totalCount) {
        statsDiv.innerHTML = `<i class="fas fa-filter"></i> Showing ${filteredCount} of ${totalCount} records`;
      } else {
        statsDiv.innerHTML = `<i class="fas fa-table"></i> ${totalCount} records total`;
      }
    }
  }

  updateRsrpStatus(filteredCount, totalCount) {
    const statusDiv = document.getElementById('rsrpStatus');
    if (statusDiv) {
      if (filteredCount < totalCount) {
        statusDiv.textContent = `Showing ${filteredCount} of ${totalCount} RSRP records (filtered)`;
      } else {
        statusDiv.textContent = `Showing all ${totalCount} RSRP records`;
      }
    }
    this.updateRsrpStats(filteredCount, totalCount);
  }

  updateCommonRsrpStatus(filteredCount, totalCount) {
    const statusDiv = document.getElementById('commonRsrpStatus');
    if (statusDiv) {
      if (filteredCount < totalCount) {
        statusDiv.textContent = `Showing ${filteredCount} of ${totalCount} common location RSRP records (filtered)`;
      } else {
        statusDiv.textContent = `Showing all ${totalCount} common location RSRP records`;
      }
    }
    this.updateCommonRsrpStats(filteredCount, totalCount);
  }
}

// Global instance for backward compatibility with inline handlers
let rsrpManager;

// Global functions for backward compatibility
function debounceRsrpFilter() {
  if (rsrpManager) rsrpManager.debounceRsrpFilter();
}

function debounceCommonRsrpFilter() {
  if (rsrpManager) rsrpManager.debounceCommonRsrpFilter();
}

function clearRsrpFilters() {
  if (rsrpManager) rsrpManager.clearRsrpFilters();
}

function clearCommonRsrpFilters() {
  if (rsrpManager) rsrpManager.clearCommonRsrpFilters();
}

// Initialize RSRP manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  rsrpManager = new RSRPTableManager();
});
