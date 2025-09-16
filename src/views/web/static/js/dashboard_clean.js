// Stream-Bit Dashboard JavaScript - Clean Version

class BitcoinDashboard {
    constructor() {
        this.chart = null;
        this.eventSource = null;
        this.lastUpdateTime = null;
        this.currentTimeRange = 24; // Default to 24 hours

        this.init();
    }

    async init() {
        console.log('Initializing Bitcoin Dashboard...');

        this.initChart();
        await this.loadInitialData();
        await this.loadCacheStats();
        this.setupEventListeners();
        this.startSSE(); // Auto-start SSE for real-time updates
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
                    },
                    tooltip: {
                        enabled: true,
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function (context) {
                                // Mostrar timestamp completo no tooltip
                                return context[0].label;
                            },
                            label: function (context) {
                                const value = context.parsed.y;
                                return `Bitcoin Price: R$ ${value.toLocaleString('pt-BR', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                })}`;
                            }
                        }
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
                },
                hover: {
                    mode: 'index',
                    intersect: false
                },
                elements: {
                    point: {
                        radius: 4,
                        hoverRadius: 8,
                        hitRadius: 15  // Aumenta área de detecção
                    },
                    line: {
                        tension: 0.4
                    }
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
            if (response.ok) {
                const data = await response.json();
                this.updateCacheStats(data.data);
            }
        } catch (error) {
            console.error('Error loading cache stats:', error);
        }
    }

    setupEventListeners() {
        // Chart range buttons
        document.querySelectorAll('.chart-range-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const hours = parseInt(btn.dataset.hours);
                this.changeTimeRange(hours);
            });
        });

        // Visibility change handler
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
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

    async changeTimeRange(hours) {
        this.currentTimeRange = hours;

        // Update button states
        document.querySelectorAll('.chart-range-btn').forEach(btn => {
            btn.classList.remove('active');
            if (parseInt(btn.dataset.hours) === hours) {
                btn.classList.add('active');
            }
        });

        // Load new data
        try {
            const response = await fetch(`/api/bitcoin/hourly?hours=${hours}`);
            if (response.ok) {
                const data = await response.json();
                this.updateChart(data);
                console.log(`Chart updated to ${hours}h range`);
            }
        } catch (error) {
            console.error('Error updating chart range:', error);
        }
    }

    startSSE() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        console.log('Connecting to live stream...');
        this.eventSource = new EventSource('/api/live-stream');

        this.eventSource.onopen = () => {
            console.log('Live stream connected successfully');
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('connection-status').className = 'badge bg-success ms-2';
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleSSEMessage(data);
            } catch (error) {
                console.error('Error parsing SSE message:', error);
            }
        };

        this.eventSource.onerror = () => {
            console.warn('SSE connection error - retrying...');
            document.getElementById('connection-status').textContent = 'Reconnecting...';
            document.getElementById('connection-status').className = 'badge bg-warning ms-2';
        };
    }

    stopSSE() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            document.getElementById('connection-status').textContent = 'Disconnected';
            document.getElementById('connection-status').className = 'badge bg-secondary ms-2';
        }
    }

    handleSSEMessage(data) {
        switch (data.type) {
            case 'price_update':
                this.updatePriceDisplay({ data: data.data });
                console.log(`Price updated: R$ ${data.data.price_brl.toLocaleString('pt-BR')}`);
                break;
            case 'cache_stats':
                this.updateCacheStats(data.data);
                console.log(`Cache stats updated - Hit rate: ${data.data.hit_rate_percent}%`);
                break;
            case 'pipeline_stopped':
                console.log('Pipeline stopped remotely');
                break;
            case 'stream_end':
                console.log('Stream ended');
                this.stopSSE();
                break;
        }
    }

    updatePriceDisplay(response) {
        if (!response?.data) return;

        const data = response.data;
        const price = parseFloat(data.price_brl || 0);
        const priceChange = parseFloat(data.price_change_percent || 0);

        // Update price
        document.getElementById('current-price').textContent =
            `R$ ${price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        // Update price change
        const changeElement = document.getElementById('price-change');
        const changeText = `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}%`;
        changeElement.textContent = changeText;
        changeElement.className = priceChange >= 0 ? 'text-success' : 'text-danger';

        // Update timestamp
        this.lastUpdateTime = new Date();
        document.getElementById('last-update').textContent =
            `Last update: ${this.lastUpdateTime.toLocaleTimeString('pt-BR')}`;

        // Update cache indicator
        const cacheIndicator = document.getElementById('cache-indicator');
        if (response.from_cache) {
            cacheIndicator.textContent = 'Cache';
            cacheIndicator.className = 'badge bg-success';
        } else {
            cacheIndicator.textContent = 'Live';
            cacheIndicator.className = 'badge bg-primary';
        }
        cacheIndicator.classList.remove('d-none');
    }

    async updateChart(response) {
        if (!response?.data || !this.chart) return;

        const chartData = response.data;
        if (!Array.isArray(chartData)) return;

        // Sort by timestamp to ensure chronological order
        const sortedData = chartData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        const labels = sortedData.map(item => {
            const date = new Date(item.timestamp);
            // Verifica se a data é válida
            if (isNaN(date.getTime())) {
                console.warn('Invalid timestamp:', item.timestamp);
                return 'Invalid Date';
            }

            // Para períodos curtos (<=6h), mostra hora e minuto
            // Para períodos mais longos, mostra dia e hora
            const hours = this.currentTimeRange || 24;
            if (hours <= 6) {
                return date.toLocaleDateString('pt-BR', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
            } else if (hours <= 24) {
                return date.toLocaleDateString('pt-BR', {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } else {
                return date.toLocaleDateString('pt-BR', {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit'
                });
            }
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
            'min-price': data.min_price ? `R$ ${parseFloat(data.min_price).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--',
            'max-price': data.max_price ? `R$ ${parseFloat(data.max_price).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--',
            'avg-price': data.avg_price ? `R$ ${parseFloat(data.avg_price).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--',
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

        const elements = {
            'hit-rate': `${(cacheData.hit_rate_percent || 0).toFixed(2)}%`,
            'total-requests': cacheData.total_requests || 0,
            'cache-size': cacheData.current_size || 0
        };

        for (const [id, value] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new BitcoinDashboard();
});
