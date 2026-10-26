export function element(tagName, { className, text, attributes } = {}, children = []) {
  const node = document.createElement(tagName);
  if (className) {
    node.className = className;
  }
  if (text !== undefined && text !== null) {
    node.textContent = String(text);
  }
  for (const [name, value] of Object.entries(attributes ?? {})) {
    node.setAttribute(name, value);
  }
  for (const child of children) {
    node.append(child);
  }
  return node;
}

export function icon(name, className) {
  return element('i', {
    className,
    attributes: { 'data-lucide': name, 'aria-hidden': 'true' },
  });
}

export function refreshIcons() {
  window.lucide?.createIcons();
}

export function byId(id) {
  return document.getElementById(id);
}

export function formatTimestamp(isoTimestamp) {
  if (!isoTimestamp) {
    return '—';
  }
  return `${isoTimestamp.slice(0, 10)} ${isoTimestamp.slice(11, 16)} UTC`;
}

export function lessonCountLabel(count) {
  return `${count} ${count === 1 ? 'aula' : 'aulas'}`;
}

export function errorAlert(message) {
  return element('p', { className: 'alert alert--error', attributes: { role: 'alert' } }, [
    icon('circle-alert'),
    element('span', { text: message }),
  ]);
}

export function showError(container, message) {
  container.replaceChildren(errorAlert(message));
  container.hidden = false;
  refreshIcons();
}

export function clearError(container) {
  container.replaceChildren();
  container.hidden = true;
}

export function statusBadge(isCompleted) {
  if (isCompleted) {
    return element('span', { className: 'status-badge status-badge--completed' }, [
      icon('circle-check'),
      'Concluída',
    ]);
  }
  return element('span', { className: 'status-badge status-badge--pending' }, [icon('circle'), 'Pendente']);
}

export function queryNumber(name) {
  const value = new URLSearchParams(window.location.search).get(name);
  if (!value || !/^\d+$/.test(value)) {
    return null;
  }
  return Number(value);
}

export function setBusy(form, isBusy) {
  for (const button of form.querySelectorAll('button')) {
    button.disabled = isBusy;
  }
}

export function onSubmit(form, errorContainer, submit) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearError(errorContainer);
    setBusy(form, true);
    try {
      await submit(new FormData(form));
    } catch (error) {
      console.error(error);
      showError(errorContainer, error.message);
    } finally {
      setBusy(form, false);
    }
  });
}

export async function runPage(renderPage) {
  try {
    await renderPage();
  } catch (error) {
    console.error(error);
    showError(byId('page-error'), error.message);
  } finally {
    refreshIcons();
  }
}
