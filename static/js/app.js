document.addEventListener('click', function (event) {
  // Sidebar (mobile)
  var toggle = event.target.closest('[data-sidebar-toggle]');
  var sidebar = document.getElementById('sidebar');
  var scrim = document.querySelector('.app-scrim');
  if (toggle && sidebar) {
    sidebar.classList.toggle('open');
    if (scrim) { scrim.classList.toggle('open'); }
  }
  var close = event.target.closest('[data-sidebar-close]');
  if (close && sidebar) {
    sidebar.classList.remove('open');
    if (scrim) { scrim.classList.remove('open'); }
  }

  // Modal close buttons
  var closer = event.target.closest('[data-modal-close]');
  if (closer) {
    var modal = closer.closest('.modal-backdrop');
    if (modal) { modal.hidden = true; }
  }
});

document.addEventListener('keydown', function (event) {
  if (event.key === 'Escape') {
    document.querySelectorAll('.modal-backdrop:not([hidden])').forEach(function (m) {
      m.hidden = true;
    });
    var sidebar = document.getElementById('sidebar');
    var scrim = document.querySelector('.app-scrim');
    if (sidebar && sidebar.classList.contains('open')) {
      sidebar.classList.remove('open');
      if (scrim) { scrim.classList.remove('open'); }
    }
  }
});