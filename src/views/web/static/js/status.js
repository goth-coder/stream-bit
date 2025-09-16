// Status Page JavaScript for Stream-Bit

class StatusMonitor {
    constructor() {
        this.checks = new Map();
        this.checkInterval = 30000; // 30 seconds
        this.intervalId = null;

        this.init();
    }

    init() {
        console.log('Initializing Status Monitor...');
        this.loadStatusChecks();
        this.startMonitoring();
    }

    async loadStatusChecks() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const statusData = await response.json();
            this.updateStatusDisplay(statusData);
        } catch (error) {
            console.error('Error loading status:', error);
            this.showError('Failed to load system status');
        }
    }

    startMonitoring() {
        // Initial load
        this.loadStatusChecks();

        // Set up interval for periodic updates
        this.intervalId = setInterval(() => {
            this.loadStatusChecks();
        }, this.checkInterval);

        console.log(`Status monitoring started (${this.checkInterval}ms interval)`);
    }

    stopMonitoring() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
            console.log('Status monitoring stopped');
        }
    }

    updateStatusDisplay(statusData) {
        this.updateOverallStatus(statusData.overall_status);
        this.updateServiceStatuses(statusData.services || {});
        this.updateSystemMetrics(statusData.metrics || {});
        this.updateLastChecked();
    }

    updateOverallStatus(overallStatus) {
        const statusElement = document.getElementById('overallStatus');
        const statusBadge = document.getElementById('statusBadge');

        if (!statusElement || !statusBadge) return;

        let statusClass, statusText, badgeClass;

        switch (overallStatus) {
            case 'healthy':
                statusClass = 'text-success';
                statusText = 'All Systems Operational';
                badgeClass = 'bg-success';
                break;
            case 'degraded':
                statusClass = 'text-warning';
                statusText = 'Some Systems Degraded';
                badgeClass = 'bg-warning';
                break;
            case 'down':
                statusClass = 'text-danger';
                statusText = 'System Issues Detected';
                badgeClass = 'bg-danger';
                break;
            default:
                statusClass = 'text-muted';
                statusText = 'Unknown Status';
                badgeClass = 'bg-secondary';
        }

        statusElement.className = `h4 ${statusClass}`;
        statusElement.innerHTML = `
            <i class="fas fa-${this.getStatusIcon(overallStatus)}"></i>
            ${statusText}
        `;

        statusBadge.className = `badge ${badgeClass}`;
        statusBadge.textContent = overallStatus.toUpperCase();
    }

    updateServiceStatuses(services) {
        const servicesContainer = document.getElementById('servicesStatus');
        if (!servicesContainer) return;

        let servicesHtml = '';

        Object.entries(services).forEach(([serviceName, serviceData]) => {
            const statusIcon = this.getStatusIcon(serviceData.status);
            const statusClass = this.getStatusClass(serviceData.status);
            const responseTime = serviceData.response_time ? `${serviceData.response_time}ms` : 'N/A';

            servicesHtml += `
                <div class="col-md-6 mb-3">
                    <div class="card service-card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h6 class="card-title mb-1">${this.formatServiceName(serviceName)}</h6>
                                    <small class="text-muted">Response: ${responseTime}</small>
                                </div>
                                <div class="text-right">
                                    <span class="status-indicator ${statusClass}">
                                        <i class="fas fa-${statusIcon}"></i>
                                    </span>
                                </div>
                            </div>
                            ${serviceData.last_error ? `
                                <div class="mt-2">
                                    <small class="text-danger">
                                        <i class="fas fa-exclamation-triangle"></i>
                                        ${serviceData.last_error}
                                    </small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        });

        servicesContainer.innerHTML = servicesHtml;
    }

    updateSystemMetrics(metrics) {
        // Update cache metrics
        const cacheHits = document.getElementById('cacheHits');
        const cacheMisses = document.getElementById('cacheMisses');
        const cacheHitRate = document.getElementById('cacheHitRate');

        if (cacheHits && metrics.cache_hits !== undefined) {
            cacheHits.textContent = metrics.cache_hits.toLocaleString();
        }

        if (cacheMisses && metrics.cache_misses !== undefined) {
            cacheMisses.textContent = metrics.cache_misses.toLocaleString();
        }

        if (cacheHitRate && metrics.cache_hit_rate !== undefined) {
            const hitRate = (metrics.cache_hit_rate * 100).toFixed(1);
            cacheHitRate.textContent = `${hitRate}%`;
            cacheHitRate.className = `badge ${hitRate > 80 ? 'bg-success' : hitRate > 60 ? 'bg-warning' : 'bg-danger'}`;
        }

        // Update API metrics
        const apiRequests = document.getElementById('apiRequests');
        const apiErrors = document.getElementById('apiErrors');
        const avgResponseTime = document.getElementById('avgResponseTime');

        if (apiRequests && metrics.api_requests !== undefined) {
            apiRequests.textContent = metrics.api_requests.toLocaleString();
        }

        if (apiErrors && metrics.api_errors !== undefined) {
            apiErrors.textContent = metrics.api_errors.toLocaleString();
        }

        if (avgResponseTime && metrics.avg_response_time !== undefined) {
            avgResponseTime.textContent = `${metrics.avg_response_time}ms`;
        }

        // Update data metrics
        const lastDataUpdate = document.getElementById('lastDataUpdate');
        const dataPoints = document.getElementById('dataPoints');

        if (lastDataUpdate && metrics.last_data_update) {
            const updateTime = new Date(metrics.last_data_update);
            lastDataUpdate.textContent = updateTime.toLocaleString();
        }

        if (dataPoints && metrics.data_points !== undefined) {
            dataPoints.textContent = metrics.data_points.toLocaleString();
        }
    }

    updateLastChecked() {
        const lastCheckedElement = document.getElementById('lastChecked');
        if (lastCheckedElement) {
            const now = new Date();
            lastCheckedElement.textContent = `Last checked: ${now.toLocaleTimeString()}`;
        }
    }

    getStatusIcon(status) {
        switch (status) {
            case 'healthy':
            case 'up':
                return 'check-circle';
            case 'degraded':
            case 'warning':
                return 'exclamation-triangle';
            case 'down':
            case 'error':
                return 'times-circle';
            default:
                return 'question-circle';
        }
    }

    getStatusClass(status) {
        switch (status) {
            case 'healthy':
            case 'up':
                return 'text-success';
            case 'degraded':
            case 'warning':
                return 'text-warning';
            case 'down':
            case 'error':
                return 'text-danger';
            default:
                return 'text-muted';
        }
    }

    formatServiceName(serviceName) {
        return serviceName
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    showError(message) {
        const errorContainer = document.getElementById('errorContainer');
        if (errorContainer) {
            errorContainer.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <i class="fas fa-exclamation-triangle"></i>
                    ${message}
                </div>
            `;

            // Auto-hide error after 5 seconds
            setTimeout(() => {
                errorContainer.innerHTML = '';
            }, 5000);
        }
    }

    destroy() {
        this.stopMonitoring();
    }
}

// Initialize status monitor when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM loaded, initializing status monitor...');
    window.statusMonitor = new StatusMonitor();

    // Setup refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            window.statusMonitor.loadStatusChecks();
        });
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function () {
    if (window.statusMonitor) {
        window.statusMonitor.destroy();
    }
});
