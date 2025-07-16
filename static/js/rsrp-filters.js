class RSRPTableManager {
  constructor() {
    this.filterTimeout = null;
  }

  debounceFilter(formType) {
    clearTimeout(this.filterTimeout);
    this.filterTimeout = setTimeout(() => {
      this.applyFilters(formType);
    }, 200);
  }

  applyFilters(formType) {
    const formId = formType === 'common' ? 'commonRsrpFilterForm' : 'rsrpFilterForm';
    const tbodyId = formType === 'common' ? 'commonRsrpTableBody' : 'rsrpTableBody';
    const statusId = formType === 'common' ? 'commonRsrpStatus' : 'rsrpStatus';
    const url = formType === 'common' ? '/filter_common_rsrp_data' : '/filter_rsrp_data';

    const form = document.getElementById(formId);
    const formData = new FormData(form);
    const headerInputs = document.querySelectorAll(`input[form="${formId}"]`);
    headerInputs.forEach(input => {
      if (input.value.trim()) {
        formData.set(input.name, input.value);
      }
    });

    fetch(url, {
      method: 'POST',
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert('Error: ' + data.error);
          return;
        }
        this.updateTable(tbodyId, data.data);
        this.updateStatus(statusId, data.filtered_count, data.total_count, formType);
      })
      .catch(error => {
        console.error('Error:', error);
        alert('Error filtering RSRP data');
      });
  }

  clearFilters(formType) {
    const formId = formType === 'common' ? 'commonRsrpFilterForm' : 'rsrpFilterForm';
    const form = document.getElementById(formId);
    const inputs = form.querySelectorAll('input[type="text"], input[type="number"], select');
    inputs.forEach(input => {
      if (input.name !== 'msisdn') {
        input.value = '';
      }
    });
    const headerInputs = document.querySelectorAll(`input[form="${formId}"]`);
    headerInputs.forEach(input => {
      input.value = '';
    });
    // Refresh the table after clearing filters
    this.applyFilters(formType);
  }

  updateTable(tbodyId, data) {
    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = '';
    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted"><i class="fas fa-info-circle"></i> No RSRP data matches the current filters</td></tr>';
      return;
    }
    const groupedData = this.groupDataBySite(data);
    this.renderGroupedData(tbody, groupedData);
  }

  groupDataBySite(data) {
    const groupedData = {};
    data.forEach(row => {
      const siteName = row['Site_Name'];
      const siteId = row['Site_ID'];
      if (!groupedData[siteName]) groupedData[siteName] = {};
      if (!groupedData[siteName][siteId]) groupedData[siteName][siteId] = [];
      groupedData[siteName][siteId].push(row);
    });
    return groupedData;
  }

  renderGroupedData(tbody, groupedData) {
    Object.keys(groupedData).forEach(siteName => {
      const siteNameGroups = groupedData[siteName];
      const totalSiteNameRows = Object.values(siteNameGroups).reduce((sum, arr) => sum + arr.length, 0);
      let siteNameRowIndex = 0;
      let goodSignal = 0, poorSignal = 0, signalQuality = 'Poor';
      // Compute Good/Poor Signal and Quality for the site
      let allRows = [];
      Object.values(siteNameGroups).forEach(rows => allRows = allRows.concat(rows));
      if (allRows.length > 0) {
        goodSignal = allRows[0]['Good Signal Avg (Range 1+2) %'] || 0;
        poorSignal = allRows[0]['Poor Signal Avg (Range 3+4) %'] || 0;
        signalQuality = allRows[0]['Signal Quality'] || 'Poor';
      }
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
            <td class="rsrp-data-cell">${range1.toFixed(1)}%</td>
            <td class="rsrp-data-cell">${range2.toFixed(1)}%</td>
            <td class="rsrp-data-cell">${range3.toFixed(1)}%</td>
            <td class="rsrp-data-cell">${range4.toFixed(1)}%</td>
          `;
          if (siteNameRowIndex === 0) {
            html += `<td rowspan="${totalSiteNameRows}" class="rsrp-data-cell">${goodSignal}%</td>`;
            html += `<td rowspan="${totalSiteNameRows}" class="rsrp-data-cell">${poorSignal}%</td>`;
            html += `<td rowspan="${totalSiteNameRows}" class="rsrp-quality-cell"><span class="badge ${signalQuality === 'Good' ? 'bg-success' : 'bg-danger'}">${signalQuality}</span></td>`;
          }
          tr.innerHTML = html;
          tbody.appendChild(tr);
          siteNameRowIndex++;
        });
      });
    });
  }

  updateStatus(statusId, filteredCount, totalCount, formType) {
    const statusDiv = document.getElementById(statusId);
    if (statusDiv) {
      if (filteredCount < totalCount) {
        statusDiv.textContent = `Showing ${filteredCount} of ${totalCount} ${formType === 'common' ? 'common location ' : ''}RSRP records (filtered)`;
      } else {
        statusDiv.textContent = `Showing all ${totalCount} ${formType === 'common' ? 'common location ' : ''}RSRP records`;
      }
    }
  }
}

// Global instance for backward compatibility
let rsrpManager;

function debounceRsrpFilter() {
  if (rsrpManager) rsrpManager.debounceFilter('main');
}
function debounceCommonRsrpFilter() {
  if (rsrpManager) rsrpManager.debounceFilter('common');
}
function clearRsrpFilters() {
  if (rsrpManager) rsrpManager.clearFilters('main');
}
function clearCommonRsrpFilters() {
  if (rsrpManager) rsrpManager.clearFilters('common');
}

document.addEventListener('DOMContentLoaded', function() {
  rsrpManager = new RSRPTableManager();
});
