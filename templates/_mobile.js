function filterRegion(region, btn) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    let hasVisible = false;
    document.querySelectorAll('.section-group').forEach(section => {
        if (region === 'all') {
            section.classList.remove('hidden');
            hasVisible = true;
        } else {
            const match = section.getAttribute('data-region') === region;
            section.classList.toggle('hidden', !match);
            if (match) hasVisible = true;
        }
    });
    // Hide zone sections that have no visible region groups
    document.querySelectorAll('.zone').forEach(zone => {
        if (region === 'all') {
            zone.style.display = '';
        } else {
            const hasContent = zone.querySelector('.section-group:not(.hidden)');
            zone.style.display = hasContent ? '' : 'none';
        }
    });
    const emptyEl = document.getElementById('emptyState');
    if (emptyEl) emptyEl.style.display = hasVisible ? 'none' : '';
}