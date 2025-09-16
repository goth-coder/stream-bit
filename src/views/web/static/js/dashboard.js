// Stream-Bit Dashboard JavaScript - Clean Version

class BitcoinDashboard {
    constructor() {
        this.chart = null;
        this.eventSource = null;
        this.lastUpdateTime = null;
        this.currentTimeRange = 24; // Default to 24 hours
        this.lastPrice = null; // Track last price for change detection

        this.init();
    }

    async init() {
        console.log('Initializing Bitcoin Dashboard...');

        // Criar referência global para acesso no tooltip
        window.dashboardInstance = this;

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
                    label: ' Bitcoin Price (BRL)',
                    data: [],
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.05)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    // Pontos invisíveis por padrão, aparecem só no hover
                    pointRadius: 0,
                    pointHoverRadius: 8,
                    pointHoverBackgroundColor: '#007bff',
                    pointHoverBorderColor: '#ffffff',
                    pointHoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                        position: 'top'
                    },
                    tooltip: {
                        enabled: true,
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function (context) {
                                // Usar timestamp real em vez da label filtrada
                                const dataIndex = context[0].dataIndex;
                                const dashboard = window.dashboardInstance || this.chart.dashboard;
                                if (dashboard && dashboard.realTimestamps && dashboard.realTimestamps[dataIndex]) {
                                    const realTime = new Date(dashboard.realTimestamps[dataIndex]);
                                    return realTime.toLocaleString('pt-BR', {
                                        day: '2-digit',
                                        month: '2-digit',
                                        year: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit',
                                        second: '2-digit'
                                    });
                                }
                                return context[0].label || 'Horário não disponível';
                            },
                            label: function (context) {
                                const value = context.parsed.y;
                                return `Bitcoin Price: R$ ${value.toLocaleString('pt-BR', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                })} UTC`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            // Remover filtros artificiais - labels são controlados pelos dados
                            maxRotation: 45,
                            minRotation: 0
                        }
                    },
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
        console.log('🚀 Loading all data in parallel for better performance...');
        const startTime = performance.now();

        try {
            // Load all data in parallel para melhor performance
            const promises = [
                fetch('/api/bitcoin/latest'),
                fetch('/api/bitcoin/chart-data?hours=24'),  // Use new chart-data API
                fetch('/api/bitcoin/analytics/summary'),
                fetch('/api/bitcoin/price-change?hours=24')
            ];

            // Aguardar todas as promises em paralelo
            const [latestResponse, hourlyResponse, statsResponse, priceChangeResponse] = await Promise.all(promises);

            // Process responses in parallel
            const updatePromises = [];

            // Update current price
            if (latestResponse.ok) {
                const latestData = await latestResponse.json();
                updatePromises.push(this.updatePriceDisplay(latestData));
            }

            // Update chart data
            if (hourlyResponse.ok) {
                const hourlyData = await hourlyResponse.json();
                updatePromises.push(this.updateChart(hourlyData));
            }

            // Update statistics
            if (statsResponse.ok) {
                const statsData = await statsResponse.json();
                updatePromises.push(this.updateStatistics(statsData.data));
            }

            // Update price change
            if (priceChangeResponse.ok) {
                const priceChangeData = await priceChangeResponse.json();
                updatePromises.push(this.updatePriceChangeDisplay(priceChangeData.data));
            }

            // Aguardar todas as atualizações de UI
            await Promise.all(updatePromises);

            const endTime = performance.now();
            const loadTime = (endTime - startTime).toFixed(2);
            console.log(`✅ All data loaded in ${loadTime}ms`);

        } catch (error) {
            console.error('❌ Error loading initial data:', error);
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

        // Show loading indicators
        this.showLoadingStates();

        // Load new data e price change em paralelo
        try {
            const startTime = performance.now();

            await Promise.all([
                this.updateChartForRange(hours),
                this.updatePriceChange(hours)
            ]);

            const endTime = performance.now();
            const loadTime = (endTime - startTime).toFixed(2);
            console.log(`Chart and price change updated to ${hours}h range in ${loadTime}ms`);

        } catch (error) {
            console.error('Error updating chart range:', error);
        } finally {
            this.hideLoadingStates();
        }
    }

    showLoadingStates() {
        // Add visual feedback
        const priceChangeElement = document.getElementById('price-change-percent');
        if (priceChangeElement) {
            priceChangeElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
    }

    hideLoadingStates() {
        // Loading will be replaced by actual data in update functions
    }

    async updateChartForRange(hours) {
        // Use new individual chart data API for precision
        const response = await fetch(`/api/bitcoin/chart-data?hours=${hours}`);
        if (response.ok) {
            const data = await response.json();
            this.updateChart(data);

            // SINCRONIZAÇÃO: Atualizar statistics quando muda o range
            await this.refreshStatisticsForRange(hours);
        }
    }

    async refreshStatisticsForRange(hours) {
        try {
            // Buscar statistics atualizadas para o range selecionado
            const response = await fetch(`/api/bitcoin/statistics?hours=${hours}`);
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.data) {
                    this.updateStatistics(data.data);
                    console.log(`Statistics synchronized for ${hours}h range`);
                }
            }
        } catch (error) {
            console.warn('Failed to refresh statistics:', error);
        }
    }

    async updatePriceChange(hours) {
        try {
            // Show loading state
            this.showPriceChangeLoading();

            const response = await fetch(`/api/bitcoin/price-change?hours=${hours}`);
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.updatePriceChangeDisplay(data.data);
                } else {
                    this.updatePriceChangeDisplay({ error: 'API returned error' });
                }
            } else {
                this.updatePriceChangeDisplay({ error: `HTTP ${response.status}` });
            }
        } catch (error) {
            console.error('Error updating price change:', error);
            this.updatePriceChangeDisplay({ error: 'Network error' });
        }
    }

    showPriceChangeLoading() {
        const changePercentElement = document.getElementById('price-change-percent');
        if (changePercentElement) {
            changePercentElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Calculating...';
            changePercentElement.className = 'badge bg-info';
        }
    }

    updatePriceChangeDisplay(priceChangeData) {
        const changeElement = document.getElementById('price-change');
        const changePercentElement = document.getElementById('price-change-percent');

        if (!changeElement) return;

        // Handle error states
        if (!priceChangeData || priceChangeData.error) {
            if (changePercentElement) {
                changePercentElement.textContent = 'Error';
                changePercentElement.className = 'badge bg-warning';
                changePercentElement.title = priceChangeData?.error || 'Unable to calculate price change';
            }
            if (changeElement) {
                changeElement.textContent = 'Price change unavailable';
                changeElement.className = 'text-muted';
            }
            return;
        }

        const {
            price_change_percent = 0,
            price_change_absolute = 0,
            is_positive = false,
            range_hours = 24
        } = priceChangeData;

        // Atualizar texto
        const changeText = `${is_positive ? '+' : ''}${price_change_percent.toFixed(2)}%`;
        const absoluteText = `${is_positive ? '+' : ''}R$ ${Math.abs(price_change_absolute).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        })}`;

        // Atualizar elementos
        if (changePercentElement) {
            changePercentElement.textContent = changeText;
            changePercentElement.className = `badge ${is_positive ? 'bg-success' : 'bg-danger'}`;
        }

        if (changeElement) {
            changeElement.textContent = absoluteText;
            changeElement.className = `text-${is_positive ? 'success' : 'danger'}`;
        }

        // Atualizar title para mostrar o range
        if (changePercentElement) {
            changePercentElement.title = `Price change in the last ${range_hours}h`;
        }

        console.log(`Price change updated: ${changeText} (${range_hours}h range)`);
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
                const newPrice = parseFloat(data.data.price_brl);

                // Atualizar Current Price sempre
                this.updatePriceDisplay({ data: data.data });

                // SÓ atualizar gráfico se houve MUDANÇA no preço
                if (this.lastPrice === null || Math.abs(newPrice - this.lastPrice) > 0.01) {
                    this.addNewPointToChart(data.data);
                    console.log(`Price CHANGED: R$ ${newPrice.toLocaleString('pt-BR')} (was R$ ${(this.lastPrice || 0).toLocaleString('pt-BR')}) - Chart updated`);
                    this.lastPrice = newPrice;
                } else {
                    console.log(`Price UNCHANGED: R$ ${newPrice.toLocaleString('pt-BR')} - Chart not updated`);
                }
                break;
            case 'statistics_update':
                this.updateStatistics(data.data);
                console.log(`Statistics updated - Data points: ${data.data.total_records}`);
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

        // Update price
        document.getElementById('current-price').textContent =
            `R$ ${price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        // Update price change SOMENTE se vier no response
        // Não resetar se o SSE não trouxer price_change_percent
        if (data.hasOwnProperty('price_change_percent')) {
            const priceChange = parseFloat(data.price_change_percent || 0);
            const changeElement = document.getElementById('price-change');
            const changeText = `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}%`;
            changeElement.textContent = changeText;
            changeElement.className = priceChange >= 0 ? 'text-success' : 'text-danger';
        }

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

        const rawData = response.data;
        if (!Array.isArray(rawData)) return;

        // Sort by timestamp to ensure chronological order
        const sortedData = rawData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        // Smart sampling para performance (max 100 points)
        const sampledData = this.smartSampleData(sortedData, 100);

        // PLOTAR TODOS OS PONTOS, mas criar labels inteligentes
        const allPrices = sampledData.map(item => parseFloat(item.price_brl || item.price || item.avg_price || 0));
        const smartLabels = this.createSmartLabelsOnly(sampledData, this.currentTimeRange || 24);

        // Guardar timestamps reais para o tooltip
        this.realTimestamps = sampledData.map(item => item.timestamp);

        this.chart.data.labels = smartLabels;
        this.chart.data.datasets[0].data = allPrices;
        this.chart.update('none'); // No animation for performance

        console.log(`Chart updated with ${sampledData.length} data points and ${smartLabels.filter(l => l !== '').length} visible labels (from ${rawData.length} total)`);
    }

    addNewPointToChart(newData) {
        if (!this.chart || !newData.price_brl || !newData.timestamp) return;

        const newPrice = parseFloat(newData.price_brl);
        const newTimestamp = newData.timestamp;

        // Adicionar novo ponto aos dados do chart
        this.chart.data.datasets[0].data.push(newPrice);

        // Adicionar timestamp real para tooltip
        if (!this.realTimestamps) this.realTimestamps = [];
        this.realTimestamps.push(newTimestamp);

        // Criar label apropriada para o novo ponto
        const newDate = new Date(newTimestamp);
        const hours = this.currentTimeRange || 24;
        let newLabel = '';

        // Determinar se este ponto merece uma label baseado na estratégia atual
        const totalPoints = this.chart.data.labels.length;
        const shouldShowLabel = this.shouldShowLabelForNewPoint(newDate, totalPoints, hours);

        if (shouldShowLabel) {
            if (hours <= 6) {
                newLabel = newDate.toLocaleTimeString('pt-BR', {
                    hour: '2-digit', minute: '2-digit'
                });
            } else if (hours <= 24) {
                newLabel = newDate.toLocaleTimeString('pt-BR', {
                    hour: '2-digit', minute: '2-digit'
                });
            } else {
                newLabel = newDate.toLocaleDateString('pt-BR', {
                    day: '2-digit', month: '2-digit'
                }) + ' ' + newDate.toLocaleTimeString('pt-BR', {
                    hour: '2-digit', minute: '2-digit'
                });
            }
        }

        this.chart.data.labels.push(newLabel);

        // Limitar número de pontos para performance (manter últimos 150)
        const maxPoints = 150;
        if (this.chart.data.datasets[0].data.length > maxPoints) {
            this.chart.data.datasets[0].data.shift();
            this.chart.data.labels.shift();
            if (this.realTimestamps) this.realTimestamps.shift();
        }

        // Atualizar chart sem animação para performance
        this.chart.update('none');

        console.log(`New point added to chart: R$ ${newPrice.toLocaleString('pt-BR')} at ${newDate.toLocaleTimeString('pt-BR')}`);
    }

    shouldShowLabelForNewPoint(newDate, totalPoints, hours) {
        // Lógica simples: mostrar label a cada N pontos baseado no range
        let interval;
        if (hours <= 6) {
            interval = 10; // Label a cada 10 pontos para 6h
        } else if (hours <= 24) {
            interval = 15; // Label a cada 15 pontos para 24h
        } else {
            interval = 20; // Label a cada 20 pontos para 3d+
        }

        return totalPoints % interval === 0;
    }

    smartSampleData(data, maxPoints) {
        if (data.length <= maxPoints) return data;

        // Take every nth item to reach target
        const step = Math.ceil(data.length / maxPoints);
        return data.filter((_, index) => index % step === 0);
    }

    createSmartLabelsOnly(data, hours) {
        // Nova estratégia: labels baseadas no horário atual com intervalos fixos
        const now = new Date();
        let startTime, intervalMillis, labelFormat;
        const totalLabels = 6; // Sempre 6 labels igualmente espaçadas

        if (hours <= 6) {
            // 6h: de 6:00 até agora (12:00), intervalos de 1h
            startTime = new Date(now);
            startTime.setHours(now.getHours() - 6, 0, 0, 0); // 6h atrás, minutos zerados
            intervalMillis = 60 * 60 * 1000; // 1 hora em milliseconds
            labelFormat = (date) => date.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } else if (hours <= 24) {
            // 24h: de 12:00 ontem até agora (12:00), intervalos de 4h
            startTime = new Date(now);
            startTime.setHours(now.getHours() - 24, 0, 0, 0); // 24h atrás, minutos zerados
            intervalMillis = 4 * 60 * 60 * 1000; // 4 horas em milliseconds
            labelFormat = (date) => date.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } else {
            // 3d: de 72h atrás até agora, intervalos de 12h
            startTime = new Date(now);
            startTime.setHours(now.getHours() - (hours), 0, 0, 0); // 72h atrás
            intervalMillis = 12 * 60 * 60 * 1000; // 12 horas em milliseconds
            labelFormat = (date) => {
                const today = new Date();
                const isToday = date.toDateString() === today.toDateString();
                const isYesterday = date.toDateString() === new Date(today - 24 * 60 * 60 * 1000).toDateString();

                if (isToday) {
                    return 'Hoje ' + date.toLocaleTimeString('pt-BR', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                } else if (isYesterday) {
                    return 'Ontem ' + date.toLocaleTimeString('pt-BR', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                } else {
                    return date.toLocaleDateString('pt-BR', {
                        day: '2-digit',
                        month: '2-digit'
                    }) + ' ' + date.toLocaleTimeString('pt-BR', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                }
            };
        }

        // Gerar 6 timestamps ideais igualmente espaçados
        const idealTimes = [];
        for (let i = 0; i < totalLabels; i++) {
            const time = new Date(startTime.getTime() + (i * intervalMillis));
            idealTimes.push(time);
        }

        // Controlar quais labels já foram usadas
        const usedLabels = new Array(totalLabels).fill(false);

        // Mapear cada ponto de dados para a label mais próxima
        const labels = data.map((item) => {
            const itemTime = new Date(item.timestamp);
            if (isNaN(itemTime.getTime())) return '';

            // Encontrar qual label ideal está mais próxima deste ponto
            let closestDistance = Infinity;
            let closestLabelIndex = -1;

            idealTimes.forEach((idealTime, index) => {
                if (idealTime && !usedLabels[index]) { // Só considerar labels não usadas
                    const distance = Math.abs(itemTime.getTime() - idealTime.getTime());
                    if (distance < closestDistance) {
                        closestDistance = distance;
                        closestLabelIndex = index;
                    }
                }
            });

            // Se este ponto está próximo de uma label ideal (dentro de 30min), mostrar a label
            const threshold = 30 * 60 * 1000; // 30 minutos
            if (closestDistance < threshold && closestLabelIndex !== -1) {
                const labelTime = idealTimes[closestLabelIndex];
                // Marcar esta label como usada para não repetir
                usedLabels[closestLabelIndex] = true;
                return labelFormat(labelTime);
            } else {
                return ''; // Sem label
            }
        });

        const visibleLabels = labels.filter(l => l !== '').length;
        console.log(`Time-based labels: ${data.length} points, ${visibleLabels} visible labels (${hours}h range)`);
        console.log(`Start time: ${startTime.toLocaleString('pt-BR')}, Interval: ${intervalMillis / 60000}min`);
        console.log(`Ideal times:`, idealTimes.map(t => t.toLocaleTimeString('pt-BR')));
        console.log(`Generated labels:`, labels.filter(l => l !== ''));

        return labels;
    }    // Manter função antiga para compatibilidade, mas não usar mais
    createSmartLabels(data, hours) {
        // Estratégia por range temporal
        let targetInterval;
        let labelFormat;

        if (hours <= 6) {
            // 6h: label a cada 1 hora
            targetInterval = 60; // minutos
            labelFormat = (date) => date.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } else if (hours <= 24) {
            // 24h: label a cada 2-4 horas
            targetInterval = 120; // 2 horas em minutos  
            labelFormat = (date) => date.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } else {
            // 3d+: label de dia em dia
            targetInterval = 1440; // 24 horas em minutos
            labelFormat = (date) => date.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: '2-digit'
            });
        }

        // Filtrar pontos com intervalos adequados
        const filteredData = [];
        const labels = [];
        let lastTimestamp = null;

        for (const item of data) {
            const currentDate = new Date(item.timestamp);
            if (isNaN(currentDate.getTime())) continue;

            if (!lastTimestamp) {
                // Primeiro ponto sempre inclui
                filteredData.push(item);
                labels.push(labelFormat(currentDate));
                lastTimestamp = currentDate;
            } else {
                const diffMinutes = Math.abs(currentDate - lastTimestamp) / (1000 * 60);

                if (diffMinutes >= targetInterval) {
                    filteredData.push(item);
                    labels.push(labelFormat(currentDate));
                    lastTimestamp = currentDate;
                }
            }
        }

        // Garantir que sempre temos pelo menos o último ponto
        if (data.length > 0 && filteredData.length > 0) {
            const lastItem = data[data.length - 1];
            const lastFilteredItem = filteredData[filteredData.length - 1];

            if (lastItem.timestamp !== lastFilteredItem.timestamp) {
                const lastDate = new Date(lastItem.timestamp);
                if (!isNaN(lastDate.getTime())) {
                    filteredData.push(lastItem);
                    labels.push(labelFormat(lastDate));
                }
            }
        }

        console.log(`Smart labels: ${data.length} points → ${filteredData.length} labels (${hours}h range)`);

        return { filteredData, labels };
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
