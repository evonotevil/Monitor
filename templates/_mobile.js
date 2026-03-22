function filterRegion(region, btn) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.section-group').forEach(section => {
        if (region === 'all') {
            section.classList.remove('hidden');
        } else {
            section.classList.toggle('hidden', section.getAttribute('data-region') !== region);
        }
    });
}