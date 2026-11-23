(function () {
  'use strict';

  const form = document.querySelector('[data-multistep-form]');
  const summary = document.querySelector('[data-error-summary]');

  if (!form) {
    if (summary) {
      summary.focus();
    }
    return;
  }

  const steps = Array.from(form.querySelectorAll('[data-form-step]'));
  const progress = form.querySelector('[data-step-navigation]');
  const progressButtons = Array.from(form.querySelectorAll('[data-step-trigger]'));
  const progressTrack = form.querySelector('[data-step-progress]');
  const progressFill = form.querySelector('[data-step-progress-fill]');
  const progressStatus = form.querySelector('[data-step-status]');
  const submitActions = form.querySelector('[data-submit-actions]');

  if (!steps.length || progressButtons.length !== steps.length || !progress) {
    if (summary) {
      summary.focus();
    }
    return;
  }

  const completed = steps.map(() => false);
  const unlocked = steps.map((step, index) => index === 0);
  let currentStep = 0;

  const updateProgress = () => {
    progressButtons.forEach((button, index) => {
      button.disabled = !unlocked[index];
      button.classList.toggle('is-current', index === currentStep);
      button.classList.toggle('is-complete', completed[index]);
      if (index === currentStep) {
        button.setAttribute('aria-current', 'step');
      } else {
        button.removeAttribute('aria-current');
      }
    });

    const stepNumber = currentStep + 1;
    const stepTitle = steps[currentStep].querySelector('.fj-form-card__title').textContent.trim();
    progressStatus.textContent = `Étape ${stepNumber} sur ${steps.length} — ${stepTitle}`;
    progressTrack.setAttribute('aria-valuenow', String(stepNumber));
    progressFill.style.width = `${(stepNumber / steps.length) * 100}%`;
  };

  const activateStep = (index, focusHeading) => {
    currentStep = index;
    steps.forEach((step, stepIndex) => {
      step.hidden = stepIndex !== index;
      const actions = step.querySelector('[data-step-actions]');
      if (actions) {
        actions.hidden = stepIndex !== index;
      }
    });
    if (submitActions) {
      submitActions.hidden = index !== steps.length - 1;
    }
    updateProgress();

    if (focusHeading) {
      const heading = steps[index].querySelector('.fj-form-card__title');
      heading.setAttribute('tabindex', '-1');
      heading.focus({ preventScroll: true });
      steps[index].scrollIntoView({
        block: 'start',
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'auto'
          : 'smooth',
      });
    }
  };

  const updateConditionalValidity = () => {
    const customFieldNames = [
      'salary_max',
      'contact_phone',
      'whatsapp_number',
      'application_email',
      'application_phone',
      'application_url',
      'application_instructions',
    ];
    const fields = {};

    customFieldNames.forEach((name) => {
      fields[name] = form.querySelector(`[name="${name}"]`);
      if (fields[name]) {
        fields[name].setCustomValidity('');
      }
    });

    const salaryMin = form.querySelector('[name="salary_min"]');
    const salaryMax = fields.salary_max;
    if (
      salaryMin
      && salaryMax
      && salaryMin.value
      && salaryMax.value
      && Number(salaryMin.value) > Number(salaryMax.value)
    ) {
      salaryMax.setCustomValidity(
        'La rémunération maximale doit être supérieure ou égale au minimum.'
      );
    }

    const contactEmail = form.querySelector('[name="contact_email"]');
    if (
      contactEmail
      && fields.contact_phone
      && !contactEmail.value.trim()
      && !fields.contact_phone.value.trim()
    ) {
      fields.contact_phone.setCustomValidity(
        'Indiquez un e-mail ou un téléphone pour que nous puissions vérifier l’annonce.'
      );
    }

    const applicationMethod = form.querySelector('[name="application_method"]');
    const requirements = {
      whatsapp: ['whatsapp_number', 'Indiquez le numéro WhatsApp à utiliser.'],
      email: ['application_email', 'Indiquez l’adresse e-mail de candidature.'],
      phone: ['application_phone', 'Indiquez le téléphone de candidature.'],
      online: ['application_url', 'Indiquez le lien de candidature.'],
      physical: [
        'application_instructions',
        'Précisez l’adresse ou les modalités du dépôt physique.',
      ],
      other: [
        'application_instructions',
        'Précisez les modalités de candidature.',
      ],
    };
    const requirement = applicationMethod && requirements[applicationMethod.value];
    if (requirement) {
      const [fieldName, message] = requirement;
      if (fields[fieldName] && !fields[fieldName].value.trim()) {
        fields[fieldName].setCustomValidity(message);
      }
    }
  };

  const firstInvalidControl = (step) => {
    updateConditionalValidity();
    return Array.from(step.querySelectorAll('input, select, textarea')).find(
      (control) => !control.disabled && control.type !== 'hidden' && !control.checkValidity()
    );
  };

  const completePreviousSteps = (index) => {
    for (let stepIndex = 0; stepIndex < index; stepIndex += 1) {
      completed[stepIndex] = true;
      unlocked[stepIndex] = true;
    }
    unlocked[index] = true;
    for (let stepIndex = index + 1; stepIndex < steps.length; stepIndex += 1) {
      completed[stepIndex] = false;
      unlocked[stepIndex] = false;
    }
  };

  const advanceStep = () => {
    const invalidControl = firstInvalidControl(steps[currentStep]);
    if (invalidControl) {
      invalidControl.reportValidity();
      invalidControl.focus();
      return;
    }

    completed[currentStep] = true;
    if (currentStep < steps.length - 1) {
      unlocked[currentStep + 1] = true;
      activateStep(currentStep + 1, true);
    } else {
      updateProgress();
    }
  };

  const firstServerErrorStep = steps.findIndex((step) => step.querySelector('.has-error'));
  if (firstServerErrorStep > 0) {
    completePreviousSteps(firstServerErrorStep);
  }
  progress.hidden = false;
  activateStep(firstServerErrorStep >= 0 ? firstServerErrorStep : 0, false);

  const handleFieldEdit = (event) => {
    const field = event.target;
    const step = field instanceof Element ? field.closest('[data-form-step]') : null;
    const index = steps.indexOf(step);
    if (index < 0) {
      return;
    }

    updateConditionalValidity();
    for (let stepIndex = index; stepIndex < steps.length; stepIndex += 1) {
      completed[stepIndex] = false;
    }
    for (let stepIndex = index + 1; stepIndex < steps.length; stepIndex += 1) {
      unlocked[stepIndex] = false;
    }
    updateProgress();
  };

  form.addEventListener('input', handleFieldEdit);
  form.addEventListener('change', handleFieldEdit);

  form.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }

    const trigger = event.target.closest('[data-step-trigger]');
    if (trigger instanceof HTMLButtonElement) {
      const index = Number(trigger.dataset.stepTrigger);
      if (unlocked[index]) {
        activateStep(index, true);
      }
      return;
    }

    const nextButton = event.target.closest('[data-step-next]');
    if (nextButton instanceof HTMLButtonElement) {
      advanceStep();
      return;
    }

    const previousButton = event.target.closest('[data-step-previous]');
    if (previousButton instanceof HTMLButtonElement && currentStep > 0) {
      activateStep(currentStep - 1, true);
    }
  });

  if (summary) {
    summary.addEventListener('click', (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }
      const link = event.target.closest('a[href^="#"]');
      const targetId = link && link.getAttribute('href').slice(1);
      let target = targetId && document.getElementById(targetId);
      let targetStep = target && target.closest('[data-form-step]');
      if (!targetStep && link && link.dataset.errorTarget) {
        targetStep = steps.find((step) => Array.from(step.querySelectorAll('[name]')).some(
          (field) => field.name === link.dataset.errorTarget
        ));
        if (targetStep) {
          target = Array.from(targetStep.querySelectorAll('[name]')).find(
            (field) => field.name === link.dataset.errorTarget
          );
        }
      }
      const index = steps.indexOf(targetStep);
      if (!link || index < 0) {
        return;
      }

      event.preventDefault();
      for (let stepIndex = 0; stepIndex < index; stepIndex += 1) {
        const invalidControl = firstInvalidControl(steps[stepIndex]);
        if (invalidControl) {
          completePreviousSteps(stepIndex);
          activateStep(stepIndex, false);
          invalidControl.reportValidity();
          invalidControl.focus();
          return;
        }
        completed[stepIndex] = true;
        unlocked[stepIndex] = true;
      }
      unlocked[index] = true;
      activateStep(index, false);
      target.focus();
    });
    summary.focus();
  }

  form.addEventListener('submit', (event) => {
    if (currentStep < steps.length - 1) {
      event.preventDefault();
      advanceStep();
      return;
    }

    for (let index = 0; index < steps.length; index += 1) {
      const invalidControl = firstInvalidControl(steps[index]);
      if (invalidControl) {
        event.preventDefault();
        completePreviousSteps(index);
        activateStep(index, false);
        invalidControl.reportValidity();
        invalidControl.focus();
        return;
      }
    }
  });
})();
