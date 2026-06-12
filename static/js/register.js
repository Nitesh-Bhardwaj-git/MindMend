(function() {
  window.togglePass = function(btn) {
    var inp = btn.parentElement.querySelector('input');
    var eyeOpen = btn.querySelector('.eye-open');
    var eyeClosed = btn.querySelector('.eye-closed');
    if (!inp || !eyeOpen || !eyeClosed) return;
    if (inp.type === 'password') {
        inp.type = 'text';
        eyeOpen.classList.add('hidden');
        eyeClosed.classList.remove('hidden');
    } else {
        inp.type = 'password';
        eyeOpen.classList.remove('hidden');
        eyeClosed.classList.add('hidden');
    }
  };
})();
