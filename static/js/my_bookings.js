(function() {
  window.toggleMenu = function(id) {
    // Close all other open menus first
    document.querySelectorAll('[id^="menu-"]').forEach(function(el) {
      if (!el.id.startsWith('menu-wrapper-') && el.id !== 'menu-' + id) {
        el.classList.add('hidden');
      }
    });
    const menu = document.getElementById('menu-' + id);
    if (menu) menu.classList.toggle('hidden');
  };

  // Close dropdown when clicking anywhere outside a menu wrapper
  document.addEventListener('click', function(e) {
    if (!e.target.closest('[id^="menu-wrapper-"]')) {
      document.querySelectorAll('[id^="menu-"]').forEach(function(el) {
        if (!el.id.startsWith('menu-wrapper-')) el.classList.add('hidden');
      });
    }
  });
})();
