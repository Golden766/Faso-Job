document.addEventListener('DOMContentLoaded', () => {
  const storageKey = 'fasojob:favorites:v1';
  const status = document.querySelector('[data-favorites-status]');
  const favoriteList = document.querySelector('[data-favorites-list]');
  const emptyState = document.querySelector('[data-favorites-empty]');
  const errorState = document.querySelector('[data-favorites-error]');
  const noScriptNotice = document.querySelector('[data-favorites-noscript]');
  let favorites = null;

  const announce = (message) => {
    if (status) {
      status.textContent = message;
      status.hidden = false;
    }
  };

  const normalizeFavorites = (items) => {
    if (!Array.isArray(items)) {
      throw new Error('invalid-favorites');
    }

    return items.map((item) => {
      if (
        !item
        || typeof item.id !== 'string'
        || !item.id
        || typeof item.title !== 'string'
        || typeof item.company !== 'string'
        || typeof item.url !== 'string'
      ) {
        throw new Error('invalid-favorite');
      }

      const url = new URL(item.url, window.location.origin);
      if (url.origin !== window.location.origin) {
        throw new Error('invalid-favorite-url');
      }

      return {
        id: item.id,
        title: item.title,
        company: item.company,
        url: `${url.pathname}${url.search}${url.hash}`,
      };
    });
  };

  const readFavorites = () => {
    try {
      const stored = window.localStorage.getItem(storageKey);
      return stored ? normalizeFavorites(JSON.parse(stored)) : [];
    } catch {
      announce('Impossible de lire vos favoris dans le stockage de ce navigateur.');
      return null;
    }
  };

  const writeFavorites = (nextFavorites) => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(nextFavorites));
      return true;
    } catch {
      announce('Impossible d’enregistrer ce favori. Vérifiez le stockage de votre navigateur.');
      return false;
    }
  };

  const renderFavorites = () => {
    document.querySelectorAll('[data-favorites-count]').forEach((count) => {
      count.textContent = String(favorites ? favorites.length : 0);
      count.hidden = !favorites || favorites.length === 0;
    });

    document.querySelectorAll('[data-favorite-toggle]').forEach((button) => {
      if (!favorites) {
        button.hidden = true;
        return;
      }

      const isSaved = favorites.some((favorite) => favorite.id === button.dataset.favoriteId);
      button.setAttribute('aria-pressed', String(isSaved));
      button.querySelector('[data-favorite-label]').textContent = isSaved
        ? 'Retirer des favoris'
        : 'Ajouter aux favoris';
      button.hidden = false;
    });

    if (!favoriteList) {
      return;
    }

    if (!favorites) {
      favoriteList.hidden = true;
      if (emptyState) {
        emptyState.hidden = true;
      }
      if (errorState) {
        errorState.hidden = false;
      }
      if (noScriptNotice) {
        noScriptNotice.hidden = true;
      }
      return;
    }

    favoriteList.replaceChildren();
    favorites.forEach((favorite) => {
      const item = document.createElement('li');
      item.className = 'fj-favorite-item';

      const details = document.createElement('div');
      details.className = 'fj-favorite-item__details';

      const link = document.createElement('a');
      link.className = 'fj-favorite-item__title';
      link.href = favorite.url;
      link.textContent = favorite.title;

      const company = document.createElement('p');
      company.className = 'fj-small';
      company.textContent = favorite.company;

      const removeButton = document.createElement('button');
      removeButton.className = 'fj-btn fj-btn--secondary fj-btn--sm';
      removeButton.type = 'button';
      removeButton.dataset.favoriteRemove = favorite.id;
      removeButton.setAttribute('aria-label', `Retirer ${favorite.title} des favoris`);
      removeButton.textContent = 'Retirer';

      details.append(link, company);
      item.append(details, removeButton);
      favoriteList.appendChild(item);
    });

    favoriteList.hidden = favorites.length === 0;
    if (emptyState) {
      emptyState.hidden = favorites.length !== 0;
    }
    if (errorState) {
      errorState.hidden = true;
    }
    if (noScriptNotice) {
      noScriptNotice.hidden = true;
    }
  };

  const toggleFavorite = (button) => {
    const id = button.dataset.favoriteId;
    const existingIndex = favorites.findIndex((favorite) => favorite.id === id);
    let updatedFavorites;

    if (existingIndex >= 0) {
      updatedFavorites = favorites.filter((favorite) => favorite.id !== id);
    } else {
      try {
        const [favorite] = normalizeFavorites([{
          id,
          title: button.dataset.favoriteTitle,
          company: button.dataset.favoriteCompany,
          url: button.dataset.favoriteUrl,
        }]);
        updatedFavorites = [...favorites, favorite];
      } catch {
        announce('Impossible d’enregistrer cette offre dans vos favoris.');
        return;
      }
    }

    if (writeFavorites(updatedFavorites)) {
      favorites = updatedFavorites;
      renderFavorites();
      announce(existingIndex >= 0 ? 'Offre retirée des favoris.' : 'Offre ajoutée aux favoris.');
    }
  };

  favorites = readFavorites();
  renderFavorites();

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element) || !favorites) {
      return;
    }

    const toggleButton = event.target.closest('[data-favorite-toggle]');
    if (toggleButton instanceof HTMLButtonElement) {
      toggleFavorite(toggleButton);
      return;
    }

    const removeButton = event.target.closest('[data-favorite-remove]');
    if (removeButton instanceof HTMLButtonElement) {
      const id = removeButton.dataset.favoriteRemove;
      const updatedFavorites = favorites.filter((favorite) => favorite.id !== id);
      if (writeFavorites(updatedFavorites)) {
        favorites = updatedFavorites;
        renderFavorites();
        announce('Offre retirée des favoris.');
      }
    }
  });

  window.addEventListener('storage', (event) => {
    if (event.key === storageKey || event.key === null) {
      favorites = readFavorites();
      renderFavorites();
    }
  });
});
