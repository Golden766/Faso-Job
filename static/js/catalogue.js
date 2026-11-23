document.addEventListener('DOMContentLoaded', () => {
  const sortSelect = document.querySelector('#catalogue-sort');
  if (sortSelect instanceof HTMLSelectElement && sortSelect.form) {
    const sortForm = sortSelect.form;
    const submitButton = sortForm.querySelector('button[type="submit"]');

    sortSelect.addEventListener('change', () => {
      sortForm.requestSubmit();
    });

    if (submitButton instanceof HTMLButtonElement) {
      submitButton.hidden = true;
    }
  }

  const openButton = document.querySelector('.mobile-filter-toggle, .fj-filter-open');
  const filtersDialog = document.querySelector('#catalogue-filters');
  const closeButton = document.querySelector('.filters-close');

  if (!openButton || !(filtersDialog instanceof HTMLDialogElement) || !closeButton) {
    return;
  }

  const filterForm = filtersDialog.querySelector('.fj-dialog__body');
  const filterCount = openButton.querySelector('[data-filter-count]');

  if (filterForm instanceof HTMLFormElement && filterCount instanceof HTMLElement) {
    const updateFilterCount = () => {
      const valueFilters = Array.from(
        filterForm.querySelectorAll(
          'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select'
        )
      ).filter((field) => field.value.trim() !== '').length;
      const checkedFilters = filterForm.querySelectorAll(
        'input[type="checkbox"]:checked, input[type="radio"]:checked'
      ).length;
      const activeCount = valueFilters + checkedFilters;

      filterCount.textContent = String(activeCount);
      filterCount.hidden = activeCount === 0;
    };

    filterForm.addEventListener('input', updateFilterCount);
    filterForm.addEventListener('change', updateFilterCount);
  }

  openButton.addEventListener('click', () => {
    filtersDialog.showModal();
  });

  closeButton.addEventListener('click', () => {
    filtersDialog.close();
    openButton.focus();
  });

  window.matchMedia('(min-width: 1024px)').addEventListener('change', (event) => {
    if (event.matches && filtersDialog.open) {
      filtersDialog.close();
    }
  });

  filtersDialog.addEventListener('click', (event) => {
    if (event.target === filtersDialog) {
      filtersDialog.close();
      openButton.focus();
    }
  });
});
