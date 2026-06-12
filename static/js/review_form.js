(function() {
  const stars = document.querySelectorAll('.star-button');
  const ratingInput = document.querySelector('[name="rating"]');
  if (!stars.length || !ratingInput) return;

  function updateStars(value, isHover) {
    stars.forEach(s => {
      const sValue = parseInt(s.dataset.value);
      const svg = s.querySelector('.star-svg');
      if (!svg) return;
      if (sValue <= value) {
        // Filled star
        svg.setAttribute('fill', 'currentColor');
        svg.classList.remove('text-gray-600', 'text-gray-500');
        svg.classList.add(isHover ? 'text-amber-300' : 'text-amber-400', 'drop-shadow-lg');
        s.classList.add(isHover ? 'scale-110' : 'scale-100');
      } else {
        // Empty star
        svg.setAttribute('fill', 'none');
        svg.classList.remove('text-amber-400', 'text-amber-300', 'drop-shadow-lg');
        svg.classList.add('text-gray-500');
        s.classList.remove('scale-110', 'scale-125');
      }
    });
  }

  stars.forEach(star => {
    star.addEventListener('mouseenter', () => {
      const value = parseInt(star.dataset.value);
      updateStars(value, true);
    });
    
    star.addEventListener('mouseleave', () => {
      const currentValue = parseInt(ratingInput.value) || 0;
      updateStars(currentValue, false);
    });

    star.addEventListener('click', () => {
      const value = star.dataset.value;
      ratingInput.value = value;
      updateStars(value, false);
      // Give a tiny pop animation to the clicked star
      const svg = star.querySelector('.star-svg');
      if (svg) {
        svg.classList.add('scale-125');
        setTimeout(() => svg.classList.remove('scale-125'), 150);
      }
    });
  });

  // Initialize state
  const initialValue = parseInt(ratingInput.value) || 0;
  if(initialValue > 0) {
    updateStars(initialValue, false);
  }
})();
