document.addEventListener("DOMContentLoaded", function () {
  const steps = document.querySelectorAll(".question-step");
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");
  const submitBtn = document.getElementById("submitBtn");
  const progressBar = document.getElementById("progressBar");
  const progressPercent = document.getElementById("progressPercent");
  const questionCount = document.getElementById("questionCount");

  let currentStep = 0;

  function updateProgress() {
    const progress = ((currentStep + 1) / steps.length) * 100;
    progressBar.style.width = progress + "%";
    progressPercent.textContent = Math.round(progress) + "%";
    questionCount.textContent = `QUESTION ${currentStep + 1} OF ${steps.length}`;
  }

  function isCurrentStepAnswered() {
    const currentQuestion = steps[currentStep];
    const checked = currentQuestion.querySelector('input[type="radio"]:checked');
    return !!checked;
  }

  function updateNextBtnState() {
    const answered = isCurrentStepAnswered();
    if (answered) {
      nextBtn.disabled = false;
      nextBtn.classList.add('next-active');
    } else {
      nextBtn.disabled = true;
      nextBtn.classList.remove('next-active');
    }
  }

  function updateSubmitStyle() {
    if (currentStep === steps.length - 1) {
      if (isCurrentStepAnswered()) {
        submitBtn.classList.remove('submit-faded');
        submitBtn.classList.add('submit-active');
        submitBtn.disabled = false;
      } else {
        submitBtn.classList.add('submit-faded');
        submitBtn.classList.remove('submit-active');
        submitBtn.disabled = true;
      }
    }
  }

  let popupShown = false;
  const distressModal = document.getElementById("distressModal");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const firstRadio = document.querySelector('input[type="radio"]');
  const prefix = firstRadio ? firstRadio.id.split('_')[0] : '';

  function isBadResponse(stepIndex, value) {
    const val = parseInt(value, 10);
    if (prefix === 'pss') {
      // PSS-10: reversed questions are index 3, 4, 6, 7 (0-indexed)
      const reversedIndices = [3, 4, 6, 7];
      if (reversedIndices.includes(stepIndex)) {
        return val <= 1; // 0 or 1 is bad for reversed
      } else {
        return val >= 2; // 2 or 3 is bad for standard
      }
    }
    // For PHQ-9 and GAD-7, 2 or 3 is bad
    return val >= 2;
  }

  function checkDistressPopup() {
    if (popupShown || !distressModal) return;
    let badResponseCount = 0;
    steps.forEach((step, stepIndex) => {
      const checked = step.querySelector('input[type="radio"]:checked');
      if (checked) {
        if (isBadResponse(stepIndex, checked.value)) {
          badResponseCount++;
        }
      }
    });

    if (badResponseCount >= 4) {
      distressModal.classList.remove("hidden");
      // Force reflow
      distressModal.offsetHeight;
      distressModal.classList.add("opacity-100");
      popupShown = true;
    }
  }

  if (closeModalBtn) {
    closeModalBtn.addEventListener("click", function () {
      if (!distressModal) return;
      distressModal.classList.remove("opacity-100");
      setTimeout(() => {
        distressModal.classList.add("hidden");
      }, 300);
    });
  }

  function attachRadioListeners(stepIndex) {
    const stepEl = steps[stepIndex];
    const radios = stepEl.querySelectorAll('input[type="radio"]');
    radios.forEach(radio => {
      radio.addEventListener('change', function () {
        if (stepIndex === steps.length - 1) {
          updateSubmitStyle();
        } else {
          updateNextBtnState();
        }
        checkDistressPopup();
      });
    });
  }

  function showStep(index) {
    steps.forEach((step, i) => {
      if (i === index) {
        step.classList.remove("hidden");
      } else {
        step.classList.add("hidden");
      }
    });

    prevBtn.disabled = index === 0;

    if (index === steps.length - 1) {
      nextBtn.classList.add("hidden");
      submitBtn.classList.remove("hidden");
      updateSubmitStyle();
    } else {
      nextBtn.classList.remove("hidden");
      submitBtn.classList.add("hidden");
      updateNextBtnState();
    }

    document.body.classList.toggle("assessment-last", index === steps.length - 1);
    updateProgress();
  }

  // Attach radio change listeners to all steps
  steps.forEach((_, i) => attachRadioListeners(i));

  nextBtn.addEventListener("click", function () {
    if (!isCurrentStepAnswered() || nextBtn.disabled) return;
    if (currentStep < steps.length - 1) {
      currentStep++;
      showStep(currentStep);
    }
  });

  prevBtn.addEventListener("click", function () {
    if (currentStep > 0) {
      currentStep--;
      showStep(currentStep);
    }
  });

  showStep(currentStep);
});
