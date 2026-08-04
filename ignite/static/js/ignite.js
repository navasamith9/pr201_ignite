document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('[data-sidebar]');
  const backdrop = document.querySelector('[data-sidebar-backdrop]');
  const toggle = document.querySelector('[data-sidebar-toggle]');

  const closeSidebar = () => {
    sidebar?.classList.remove('is-open');
    backdrop?.classList.remove('is-open');
  };

  toggle?.addEventListener('click', () => {
    sidebar?.classList.add('is-open');
    backdrop?.classList.add('is-open');
  });
  backdrop?.addEventListener('click', closeSidebar);
  document.querySelectorAll('.ignite-sidebar a').forEach((link) => link.addEventListener('click', closeSidebar));
});
