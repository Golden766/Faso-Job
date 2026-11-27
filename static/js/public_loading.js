document.addEventListener('DOMContentLoaded', () => {
  const loader = document.getElementById('fj-page-loader');
  if (!loader) return;

  const setLoaderLabel = (label) => {
    const labelNode = loader.querySelector('.fj-page-loader__label');
    if (labelNode) {
      labelNode.textContent = label;
    }
  };

  const showLoader = (label = 'Chargement…') => {
    setLoaderLabel(label);
    loader.hidden = false;
    loader.setAttribute('aria-busy', 'true');
  };

  const hideLoader = () => {
    loader.hidden = true;
    loader.setAttribute('aria-busy', 'false');
  };

  const applyButtonLoadingState = (button) => {
    if (!(button instanceof HTMLButtonElement)) return;
    const label = button.querySelector('.fj-btn__label');

    button.setAttribute('aria-busy', 'true');
    button.classList.add('is-loading');
    button.disabled = true;

    if (label) {
      label.textContent = 'Chargement…';
    } else {
      const currentText = button.textContent.trim() || 'Chargement…';
      button.innerHTML = '<span class="fj-btn__label">Chargement…</span><span class="fj-spinner" aria-hidden="true"></span>';
      button.dataset.originalLabel = currentText;
    }
  };

  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', () => {
      if (form.dataset.skipLoader === 'true') return;

      const submitButton = form.querySelector('button[type="submit"]');
      const formAction = (form.getAttribute('action') || '').toLowerCase();
      const isPublicPage = formAction.includes('catalogue') || formAction.includes('home') || formAction.includes('offres');
      const isSearchOrFilterForm = form.classList.contains('fj-search') || form.classList.contains('fj-filter-panel') || form.classList.contains('fj-mobile-search') || form.classList.contains('fj-sort');

      if (submitButton) {
        applyButtonLoadingState(submitButton);
      }

      if (isPublicPage || isSearchOrFilterForm) {
        showLoader('Chargement des offres…');
      }
    });
  });

  document.querySelectorAll('a[href]').forEach((link) => {
    if (link.closest('[data-no-loader="true"]')) return;

    const href = link.getAttribute('href') || '';
    if (!href || href.startsWith('#')) return;
    if (!(href.startsWith('/') || href.startsWith('./') || href.startsWith('../') || href.includes('catalogue') || href.includes('submit_offer'))) {
      return;
    }

    link.addEventListener('click', () => {
      if (link.getAttribute('target') === '_blank') return;
      showLoader('Ouverture…');
    });
  });

  const offersLists = document.querySelectorAll('[data-offers-list]');
  offersLists.forEach((list) => {
    list.dataset.loading = 'false';
  });

  if (performance.getEntriesByType('navigation').length > 0) {
    setTimeout(() => hideLoader(), 180);
  }

  window.addEventListener('pageshow', () => {
    hideLoader();
  });
});
