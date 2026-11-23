document.addEventListener('DOMContentLoaded', () => {
  const buttons = document.querySelectorAll('[data-copy-link]');
  const status = document.querySelector('[data-share-status]');

  if (!buttons.length) {
    return;
  }

  const announce = (message) => {
    if (status) {
      status.textContent = message;
    }
  };

  const copyWithFallback = () => {
    const field = document.createElement('input');
    field.value = window.location.href;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(field);
    if (!copied) {
      throw new Error('copy-unavailable');
    }
  };

  buttons.forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          try {
            await navigator.clipboard.writeText(window.location.href);
          } catch (error) {
            copyWithFallback();
          }
        } else {
          copyWithFallback();
        }
        announce('Lien de l’offre copié dans le presse-papier.');
      } catch (error) {
        announce('Impossible de copier le lien. Copiez l’adresse depuis la barre du navigateur.');
      }
    });
  });
});
