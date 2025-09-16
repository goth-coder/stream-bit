// Stream-Bit Dashboard JavaScript - Simplified with SSE

class BitcoinDashboard {
    constructor() {
        this.chart = null;
        this.eventSource = null;
        this.isLiveDataActive = false;
        this.lastUpdateTime = null;

        this.init();
    }

    async init() {
        console.log('Initializing Bitcoin Dashboard...');

        this.initChart();
        await this.loadInitialData();
        await this.loadCacheStats();
        this.setupEventListeners();

        // Check if live data was already running
        await this.checkLiveDataStatus();

        console.log('Dashboard initialized successfully');
    }

    initChart() {
        const ctx = document.getElementById('priceChart');
        if (!ctx) return;

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Bitcoin Price (BRL)',
                    data: [],
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function (value) {
                                return 'R$ ' + value.toLocaleString('pt-BR');
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    async loadInitialData() {
        try {
            // Load current price
            const latestResponse = await fetch('/api/bitcoin/latest');
            if (latestResponse.ok) {
                const latestData = await latestResponse.json();
                this.updatePriceDisplay(latestData);
            }

            // Load chart data
            const hourlyResponse = await fetch('/api/bitcoin/hourly?hours=24');
            if (hourlyResponse.ok) {
                const hourlyData = await hourlyResponse.json();
                this.updateChart(hourlyData);
            }

            // Load statistics
            const statsResponse = await fetch('/api/bitcoin/analytics/summary');
            if (statsResponse.ok) {
                const statsData = await statsResponse.json();
                this.updateStatistics(statsData.data);
            }

        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    async loadCacheStats() {
        try {
            const response = await fetch('/api/cache/stats');
            if (!response.ok) return;

            const data = await response.json();
            this.updateCacheStats(data.data);
        } catch (error) {
            console.error('Error loading cache stats:', error);
        }
    }

    async checkLiveDataStatus() {
        try {
            const response = await fetch('/api/pipeline/status');
            if (response.ok) {
                const data = await response.json();
                this.isLiveDataActive = data.data.running;
                this.updateLiveDataButton();

                if (this.isLiveDataActive) {
                    this.startSSE();
                }
            }
        } catch (error) {
            console.error('Error checking live data status:', error);
        }
    }

    setupEventListeners() {
        // Live data toggle button
        const liveDataButton = document.getElementById('live-data-toggle');
        if (liveDataButton) {
            liveDataButton.addEventListener('click', () => this.toggleLiveData());
        }

        // Window focus/blur
        window.addEventListener('focus', () => {
            if (!this.isLiveDataActive) {
                this.loadInitialData();
                this.loadCacheStats();
            }
        });

        // Before unload
        window.addEventListener('beforeunload', () => {
            if (this.eventSource) {
                this.eventSource.close();
            }
        });
    }

    async toggleLiveData() {
        try {
            const button = document.getElementById('live-data-toggle');
            button.disabled = true;

            const response = await fetch('/api/live-data/toggle', { method: 'POST' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            this.isLiveDataActive = data.data.running;

            if (this.isLiveDataActive) {
                this.startSSE();
            } else {
                this.stopSSE();
            }

            this.updateLiveDataButton();
            console.log(data.data.message);

        } catch (error) {
            console.error('Error toggling live data:', error);
        } finally {
            document.getElementById('live-data-toggle').disabled = false;
        }
    }

    startSSE() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        this.eventSource = new EventSource('/api/live-stream');

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleSSEMessage(data);
            } catch (error) {
                console.error('Error parsing SSE message:', error);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            this.eventSource.close();
            this.isLiveDataActive = false;
            this.updateLiveDataButton();
        };

        console.log('SSE connection started');
    }

    stopSSE() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            console.log('SSE connection stopped');
        }
    }

    handleSSEMessage(data) {
        switch (data.type) {
            case 'price_update':
                this.updatePriceDisplay({ data: data.data });
                this.lastUpdateTime = new Date();
                this.updateLastUpdated();
                break;

            case 'cache_stats':
                this.updateCacheStats(data.data);
                break;

            case 'pipeline_stopped':
                this.isLiveDataActive = false;
                this.updateLiveDataButton();
                this.stopSSE();
                console.log('Pipeline stopped remotely');
                break;

            case 'stream_ended':
                this.isLiveDataActive = false;
                this.updateLiveDataButton();
                this.stopSSE();
                console.log('Stream ended');
                break;
        }
    }

    updateLiveDataButton() {
        const button = document.getElementById('live-data-toggle');
        const statusSpan = document.getElementById('live-data-status');
        const description = document.getElementById('live-data-description');

        if (button && statusSpan) {
            if (this.isLiveDataActive) {
                button.className = 'btn btn-danger btn-lg';
                button.querySelector('i').className = 'fas fa-stop';
                statusSpan.textContent = 'Stop Live Data';
                if (description) {
                    description.textContent = 'Live data collection active - receiving real-time updates';
                }
            } else {
                button.className = 'btn btn-primary btn-lg';
                button.querySelector('i').className = 'fas fa-play';
                statusSpan.textContent = 'Start Live Data';
                if (description) {
                    description.textContent = 'Click to start real-time Bitcoin data collection and dashboard updates';
                }
            }
        }
    }

    updatePriceDisplay(response) {
        if (!response?.data) return;

        const data = response.data;
        const priceElement = document.getElementById('current-price');
        const changeElement = document.getElementById('price-change');

        if (priceElement) {
            const price = parseFloat(data.price || 0);
            priceElement.textContent = `R$ ${price.toLocaleString('pt-BR', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            })}`;
        }

        if (changeElement) {
            const change24h = parseFloat(data.change_24h || 0);
            const changePercent = parseFloat(data.change_24h_percent || 0);

            if (change24h === 0 && changePercent === 0) {
                changeElement.textContent = 'No change (24h)';
                changeElement.className = 'mb-0 text-muted';
            } else {
                const changeText = `${change24h >= 0 ? '+' : ''}${change24h.toFixed(2)} (${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%)`;
                changeElement.textContent = changeText;
                changeElement.className = `mb-0 ${change24h >= 0 ? 'text-success' : 'text-danger'}`;
            }
        }
    }

    async updateChart(response) {
        if (!response?.data || !this.chart) return;

        const chartData = response.data;
        if (!Array.isArray(chartData)) return;

        // Sort by timestamp to ensure chronological order
        const sortedData = chartData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        const labels = sortedData.map(item => {
            const date = new Date(item.timestamp);
            return date.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        });

        const prices = sortedData.map(item => parseFloat(item.price || item.avg_price || 0));

        this.chart.data.labels = labels;
        this.chart.data.datasets[0].data = prices;
        this.chart.update('none');

        console.log('Chart updated with', prices.length, 'data points');
    }

    updateStatistics(data) {
        if (!data) return;

        const elements = {
            'min-price': data.min_price ? `R$ ${parseFloat(data.min_price).toLocaleString('pt-BR')}` : '--',
            'max-price': data.max_price ? `R$ ${parseFloat(data.max_price).toLocaleString('pt-BR')}` : '--',
            'avg-price': data.avg_price ? `R$ ${parseFloat(data.avg_price).toLocaleString('pt-BR')}` : '--',
            'volatility': data.price_volatility !== undefined ? `${parseFloat(data.price_volatility).toFixed(2)}%` : '--',
            'data-points': data.total_records || '--'
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

    updateLastUpdated() {
        const element = document.getElementById('last-update');
        if (element) {
            const now = new Date();
            element.textContent = `Last update: ${now.toLocaleTimeString('pt-BR')}`;
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM loaded, initializing dashboard...');
    window.bitcoinDashboard = new BitcoinDashboard();
});

// Utility functions (keeping existing ones)
function formatPrice(price) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(price);
}

function formatDateTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('pt-BR');
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
