// static/js/charts.js
// Chart.js helpers for live timeline and analytics

const EMOTION_COLORS = {
  happy:    '#FFD700',
  sad:      '#4A90D9',
  angry:    '#E74C3C',
  fear:     '#E67E22',
  disgust:  '#27AE60',
  surprise: '#9B59B6',
  neutral:  '#95A5A6',
};

const EMOTIONS = ['angry','disgust','fear','happy','sad','surprise','neutral'];
const MAX_POINTS = 30;

// ── Live Timeline Chart (Dashboard) ──────────────────────────────────────────
let timelineChart = null;

function initTimelineChart(canvasId) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const labels = [];
  const datasets = EMOTIONS.map(e => ({
    label: e.charAt(0).toUpperCase() + e.slice(1),
    data: [],
    borderColor: EMOTION_COLORS[e],
    backgroundColor: EMOTION_COLORS[e] + '22',
    tension: 0.4,
    fill: false,
    pointRadius: 3,
    borderWidth: 2,
  }));

  timelineChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: '#8892b0', font: { size: 11 }, padding: 8 },
          position: 'bottom',
        },
        tooltip: {
          backgroundColor: 'rgba(10,10,26,0.95)',
          titleColor: '#f0f4ff',
          bodyColor: '#8892b0',
          borderColor: 'rgba(108,99,255,0.4)',
          borderWidth: 1,
        }
      },
      scales: {
        x: {
          ticks: { color: '#4a5568', font: { size: 10 }, maxRotation: 0 },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          min: 0, max: 100,
          ticks: { color: '#4a5568', font: { size: 10 }, callback: v => v + '%' },
          grid: { color: 'rgba(255,255,255,0.04)' },
        }
      }
    }
  });
  return timelineChart;
}

function updateTimelineChart(chart, timestamp, emotions) {
  if (!chart) return;
  chart.data.labels.push(timestamp);
  EMOTIONS.forEach((e, i) => {
    chart.data.datasets[i].data.push(emotions[e] || 0);
  });

  // Rolling window
  if (chart.data.labels.length > MAX_POINTS) {
    chart.data.labels.shift();
    chart.data.datasets.forEach(ds => ds.data.shift());
  }
  chart.update('none');
}

// ── Donut Chart (Analytics) ───────────────────────────────────────────────────
function initDonutChart(canvasId, distribution) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const labels = Object.keys(distribution);
  const data   = Object.values(distribution);
  const colors = labels.map(e => EMOTION_COLORS[e] || '#888');

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.map(e => e.charAt(0).toUpperCase() + e.slice(1)),
      datasets: [{
        data,
        backgroundColor: colors.map(c => c + 'bb'),
        borderColor: colors,
        borderWidth: 2,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: {
          labels: { color: '#8892b0', font: { size: 11 }, padding: 10 },
          position: 'bottom',
        },
        tooltip: {
          backgroundColor: 'rgba(10,10,26,0.95)',
          titleColor: '#f0f4ff',
          bodyColor: '#8892b0',
          borderColor: 'rgba(108,99,255,0.4)',
          borderWidth: 1,
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.parsed.toFixed(1)}%`
          }
        }
      }
    }
  });
}

// ── Session Timeline Chart (Analytics) ───────────────────────────────────────
function initSessionTimeline(canvasId, timelineData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !timelineData) return null;

  return new Chart(ctx, {
    type: 'line',
    data: timelineData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: '#8892b0', font: { size: 11 }, padding: 8 },
          position: 'bottom',
        },
        tooltip: {
          backgroundColor: 'rgba(10,10,26,0.95)',
          titleColor: '#f0f4ff',
          bodyColor: '#8892b0',
          borderColor: 'rgba(108,99,255,0.4)',
          borderWidth: 1,
        }
      },
      scales: {
        x: {
          ticks: { color: '#4a5568', font: { size: 10 }, maxRotation: 0, maxTicksLimit: 10 },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          min: 0, max: 100,
          ticks: { color: '#4a5568', font: { size: 10 }, callback: v => v + '%' },
          grid: { color: 'rgba(255,255,255,0.04)' },
        }
      }
    }
  });
}
