class UsageAnalyzerApp {
  constructor() {
    this.init();
  }

  init() {
    this.initializeComponents();
    this.setupEventListeners();
  }

  initializeComponents() {
    // Initialize components when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
      // Components are initialized by their respective modules
      console.log('Usage Analyzer Application Initialized');
    });
  }

  setupEventListeners() {
    // Tab switching functionality
    const tabLinks = document.querySelectorAll('[data-bs-toggle="tab"]');
    tabLinks.forEach(tab => {
      tab.addEventListener('shown.bs.tab', (event) => {
        const targetTab = event.target.getAttribute('data-bs-target');
        this.onTabChange(targetTab);
      });
    });
  }

  onTabChange(targetTab) {
    // Handle tab-specific logic
    switch(targetTab) {
      case '#graphs':
        // Charts are already initialized on page load
        break;
      case '#rsrp':
        // RSRP tables are already rendered
        break;
      case '#location':
        // Map functionality handled separately
        break;
      default:
        break;
    }
  }

  // Utility functions
  static showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
    }
  }

  static hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = '';
    }
  }

  static showError(message, elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> ${message}</div>`;
    }
  }
}

// Initialize the application
const app = new UsageAnalyzerApp();
