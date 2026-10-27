document.addEventListener('DOMContentLoaded', function () {
    const viewMoreButton = document.getElementById('view-more-conditions');
    const extraCards = document.querySelectorAll('.extra-condition');

    if (viewMoreButton) {
        viewMoreButton.addEventListener('click', function () {
            const isOpen = viewMoreButton.classList.contains('active');

            extraCards.forEach(function (card) {
                if (isOpen) {
                    card.classList.remove('show');
                } else {
                    card.classList.add('show');
                }
            });

            viewMoreButton.classList.toggle('active');

            const text = viewMoreButton.querySelector('span');
            if (text) {
                text.textContent = isOpen ? 'View More' : 'View Less';
            }
        });
    }

    const searchInput = document.getElementById('treatment-search');
    const cards = document.querySelectorAll('#treatments-grid .treatment-card');
    const emptyMessage = document.getElementById('treatments-filter-empty');

    if (!searchInput || !cards.length) {
        return;
    }

    searchInput.addEventListener('input', function () {
        const query = searchInput.value.trim().toLowerCase();
        let visibleCount = 0;

        cards.forEach(function (card) {
            const match = !query || (card.dataset.name || '').includes(query);
            card.hidden = !match;
            if (match) {
                visibleCount += 1;
            }
        });

        if (emptyMessage) {
            emptyMessage.hidden = visibleCount > 0;
        }
    });
});
