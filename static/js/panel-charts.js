/* Panel grafiklari.
   HTML:  {{ data|json_script:"my-data" }}
          <canvas data-chart="line|doughnut|bar" data-source="my-data"></canvas>
   Ma'lumot: { labels: [...], series: [{ name, data }] } yoki { labels, data }.
   Matn <script> ichiga qo'lda yozilmaydi — kitob nomi sahifani buza olmaydi. */
(function () {
  'use strict';
  if (!window.Chart) return;

  const PALETTE = ['#17a088', '#ec5b30', '#fdb924', '#3559b5', '#8247bd', '#0e8ba1', '#8a9a5b', '#b4536b'];

  const options = {
    line: () => ({
      interaction: { mode: 'index', intersect: false },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } },
    }),
    bar: () => ({
      indexAxis: 'y',
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } },
    }),
    doughnut: () => ({ cutout: '62%' }),
  };

  document.querySelectorAll('canvas[data-chart]').forEach((canvas) => {
    const source = document.getElementById(canvas.dataset.source);
    if (!source) return;
    const payload = JSON.parse(source.textContent);
    const type = canvas.dataset.chart;
    const series = payload.series || [{ name: '', data: payload.data }];

    const datasets = series.map((item, index) => {
      const color = PALETTE[index % PALETTE.length];
      if (type === 'doughnut') return { label: item.name, data: item.data, backgroundColor: PALETTE, borderWidth: 0 };
      if (type === 'bar') return { label: item.name, data: item.data, backgroundColor: color, borderRadius: 4 };
      return {
        label: item.name, data: item.data, borderColor: color, backgroundColor: color + '22',
        fill: index === 0, tension: 0.35, borderWidth: 2.5, pointRadius: item.data.length > 60 ? 0 : 2,
        pointHoverRadius: 5, pointBackgroundColor: color,
      };
    });

    const legend = type === 'doughnut'
      ? { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
      : { display: series.length > 1, labels: { boxWidth: 12 } };

    new window.Chart(canvas, {
      type: type,
      data: { labels: payload.labels, datasets: datasets },
      options: Object.assign({ responsive: true, maintainAspectRatio: false, plugins: { legend: legend } },
        options[type]()),
    });
  });
}());
