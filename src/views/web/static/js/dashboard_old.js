// Stream-Bit Dashboard JavaScript

class BitcoinDashboard {
    constructor() {
        this.priceChart = null;
        this.eventSource = null;
        this.isConnected = false;
        this.lastUpdateTime = null;
        this.retryCount = 0;
        this.maxRetries = 5;
        this.retryDelay = 1000; // Start with 1 second

        this.init();
    }

    init() {
        console.log('Initializing Bitcoin Dashboard...');
        this.initializeChart();
        this.startDataStream();
        this.setupEventListeners();
        this.loadInitialData();
    }

    initializeChart() {
        const ctx = document.getElementById('priceChart');
        if (!ctx) {
            console.error('Price chart canvas not found');
            return;
        }

        this.priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Bitcoin Price (USD)',
                    data: [],
                    borderColor: 'rgb(102, 126, 234)',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: 'rgb(102, 126, 234)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: 'rgb(102, 126, 234)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        callbacks: {
                            label: function (context) {
                                return `Price: $${context.parsed.y.toLocaleString()}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Time',
                            font: {
                                size: 12,
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Price (USD)',
                            font: {
                                size: 12,
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        },
                        ticks: {
                            callback: function (value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });

        console.log('Chart initialized successfully');
    }

    startDataStream() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        console.log('Starting data stream...');
        this.eventSource = new EventSource('/api/bitcoin/stream');

        this.eventSource.onopen = () => {
            console.log('Data stream connected');
            this.updateConnectionStatus(true);
            this.retryCount = 0;
            this.retryDelay = 1000;
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.updateDashboard(data);
            } catch (error) {
                console.error('Error parsing stream data:', error);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('Stream error:', error);
            this.updateConnectionStatus(false);
            this.handleStreamError();
        };
    }

    handleStreamError() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            console.log(`Retrying connection (${this.retryCount}/${this.maxRetries}) in ${this.retryDelay}ms...`);

            setTimeout(() => {
                this.startDataStream();
            }, this.retryDelay);

            // Exponential backoff
            this.retryDelay = Math.min(this.retryDelay * 2, 30000);
        } else {
            console.error('Max retries reached. Falling back to polling.');
            this.startPolling();
        }
    }

    startPolling() {
        console.log('Starting polling fallback...');
        setInterval(() => {
            this.loadLatestData();
        }, 30000); // Poll every 30 seconds
    }

    async loadInitialData() {
        try {
            this.showLoading(true);

            // Load latest price
            await this.loadLatestData();

            // Load hourly chart data
            await this.loadHourlyData();

            // Load statistics
            await this.loadStatisticsData();

            // Load cache stats
            await this.loadCacheStats();

            this.showLoading(false);
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to load initial data');
            this.showLoading(false);
        }
    }

    async loadLatestData() {
        try {
            const response = await fetch('/api/bitcoin/latest');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.updatePriceDisplay(data);
            this.updateLastUpdated();
        } catch (error) {
            console.error('Error loading latest data:', error);
            this.showError('Failed to load latest price');
        }
    }

    async loadHourlyData() {
        try {
            const response = await fetch('/api/bitcoin/hourly?hours=24');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.updateChart(data.data);
        } catch (error) {
            console.error('Error loading hourly data:', error);
            this.showError('Failed to load chart data');
        }
    }

    async loadStatisticsData() {
        try {
            const response = await fetch('/api/bitcoin/analytics/summary');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.updateStatistics(data.data);
        } catch (error) {
            console.error('Error loading statistics data:', error);
            // Não mostrar erro, apenas manter valores padrão
        }
    }

    async loadCacheStats() {
        try {
            const response = await fetch('/api/cache/stats');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.updateCacheStats(data.data);
        } catch (error) {
            console.error('Error loading cache stats:', error);
            // Não mostrar erro, apenas manter valores padrão
        }
    }

    updateDashboard(data) {
        if (data.latest) {
            this.updatePriceDisplay(data.latest);
        }

        if (data.hourly) {
            this.updateChart(data.hourly);
        }

        this.updateLastUpdated();
    }

    updatePriceDisplay(response) {
        const priceElement = document.getElementById('current-price');
        const changeElement = document.getElementById('price-change');

        // Acessar dados da resposta da API
        const priceData = response.data || response;

        console.log('Price data received:', priceData);

        if (priceElement && priceData && priceData.price) {
            priceElement.textContent = `R$${priceData.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;

            // Update price color based on change
            priceElement.className = 'text-primary';
            const change = priceData.change_24h || 0;
            if (change > 0) {
                priceElement.classList.add('text-success');
            } else if (change < 0) {
                priceElement.classList.add('text-danger');
            } else {
                priceElement.classList.add('text-primary');
            }
        }

        if (changeElement && priceData && priceData.change_24h !== undefined) {
            const change = priceData.change_24h;
            const changePercent = priceData.change_24h_percent || 0;

            if (change === 0) {
                changeElement.textContent = 'No change (24h)';
            } else {
                changeElement.innerHTML = `
                    <span class="${change >= 0 ? 'text-success' : 'text-danger'}">
                        <i class="fas fa-arrow-${change >= 0 ? 'up' : 'down'}"></i>
                        R$${Math.abs(change).toLocaleString('pt-BR', { minimumFractionDigits: 2 })} (${Math.abs(changePercent).toFixed(2)}%)
                    </span>
                `;
            }
        }
    }

    updateChart(hourlyData) {
        if (!this.priceChart || !hourlyData || !Array.isArray(hourlyData)) {
            return;
        }

        // Prepare data for chart - sort by timestamp first
        const sortedData = hourlyData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        const labels = [];
        const prices = [];

        sortedData.forEach(item => {
            if (item.timestamp && item.price) {
                const date = new Date(item.timestamp);
                // Format time as DD/MM HH:mm for better readability
                const label = `${date.getDate().toString().padStart(2, '0')}/${(date.getMonth() + 1).toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:00`;
                labels.push(label);
                prices.push(item.price);
            }
        });

        console.log('Chart data:', { labels, prices });

        // Update chart data
        this.priceChart.data.labels = labels;
        this.priceChart.data.datasets[0].data = prices;
        this.priceChart.update();
    }

    updateStatistics(statsData) {
        if (!statsData) return;

        // Update statistics elements
        const elements = {
            'min-price': statsData.min_price ? `R$${parseFloat(statsData.min_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '--',
            'max-price': statsData.max_price ? `R$${parseFloat(statsData.max_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '--',
            'avg-price': statsData.avg_price ? `R$${parseFloat(statsData.avg_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '--',
            'volatility': statsData.price_volatility ? `${parseFloat(statsData.price_volatility).toFixed(2)}%` : '--%',
            'data-points': statsData.total_records ? parseInt(statsData.total_records).toLocaleString() : '--'
        };

        for (const [id, value] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        }
    }

    updateCacheStats(cacheData) {
        if (!cacheData) return;

        // Update cache statistics elements
        const cacheElements = {
            'hit-rate': cacheData.hit_rate_percent ? `${cacheData.hit_rate_percent}%` : '--%',
            'total-requests': cacheData.total_requests ? parseInt(cacheData.total_requests).toLocaleString() : '--',
            'cache-size': cacheData.current_size ? parseInt(cacheData.current_size).toLocaleString() : '--'
        };

        for (const [id, value] of Object.entries(cacheElements)) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        }
    }

    updateConnectionStatus(connected) {
        this.isConnected = connected;
        const statusElement = document.getElementById('connection-status');

        if (statusElement) {
            statusElement.className = 'badge ms-2';
            if (connected) {
                statusElement.classList.add('bg-success');
                statusElement.textContent = 'Connected';
            } else {
                statusElement.classList.add('bg-danger');
                statusElement.textContent = 'Disconnected';
            }
        }
    }

    updateLastUpdated() {
        this.lastUpdateTime = new Date();
        const element = document.getElementById('last-update');
        if (element) {
            element.textContent = `Last update: ${this.lastUpdateTime.toLocaleTimeString()}`;
        }
    }

    showLoading(show) {
        const spinner = document.getElementById('loadingSpinner');
        if (spinner) {
            spinner.style.display = show ? 'block' : 'none';
        }
    }

    showError(message) {
        const errorContainer = document.getElementById('errorContainer');
        if (errorContainer) {
            errorContainer.innerHTML = `
                <div class="error-message">
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

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadInitialData();
            });
        }

        // Window focus/blur for connection management
        window.addEventListener('focus', () => {
            if (!this.isConnected) {
                console.log('Window focused, attempting to reconnect...');
                this.startDataStream();
            }
        });

        window.addEventListener('beforeunload', () => {
            if (this.eventSource) {
                this.eventSource.close();
            }
        });

        // Handle connection errors
        window.addEventListener('online', () => {
            console.log('Network connection restored');
            this.startDataStream();
        });

        window.addEventListener('offline', () => {
            console.log('Network connection lost');
            this.updateConnectionStatus(false);
        });
    }

    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        if (this.priceChart) {
            this.priceChart.destroy();
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM loaded, initializing dashboard...');
    window.bitcoinDashboard = new BitcoinDashboard();
    
    // Initialize pipeline control
    loadPipelineStatus();
    
    // Add pipeline toggle button event listener
    const pipelineButton = document.getElementById('toggle-pipeline');
    if (pipelineButton) {
        pipelineButton.addEventListener('click', togglePipeline);
    }
});

// Utility functions
function formatPrice(price) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(price);
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function getRelativeTime(timestamp) {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now - time;
    const diffMins = Math.floor(diffMs / (1000 * 60));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}

// Pipeline control functions
async function loadPipelineStatus() {
    try {
        const response = await fetch('/api/pipeline/status');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        updatePipelineButton(data.data);
    } catch (error) {
        console.error('Error loading pipeline status:', error);
    }
}

async function togglePipeline() {
    try {
        const button = document.getElementById('toggle-pipeline');
        button.disabled = true;
        
        const response = await fetch('/api/pipeline/toggle', { method: 'POST' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        updatePipelineButton(data.data);
        
        // Show success message
        console.log(data.data.message);
    } catch (error) {
        console.error('Error toggling pipeline:', error);
    } finally {
        document.getElementById('toggle-pipeline').disabled = false;
    }
}

function updatePipelineButton(pipelineData) {
    const button = document.getElementById('toggle-pipeline');
    const statusSpan = document.getElementById('pipeline-status');
    
    if (button && statusSpan) {
        const isRunning = pipelineData.running;
        
        button.className = isRunning ? 'btn btn-outline-danger' : 'btn btn-outline-success';
        statusSpan.textContent = isRunning ? 'Stop Pipeline' : 'Start Pipeline';
        
        // Update icon
        const icon = button.querySelector('i');
        if (icon) {
            icon.className = isRunning ? 'fas fa-stop' : 'fas fa-play';
        }
    }
}
