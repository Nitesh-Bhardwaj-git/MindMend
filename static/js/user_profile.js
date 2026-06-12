(function() {
  window.switchToEdit = function() {
    const viewMode = document.getElementById('viewMode');
    const editMode = document.getElementById('editMode');
    if (viewMode) viewMode.classList.add('hidden');
    if (editMode) editMode.classList.remove('hidden');
  };

  window.switchToView = function() {
    const viewMode = document.getElementById('viewMode');
    const editMode = document.getElementById('editMode');
    if (editMode) editMode.classList.add('hidden');
    if (viewMode) viewMode.classList.remove('hidden');
  };

  const config = window.USER_PROFILE_CONFIG || {};
  if (config.hasErrors) {
    window.switchToEdit();
  }
})();
